import asyncio
import paho.mqtt.client as mqtt
import argparse
from datetime import datetime
from ocpp.v16 import ChargePoint as OcppChargePoint
from ocpp.v16 import call, call_result
from ocpp.v16.enums import RegistrationStatus, ConfigurationStatus, AvailabilityStatus, ChargePointStatus
from ocpp.routing import on
import websockets
import daemon
import sys

# Default Configuration
DEFAULT_WS_ADDRESS = "0.0.0.0"
DEFAULT_WS_PORT = 9000
DEFAULT_CHARGE_POINT_ID = "juicepassproxy"
MQTT_BROKER = "127.0.0.1"
MQTT_PORT = 1883
MQTT_USER = ""
MQTT_PASSWORD = ""
VOLTAGE_TOPIC = "hmd/sensor/JuiceBox/Voltage/state"
FREQUENCY_TOPIC = "hmd/sensor/JuiceBox/Frequency/state"
TEMPERATURE_TOPIC = "hmd/sensor/JuiceBox/Temperature/state"
POWER_FACTOR_TOPIC = "hmd/sensor/JuiceBox/Power-Factor/state"
CURRENT_TOPIC = "hmd/sensor/JuiceBox/Current/state"
POWER_TOPIC = "hmd/sensor/JuiceBox/Power/state"
CURRENT_OFFERED_TOPIC = "hmd/sensor/JuiceBox/Max-Current-Online-Device-/state"
ENERGY_ACTIVE_IMPORT_TOPIC = "hmd/sensor/JuiceBox/Energy--Session-/state"
STATUS_TOPIC = "hmd/sensor/JuiceBox/Status/state"

# Argument Parsing
parser = argparse.ArgumentParser(description="EVSE OCPP Client with MQTT")
parser.add_argument("--mqtt_address", default=MQTT_BROKER, help="MQTT broker address")
parser.add_argument("--mqtt_port", type=int, default=MQTT_PORT, help="MQTT broker port")
parser.add_argument("--mqtt_user", default=MQTT_USER, help="MQTT username")
parser.add_argument("--mqtt_pass", default=MQTT_PASSWORD, help="MQTT password")
parser.add_argument("--ws_address", default=DEFAULT_WS_ADDRESS, help="WebSocket server address")
parser.add_argument("--ws_port", type=int, default=DEFAULT_WS_PORT, help="WebSocket server port")
parser.add_argument("--chargepoint_id", default=DEFAULT_CHARGE_POINT_ID, help="ChargePoint ID for OCPP server")
parser.add_argument("--debug", action="store_true", help="Enable debug output")
parser.add_argument("-d", "--daemon", action="store_true", help="Run as a daemon in the background")
args = parser.parse_args()

# Function for conditional debug output
def debug_log(message):
    if args.debug:
        print(f"[DEBUG] {message}")

class EVSEClient(OcppChargePoint):
    def __init__(self, id, connection):
        super().__init__(id, connection)
        self.current_voltage = None
        self.current_frequency = None
        self.current_temperature = None
        self.current_power_factor = None
        self.current_import = None
        self.power_active_import = None
        self.current_offered = None
        self.energy_active_import_register = None
        self.status = None

    async def send_boot_notification(self):
        request = call.BootNotification(
            charge_point_model="EVChargerSim",
            charge_point_vendor="OpenAI"
        )
        try:
            response = await self.call(request)
            debug_log(f"BootNotification response: {response.status}")
            return response.status == RegistrationStatus.accepted
        except Exception as e:
            print(f"[ERROR] BootNotification failed: {e}")
            return False

    async def send_meter_values(self):
        if not self._connection:
            print("[WARNING] WebSocket connection is not active. Cannot send MeterValues.")
            return

        sampled_values = []
        if self.current_voltage is not None:
            sampled_values.append({"measurand": "Voltage", "value": str(self.current_voltage), "unit": "V"})
        if self.current_frequency is not None:
            sampled_values.append({"measurand": "Frequency", "value": str(self.current_frequency), "unit": "Hertz"})
        if self.current_temperature is not None:
            sampled_values.append({"measurand": "Temperature", "value": str(self.current_temperature), "unit": "Celsius"})
        if self.current_power_factor is not None:
            sampled_values.append({"measurand": "Power.Factor", "value": str(self.current_power_factor * 100), "unit": "Percent"})
        if self.current_import is not None:
            sampled_values.append({"measurand": "Current.Import", "value": str(self.current_import), "unit": "A"})
        if self.power_active_import is not None:
            sampled_values.append({"measurand": "Power.Active.Import", "value": str(self.power_active_import), "unit": "W"})
        if self.current_offered is not None:
            sampled_values.append({"measurand": "Current.Offered", "value": str(self.current_offered), "unit": "A"})
        if self.energy_active_import_register is not None:
            sampled_values.append({"measurand": "Energy.Active.Import.Register", "value": str(self.energy_active_import_register), "unit": "Wh"})

        debug_log(f"Preparing to send MeterValues with sampled values: {sampled_values}")

        if sampled_values:
            try:
                request = call.MeterValues(
                    connector_id=1,
                    meter_value=[{
                        "timestamp": datetime.utcnow().isoformat(),
                        "sampledValue": sampled_values
                    }]
                )
                response = await self.call(request)
                debug_log(f"MeterValues sent successfully with values: {sampled_values}")
            except Exception as e:
                print(f"[ERROR] Failed to send MeterValues: {e}")

    async def send_status_notification(self, status):
        status_map = {
            "Available": ChargePointStatus.available,
            "Preparing": ChargePointStatus.preparing,
            "Charging": ChargePointStatus.charging,
            "Suspended": ChargePointStatus.suspended_ev,
            "Finishing": ChargePointStatus.finishing,
            "Reserved": ChargePointStatus.reserved,
            "Unavailable": ChargePointStatus.unavailable,
            "Faulted": ChargePointStatus.faulted,
        }
        mapped_status = status_map.get(status, ChargePointStatus.unavailable)
        
        request = call.StatusNotification(
            connector_id=1,
            error_code="NoError",
            status=mapped_status,
            timestamp=datetime.utcnow().isoformat()
        )
        try:
            response = await self.call(request)
            debug_log(f"StatusNotification sent successfully with status: {status}")
        except Exception as e:
            print(f"[ERROR] Failed to send StatusNotification: {e}")

