# JuicepassProxy MQTT to OCPP Client

This project is an Proof of Concept  client that connects to an Open Charge Point Protocol (OCPP) server and integrates with an MQTT broker to monitor  charging parameters. This application listens to various MQTT topics for EV charging information (e.g., voltage, frequency, power, status) and sends these values to an OCPP server, as well as receiving configuration and status requests from the server. This application has ONLY BEEN TESTED WITH THE OCPP Home Assistant addon.  It only monitors values and does not support control at this time. 



## Features

- **OCPP 1.6 Support**: Integrates with OCPP servers to send meter values and handle configuration requests.
- **MQTT Integration**: Subscribes to MQTT topics for real-time updates on EV charging parameters.
- **Configurable Arguments**: Customizable broker, server, and client settings via command-line arguments.
- **Debug and Daemon Modes**: Supports verbose debug logging and can run as a background daemon.

## Installation

This project requires `Python 3.7+` and the following libraries:
- `paho-mqtt`
- `websockets`
- `ocpp`
- `python-daemon` (for daemon mode)

To install dependencies:
```bash
pip install paho-mqtt websockets ocpp python-daemon
```
For many distributions, Python venv now needs to be used as pip installs a few libraries. 

## Home Assistant
This has only been tested with the OCPP HA Addon/Integration.  If you want to test the same way,  you install the OCPP Addon, and within the integration when you add a new instance set the Chargepoint ID to "juicepassproxy" . 
Unselect " Automatic detection of OCPP Measurands"   
Max Charging Current to your value   
Select "Skip OCPP schema validation"   

On the next screen select the follwing options:
* Current.Import: Instantaneous current flow to EV
* Current.Offered: Maximum current offered to EV
* Energy.Active.Import.Register: Active energy imported from the grid
* Energy.Active.Import.Interval: Active energy imported from the grid during last interval
* Frequency: Powerline frequency
* Power.Active.Import: Instantaneous active power imported by EV
* Power.Factor: Instantaneous power factor of total energy flow
* Temperature: Temperature reading inside Charge Point
* Voltage: Instantaneous AC RMS supply voltage



## Usage
The application can be executed from the command line with the following options:
``` python ocpp_client.py [OPTIONS]
```

## Command-Line Arguments

| Argument            | Type    | Description                                                                                       | Default Value       |
|---------------------|---------|---------------------------------------------------------------------------------------------------|---------------------|
| `--mqtt_address`    | string  | MQTT broker address or hostname.                                                                  | `127.0.0.1`        |
| `--mqtt_port`       | int     | Port for MQTT broker.                                                                             | `1883`             |
| `--mqtt_user`       | string  | Username for MQTT broker authentication (leave blank if no authentication is required).           | `""`               |
| `--mqtt_pass`       | string  | Password for MQTT broker authentication.                                                          | `""`               |
| `--ws_address`      | string  | WebSocket IP address or hostname for the OCPP server.                                             | `0.0.0.0`          |
| `--ws_port`         | int     | Port for the WebSocket server.                                                                    | `9000`             |
| `--chargepoint_id`  | string  | Charge Point ID used to identify this EVSE to the OCPP server.                                    | `juicepassproxy`   |
| `--debug`           | flag    | Enable debug mode, providing verbose logging for development and troubleshooting.                 | `False`            |
| `--daemon`          | flag    | Run the application in the background as a daemon. Requires `python-daemon` library.              | `False`            |




## Example Usage

```
python jpp_ocpp_client.py --debug
```
Run the application as a daemon:
```
python jpp_ocpp_client.py --daemon
```

## Configuration
For quick configuration, you can pass arguments directly on the command line. Alternatively, modify the default values in the code if you prefer hardcoded values or require fixed settings.

## MQTT Topics   
This application listens to the following MQTT topics for EV charging data:

* Voltage: hmd/sensor/JuiceBox/Voltage/state
* Frequency: hmd/sensor/JuiceBox/Frequency/state
* Temperature: hmd/sensor/JuiceBox/Temperature/state
* Power Factor: hmd/sensor/JuiceBox/Power-Factor/state
* Current: hmd/sensor/JuiceBox/Current/state
* Power: hmd/sensor/JuiceBox/Power/state
* Current Offered: hmd/sensor/JuiceBox/Max-Current-Online-Device-/state
* Energy Active Import Register: hmd/sensor/JuiceBox/Energy--Session-/state
* Status: hmd/sensor/JuiceBox/Status/state (e.g., Charging, Available, etc.)

These values are sent to the OCPP server in real-time as part of the MeterValues or StatusNotification calls.

## Debug Mode
Use the --debug flag to enable verbose debug logging. This mode will log each MQTT topic message, connections to the MQTT broker and OCPP server, and responses from the server.


## Daemon Mode
Use the --daemon flag to run the application in the background as a system daemon. Daemon mode allows the application to continue running after logging out or closing the terminal. Note: The python-daemon library must be installed for this feature.



## Info, TODO, and Bugs   
Currently can only monitor several values that are in MQTT from JuicepassProxy.   
For some reason, Charging Session Energy values do not popualte in HA, but are processesed by the application.   
Maybe add ability to control.   
Include in to JPP appliance builds to create a bridge to OCPP services.    



