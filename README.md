# SUMO-RL Traffic Sensor Simulator

**Version 1.0 | 2026**

Python-based intersection sensor simulator that integrates with SUMO via TraCI. Auto-discovers all junctions in a user-supplied `.net.xml` network, attaches one sensor per junction, collects raw traffic data at 1-second intervals, and publishes to an MQTT broker while printing to stdout.

## Features

- **Auto-discovery**: Automatically discovers all junctions in SUMO network
- **Manual configuration**: Configure specific sensors with custom parameters
- **Comprehensive data collection**:
    - Vehicle metrics (speed, position, waiting time, acceleration)
    - Lane-level details (occupancy, queue length, average speed)
    - Road metrics (capacity, occupancy rate, congestion level)
    - Traffic light states and phases
    - Flow metrics (vehicles entering/exiting)
- **Dual output**: Publishes to Highway Broker (MQTT) + stdout
- **Flexible configuration**: JSON-based configuration
- **Error handling**: Graceful error handling with logging

## Prerequisites

- **Python 3.10+**
- **SUMO 1.19+** with TraCI support
- **Highway Broker** running (MQTT-like message broker)

## Installation

### 1. Install SUMO

Follow the [official SUMO installation guide](https://sumo.dlr.de/docs/Installing/index.html) for your platform.

Make sure `SUMO_HOME` environment variable is set:

```bash
export SUMO_HOME=/usr/share/sumo  # Adjust path as needed
export PATH=$SUMO_HOME/bin:$PATH
```

Verify installation:

```bash
sumo --version
```

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

Or using a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Prepare SUMO Network

The network file (`osm.net.xml`) has already been decompressed from `osm.net.xml.gz` in the `assets/2026-02-24-23-58-01/` directory.

If you have a new `.net.xml.gz` file, decompress it:

```bash
gunzip -k assets/2026-02-24-23-58-01/osm.net.xml.gz
```

## Configuration

### Auto-Discovery Mode (Recommended)

Automatically creates sensors for all junctions in the network:

```json
{
    "sumo": {
        "binary": "sumo",
        "config_file": "./assets/2026-02-24-23-58-01/osm.sumocfg",
        "mode": "launch",
        "port": 8813
    },
    "broker": {
        "host": "localhost",
        "port": 1883,
        "client_id": "sumo-sensor-01",
        "topic_pattern": "sumo/sensor/{id}/data",
        "keepalive": 60
    },
    "auto_discover_junctions": true,
    "sensors": []
}
```

### Manual Configuration Mode

Manually specify which junctions to monitor:

```json
{
    "sumo": {
        "binary": "sumo",
        "config_file": "./assets/2026-02-24-23-58-01/osm.sumocfg",
        "mode": "launch",
        "port": 8813
    },
    "broker": {
        "host": "localhost",
        "port": 1883,
        "client_id": "sumo-sensor-manual",
        "topic_pattern": "sumo/sensor/{id}/data",
        "keepalive": 60
    },
    "auto_discover_junctions": false,
    "sensors": [
        {
            "sensorId": "junction_1",
            "intersectionType": "4-way-intersection",
            "detectionRadius": 80.0,
            "publishInterval": 1.0,
            "enableRawData": true,
            "enableMetrics": true
        }
    ]
}
```

### Custom Position Mode

Create sensors at custom x,y positions (useful for monitoring specific road segments or areas):

```json
{
    "sumo": {
        "binary": "sumo-gui",
        "config_file": "./assets/2026-02-24-23-58-01/osm.sumocfg",
        "mode": "launch",
        "port": 8813
    },
    "broker": {
        "host": "localhost",
        "port": 1883,
        "client_id": "sumo-sensor-custom",
        "topic_pattern": "sumo/sensor/{id}/data",
        "keepalive": 60
    },
    "auto_discover_junctions": false,
    "enable_visualization": true,
    "sensors": [
        {
            "sensorId": "custom_sensor_1",
            "intersectionType": "custom",
            "detectionRadius": 100.0,
            "publishInterval": 1.0,
            "position": {
                "x": 3500.0,
                "y": 4000.0
            },
            "enableRawData": true,
            "enableMetrics": true
        }
    ]
}
```

**Important:** When using custom positions:
- The `sensorId` can be any unique string (doesn't need to match a junction ID)
- The `position` object with `x` and `y` coordinates is **required**
- The sensor will collect data from all vehicles within the detection radius
- No road/edge data will be collected (only vehicles and aggregate metrics)
- Perfect for monitoring highway segments, parking lots, or custom areas

### Configuration Fields

#### SUMO Configuration

| Field         | Type   | Required | Description                         |
| ------------- | ------ | -------- | ----------------------------------- |
| `binary`      | string | yes      | Path to `sumo` or `sumo-gui` binary |
| `config_file` | string | yes      | Path to `.sumocfg` file             |
| `mode`        | string | yes      | `launch` or `attach`                |
| `port`        | int    | no       | TraCI port (default: 8813)          |

#### Broker Configuration

| Field           | Type   | Required | Description                                     |
| --------------- | ------ | -------- | ----------------------------------------------- |
| `host`          | string | yes      | Highway Broker hostname                         |
| `port`          | int    | no       | Broker port (default: 1883)                     |
| `client_id`     | string | no       | Client ID (default: auto-generated)             |
| `topic_pattern` | string | no       | Topic template (default: sumo/sensor/{id}/data) |
| `keepalive`     | int    | no       | Keepalive interval (default: 60)                |

#### Sensor Configuration (Manual Mode)

| Field              | Type    | Required | Description                                                                                                                          |
| ------------------ | ------- | -------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `sensorId`         | string  | yes      | Junction ID from SUMO network OR any unique string for custom positions                                                             |
| `intersectionType` | string  | yes      | One of: `4-way-intersection`, `t-junction`, `roundabout`, `y-junction`, `traffic-circle`, `custom`                                   |
| `detectionRadius`  | float   | no       | Detection radius in meters (default: 80.0)                                                                                           |
| `publishInterval`  | float   | no       | Publish interval in seconds (default: 1.0)                                                                                           |
| `position`         | object  | no\*     | Custom position: `{x: float, y: float}`. **Required** if sensorId doesn't match a junction. Optional to override junction position. |
| `enableRawData`    | boolean | no       | Publish to MQTT (default: true)                                                                                                      |
| `enableMetrics`    | boolean | no       | Include metrics (default: true)                                                                                                      |

\* `position` is required if the `sensorId` doesn't match any junction in the network.

#### Root Configuration Options

| Field                       | Type    | Required | Description                                                                          |
| --------------------------- | ------- | -------- | ------------------------------------------------------------------------------------ |
| `auto_discover_junctions`   | boolean | no       | If `true`, automatically create sensors for all junctions (default: false)           |
| `enable_visualization`      | boolean | no       | If `true`, draw sensor detection zones in SUMO GUI (default: true)                   |

## Usage

### Basic Usage

```bash
# Copy example config
cp config.example.json config.json

# Edit config.json with your settings

# Run with auto-discovery (launches SUMO)
python -m sumo_sensor --config config.json
```

### Using SUMO GUI

Edit your config to use `sumo-gui` instead of `sumo`:

```json
{
  "sumo": {
    "binary": "sumo-gui",
    ...
  }
}
```

### Attach to Running SUMO

If SUMO is already running with TraCI enabled:

```json
{
  "sumo": {
    "mode": "attach",
    "port": 8813,
    ...
  }
}
```

### Change Log Level

```bash
python -m sumo_sensor --config config.json --log-level DEBUG
```

Available levels: `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

## Output

### Stdout

Sensor data is printed to stdout in pretty JSON format:

```
================================================================================
Sensor: junction_123
================================================================================
{
  "sensorId": "junction_123",
  "sensorType": "4-way-intersection",
  "timestamp": "2026-03-17T12:34:56Z",
  "geometry": {
    "position": {"x": 100.0, "y": 200.0},
    "detection_radius": 80.0,
    "intersection_type": "4-way-intersection"
  },
  "roads": [...],
  "intersectionMetrics": {
    "totalVehicles": 15,
    "totalQueueLength": 3,
    "avgSpeedAll": 45.2,
    "globalCongestionLevel": 0.35
  }
}
================================================================================
```

### MQTT (Highway Broker)

Data is published to topics following the pattern: `sumo/sensor/{junction_id}/data`

Example topic: `sumo/sensor/junction_123/data`

Payload: Compact JSON (same structure as stdout but minified)

QoS: 0 (at most once)

### Logs

Logs are written to `logs/sensor.log` with format:

```
2026-03-17T12:34:56 | INFO     | Connected to SUMO
2026-03-17T12:34:57 | INFO     | [Junction junction_123] Published data: vehicles=15, queue=3
```

## Data Model

The simulator publishes `RawSensorData` objects with the following structure:

- **sensorId**: Junction ID
- **sensorType**: Intersection type
- **timestamp**: ISO 8601 timestamp
- **geometry**: Position, detection radius, intersection type
- **roads**: Array of road objects, one per incoming edge
    - **roadMetrics**: Speed, occupancy, capacity, congestion
    - **queueMetrics**: Queue length, saturation
    - **flowMetrics**: Vehicle counts, flow rate
    - **laneDetails**: Per-lane breakdown
    - **trafficLight**: Traffic light state and phases
    - **vehicles**: Array of vehicles on this road
- **intersectionMetrics**: Aggregated statistics

See `REQUIREMENT.md` for complete data model specification.

## Troubleshooting

### "Failed to connect to SUMO"

- Check that SUMO is installed and in PATH
- Verify `sumo.binary` path in config
- Ensure `sumo.config_file` exists
- Check that port 8813 is not already in use

### "Network file not found"

- Ensure `osm.net.xml` exists (decompress from `.gz` if needed)
- Check that the path in `osm.sumocfg` points to the network file

### "Could not connect to broker"

- Verify Highway Broker is running on specified host:port
- Check firewall settings
- The simulator will continue and print to stdout even without broker

### "No sensors configured"

- In auto-discovery mode: check that the network has junctions
- In manual mode: ensure `sensors` array is not empty and junction IDs match the network

### "Invalid junction IDs"

- Check that `sensorId` values match junction IDs in the `.net.xml` file
- Use auto-discovery mode to see all available junction IDs

## Project Structure

```
.
├── assets/
│   └── 2026-02-24-23-58-01/        # SUMO network snapshot
│       ├── osm.net.xml              # Road network (decompressed)
│       ├── osm.sumocfg              # SUMO simulation config
│       └── ...
├── libs/
│   └── rnneb_client.py              # Highway Broker client
├── sumo_sensor/                     # Main Python package
│   ├── __init__.py
│   ├── __main__.py                  # Entry point
│   ├── config.py                    # Config loading
│   ├── runner.py                    # Simulation loop
│   ├── sensor.py                    # Sensor class
│   ├── collector.py                 # TraCI data collection
│   ├── publisher.py                 # Publishing logic
│   ├── models.py                    # Data models
│   └── utils/
│       ├── net_parser.py            # Network file parsing
│       └── logger.py                # Logging utilities
├── logs/                            # Log files (created at runtime)
├── config.example.json              # Example config (auto-discovery)
├── config.manual.example.json       # Example config (manual)
├── requirements.txt                 # Python dependencies
├── README.md                        # This file
└── REQUIREMENT.md                   # Complete specification
```

## Development

### Adding New Intersection Types

1. Add enum value to `IntersectionType` in `models.py`
2. Update mapping in `utils/net_parser.py` → `map_junction_type_to_intersection_type()`
3. Update documentation

### Extending Data Collection

Modify `collector.py` → `DataCollector.collect()` to add new metrics.

## License

See project repository for license information.

## Support

For issues, questions, or contributions, please refer to the project repository.

---

**Built with** ❤️ **for traffic simulation and reinforcement learning research**