class EVSEManager:
    def __init__(self):
        self.cp = None
        self.mqtt_client = None
        self.loop = None

    def on_mqtt_connect(self, client, userdata, flags, rc):
        debug_log(f"Connected to MQTT broker with result code: {rc}")
        client.subscribe([
            (VOLTAGE_TOPIC, 0), (FREQUENCY_TOPIC, 0), (TEMPERATURE_TOPIC, 0),
            (POWER_FACTOR_TOPIC, 0), (CURRENT_TOPIC, 0), (POWER_TOPIC, 0),
            (CURRENT_OFFERED_TOPIC, 0), (ENERGY_ACTIVE_IMPORT_TOPIC, 0), (STATUS_TOPIC, 0)
        ])
        debug_log("Subscribed to topics: " + ", ".join([
            VOLTAGE_TOPIC, FREQUENCY_TOPIC, TEMPERATURE_TOPIC, POWER_FACTOR_TOPIC, CURRENT_TOPIC, POWER_TOPIC, CURRENT_OFFERED_TOPIC, ENERGY_ACTIVE_IMPORT_TOPIC, STATUS_TOPIC
        ]))

    def on_mqtt_message(self, client, userdata, msg):
        if not self.cp:
            print("[WARNING] OCPP client is not yet initialized. MQTT message ignored.")
            return

        try:
            if msg.topic == VOLTAGE_TOPIC:
                self.cp.current_voltage = float(msg.payload.decode())
                debug_log(f"MQTT received voltage: {self.cp.current_voltage}")
            elif msg.topic == FREQUENCY_TOPIC:
                self.cp.current_frequency = float(msg.payload.decode())
                debug_log(f"MQTT received frequency: {self.cp.current_frequency}")
            elif msg.topic == TEMPERATURE_TOPIC:
                self.cp.current_temperature = float(msg.payload.decode())
                debug_log(f"MQTT received temperature: {self.cp.current_temperature}")
            elif msg.topic == POWER_FACTOR_TOPIC:
                self.cp.current_power_factor = float(msg.payload.decode())
                debug_log(f"MQTT received power factor: {self.cp.current_power_factor}")
            elif msg.topic == CURRENT_TOPIC:
                self.cp.current_import = float(msg.payload.decode())
                debug_log(f"MQTT received current import: {self.cp.current_import}")
            elif msg.topic == POWER_TOPIC:
                self.cp.power_active_import = float(msg.payload.decode())
                debug_log(f"MQTT received power active import: {self.cp.power_active_import}")
            elif msg.topic == CURRENT_OFFERED_TOPIC:
                self.cp.current_offered = float(msg.payload.decode())
                debug_log(f"MQTT received current offered: {self.cp.current_offered}")
            elif msg.topic == ENERGY_ACTIVE_IMPORT_TOPIC:
                self.cp.energy_active_import_register = float(msg.payload.decode())
                debug_log(f"MQTT received energy active import register: {self.cp.energy_active_import_register}")
            elif msg.topic == STATUS_TOPIC:
                status = msg.payload.decode()
                debug_log(f"MQTT received status: {status}")
                asyncio.run_coroutine_threadsafe(self.cp.send_status_notification(status), self.loop)

            asyncio.run_coroutine_threadsafe(self.cp.send_meter_values(), self.loop)

        except ValueError as e:
            print(f"[ERROR] Invalid value received on topic {msg.topic}: {e}")

    def setup_mqtt(self):
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(args.mqtt_user, args.mqtt_pass)
        self.mqtt_client.on_connect = self.on_mqtt_connect
        self.mqtt_client.on_message = self.on_mqtt_message

        try:
            self.mqtt_client.connect(args.mqtt_address, args.mqtt_port, 60)
            self.mqtt_client.loop_start()
            debug_log("MQTT client started")
        except Exception as e:
            print(f"[ERROR] MQTT connection failed: {e}")
            raise

async def main():
    manager = EVSEManager()
    manager.loop = asyncio.get_running_loop()
    manager.setup_mqtt()

    server_url = f"ws://{args.ws_address}:{args.ws_port}"

    while True:
        try:
            async with websockets.connect(
                server_url,
                subprotocols=['ocpp1.6'],
                ping_interval=30,
                ping_timeout=10
            ) as ws:
                debug_log("Connected to OCPP server")
                manager.cp = EVSEClient(args.chargepoint_id, ws)

                await manager.cp.start()

                if await manager.cp.send_boot_notification():
                    debug_log("Boot notification accepted")
                    await asyncio.Future()
                else:
                    print("[ERROR] Boot notification rejected")
                    
        except (websockets.exceptions.WebSocketException, ConnectionError) as e:
            print(f"[ERROR] WebSocket connection failed: {e}")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"[ERROR] Unexpected error: {e}")
            await asyncio.sleep(5)

def run():
    asyncio.run(main())

if __name__ == "__main__":
    if args.daemon:
        with daemon.DaemonContext(
            stdout=sys.stdout,
            stderr=sys.stderr
        ):
            run()
    else:
        run()

