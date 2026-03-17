# SUMO-RL Traffic Sensor Simulator

## Product Requirements Document

**Version 1.0 | 2026**

---

## 1. Overview

Python-based intersection sensor simulator that integrates with SUMO via TraCI. Auto-discovers all junctions in a user-supplied `.net.xml` network, attaches one sensor per junction, collects raw traffic data at 1-second intervals, and publishes to an MQTT broker while printing to stdout.

| Field              | Value                                 |
| ------------------ | ------------------------------------- |
| Project name       | sumo-rl-sensor                        |
| Version            | v1.0                                  |
| Target env         | Local machine, Python 3.10+           |
| SUMO version       | 1.19+ (TraCI API)                     |
| Intersection types | 4-way, T-junction, Roundabout, Custom |
| Output             | stdout + Highway Broker (QoS 0)       |
| Config format      | JSON                                  |

---

## 2. Goals and Non-Goals

### 2.1 Goals

- Simulate realistic per-junction sensor readings from any user-supplied SUMO network
- Collect full vehicle, lane, road, queue, flow, and traffic-light state per junction per tick
- Publish raw `RawSensorData` as JSON to Highway Broker, topic pattern configurable
- Print sensor snapshots to stdout for dev/debug
- Handle errors gracefully: skip bad steps, log to file, keep running
- Ship with a README covering installation, config, and usage

### 2.2 Non-Goals (v1)

- RL state preprocessing (`RLState`) — handled by the downstream RL agent
- Consuming RL actions back from the broker (`HighwayClient.subscribe()` unused in v1)
- Remote TraCI connections
- Unit tests
- Docker containerization

---

## 3. System Architecture

The simulator is a Python package. The entry point loads config, connects to SUMO (either launching it or attaching to a running instance), discovers all junctions, spawns one `Sensor` per junction, and runs the main simulation loop.

### 3.1 Project Structure

```
.
├── assets/
│   └── 2026-02-24-23-58-01/        # SUMO network snapshot
├── libs/
│   └── rnneb_client.py              # Highway Broker client (HighwayClient)
├── sumo_sensor/                     # main Python package
│   ├── __init__.py
│   ├── __main__.py                  # entry point: python -m sumo_sensor
│   ├── config.py                    # JSON config loader + dataclasses
│   ├── runner.py                    # simulation loop, TraCI lifecycle
│   ├── sensor.py                    # Sensor class, one per junction
│   ├── collector.py                 # TraCI data collection helpers
│   ├── publisher.py                 # HighwayClient + stdout publisher
│   ├── models.py                    # Python equivalents of TS types
│   └── utils/
│       ├── net_parser.py            # .net.xml junction auto-discovery
│       └── logger.py                # file + stream logging
├── config.example.json
├── libs/
├── README.md
└── REQUIREMENT.md
```

> `osm.net.xml.gz` must be decompressed to `osm.net.xml` before the simulator runs. `net_parser.py` reads the uncompressed file directly.

---

## 4. Configuration Schema (`config.json`)

All runtime behaviour is controlled by a single JSON file passed to the simulator.

### 4.1 Top-level fields

| Field                  | Type             | Required | Description                                                |
| ---------------------- | ---------------- | -------- | ---------------------------------------------------------- |
| `sumo.binary`          | string           | yes      | Path to `sumo` or `sumo-gui` binary                        |
| `sumo.config_file`     | string           | yes      | Path to `.sumocfg` file                                    |
| `sumo.mode`            | string           | yes      | `launch` \| `attach`                                       |
| `sumo.port`            | integer          | no       | TraCI port (default: 8813)                                 |
| `broker.host`          | string           | yes      | Highway Broker hostname                                    |
| `broker.port`          | integer          | yes      | Highway Broker port (default: 1883)                        |
| `broker.client_id`     | string           | no       | Client ID sent in CONNECT packet (default: auto-generated) |
| `broker.topic_pattern` | string           | yes      | Topic template, e.g. `sumo/sensor/{id}/data`               |
| `broker.keepalive`     | integer          | no       | Keepalive interval in seconds (default: 60)                |
| `sensors`              | `SensorConfig[]` | yes      | List of sensor definitions, one per junction               |

### 4.2 `SensorConfig` object (one entry in `sensors`)

| Field              | Type               | Required | Description                                                |
| ------------------ | ------------------ | -------- | ---------------------------------------------------------- |
| `sensorId`         | string             | yes      | Unique sensor ID, must match SUMO junction ID              |
| `intersectionType` | `IntersectionType` | yes      | Intersection type enum string value                        |
| `detectionRadius`  | float              | no       | Detection radius in metres (default: 80)                   |
| `publishInterval`  | float              | no       | Seconds between publishes (default: 1.0)                   |
| `position`         | `{x, y}`           | no       | Override junction coordinates                              |
| `enableRawData`    | boolean            | no       | Publish `RawSensorData` to MQTT (default: `true`)          |
| `enableMetrics`    | boolean            | no       | Include `intersectionMetrics` in payload (default: `true`) |

Each sensor in the list runs independently with its own `detectionRadius` and `publishInterval`. Fields omitted in a sensor entry fall back to the defaults above.

### 4.3 Example `config.json`

```json
{
    "sumo": {
        "binary": "/usr/bin/sumo",
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
    "sensors": [
        {
            "sensorId": "J1",
            "intersectionType": "4-way-intersection",
            "detectionRadius": 80.0,
            "publishInterval": 1.0,
            "position": { "x": 100.0, "y": 200.0 },
            "enableRawData": true,
            "enableMetrics": true
        },
        {
            "sensorId": "J2",
            "intersectionType": "t-junction",
            "detectionRadius": 60.0,
            "publishInterval": 1.0,
            "position": { "x": 350.0, "y": 200.0 }
        },
        {
            "sensorId": "J3",
            "intersectionType": "roundabout",
            "detectionRadius": 120.0,
            "publishInterval": 2.0,
            "position": { "x": 600.0, "y": 200.0 }
        }
    ]
}
```

Junction IDs in `sensors[].sensorId` must match junction IDs present in the `.net.xml` file. At startup, the simulator validates each `sensorId` against the parsed network and skips any entry that does not resolve to a known junction, logging a warning.

---

## 5. Component Specifications

### 5.1 `net_parser.py` — Junction Discovery

Parses the `.net.xml` file specified in `sumo.config_file`. Extracts all `<junction>` elements with `type != internal`. Returns a list of `JunctionInfo(id, x, y, type, incoming_edges)`.

### 5.2 `runner.py` — Simulation Loop

- If `mode = launch`: spawns SUMO subprocess with `--remote-port`, waits for TraCI connection
- If `mode = attach`: connects directly to `sumo.port`
- Instantiates one `Sensor` per discovered junction
- Main loop: advances one SUMO step per tick, checks elapsed wall-clock time, triggers each sensor at `publish_interval`
- Runs until SUMO simulation ends (`traci.simulation.getMinExpectedNumber() == 0`) or `KeyboardInterrupt`
- On exit: disconnects TraCI, disconnects `HighwayClient`, flushes log

### 5.3 `sensor.py` — Per-Junction Sensor

Each `Sensor` instance is responsible for one junction. On each trigger it calls `collector.collect(junction_id)` to build a `RawSensorData` snapshot, then hands it to `publisher.publish()`.

### 5.4 `collector.py` — TraCI Data Collection

Implements `collect(junction_id, config) -> RawSensorData`. Key responsibilities:

- Resolve incoming edge IDs for the junction from the parsed network
- For each incoming edge: collect road metrics, queue metrics, flow metrics, lane details, traffic light state, and vehicles within `detection_radius`
- Determine intersection type from junction `type` attribute in `.net.xml`
- Compute `IntersectionMetrics` aggregates across all roads
- Vehicle fields collected per vehicle: `speed`, `position`, `waitingTime`, `wasteTime`, `acceleration`, `vehicleType`, `distanceToStop`

### 5.5 `publisher.py` — Output

Wraps a single shared `HighwayClient` instance imported from `libs/rnneb_client.py` and exposes a `publish(sensor_id, data)` method used by all sensors.

- **stdout**: pretty-printed JSON snapshot per sensor per interval
- **Highway Broker**: serialised `RawSensorData` as compact JSON (`data.encode('utf-8')`), published via `HighwayClient.publish(topic, data, qos=QoS.AT_MOST_ONCE)` to `topic_pattern` with `{id}` replaced by `sensorId`
- `HighwayClient` is instantiated once at startup with `auto_connect=True`; the `on_connect` event is awaited before the simulation loop starts
- On broker disconnect mid-run: log warning, continue printing to stdout

### 5.6 `logger.py` — Error Logging

- All errors during `collect()` are caught, logged to file (`logs/sensor.log`), and the step is skipped
- Log format: `ISO timestamp | level | junction_id | message`
- Log file path configurable; defaults to `logs/sensor.log` relative to working directory

---

## 6. Data Model

`models.py` mirrors the TypeScript type definitions exactly. All field names, nesting, and enum values match the TS types to ensure JSON payloads are interoperable with any downstream consumer.

---

### 6.1 Enums

#### `TrafficLightColor`

| Value    | String |
| -------- | ------ |
| `GREEN`  | `"g"`  |
| `YELLOW` | `"y"`  |
| `RED`    | `"r"`  |

#### `VehicleType`

| Value        | String         |
| ------------ | -------------- |
| `CAR`        | `"car"`        |
| `TRUCK`      | `"truck"`      |
| `BUS`        | `"bus"`        |
| `MOTORCYCLE` | `"motorcycle"` |
| `BICYCLE`    | `"bicycle"`    |

#### `IntersectionType`

| Value            | String                 |
| ---------------- | ---------------------- |
| `FOUR_WAY`       | `"4-way-intersection"` |
| `ROUNDABOUT`     | `"roundabout"`         |
| `T_JUNCTION`     | `"t-junction"`         |
| `Y_JUNCTION`     | `"y-junction"`         |
| `TRAFFIC_CIRCLE` | `"traffic-circle"`     |
| `CUSTOM`         | `"custom"`             |

#### `RoadDirection`

| Value       | String        |
| ----------- | ------------- |
| `NORTH`     | `"north"`     |
| `SOUTH`     | `"south"`     |
| `EAST`      | `"east"`      |
| `WEST`      | `"west"`      |
| `NORTHEAST` | `"northeast"` |
| `NORTHWEST` | `"northwest"` |
| `SOUTHEAST` | `"southeast"` |
| `SOUTHWEST` | `"southwest"` |
| `CUSTOM`    | `"custom"`    |

#### `CongestionLevel`

| Value       | String        | Occupancy threshold |
| ----------- | ------------- | ------------------- |
| `FREE`      | `"free"`      | < 20%               |
| `LIGHT`     | `"light"`     | 20–40%              |
| `MODERATE`  | `"moderate"`  | 40–60%              |
| `HEAVY`     | `"heavy"`     | 60–80%              |
| `CONGESTED` | `"congested"` | > 80%               |

---

### 6.2 Top-level: `RawSensorData`

The root object published to MQTT and printed to stdout on every interval.

| Field                 | Type                   | Description                                 |
| --------------------- | ---------------------- | ------------------------------------------- |
| `sensorId`            | `string`               | Unique sensor ID, matches SUMO junction ID  |
| `sensorType`          | `IntersectionType`     | Intersection type enum value                |
| `timestamp`           | `string`               | ISO 8601 timestamp of the snapshot          |
| `geometry`            | `IntersectionGeometry` | Physical placement and detection config     |
| `roads`               | `Road[]`               | One entry per incoming edge of the junction |
| `intersectionMetrics` | `IntersectionMetrics`  | Aggregated stats across all roads           |

#### `IntersectionGeometry`

| Field               | Type               | Description                          |
| ------------------- | ------------------ | ------------------------------------ |
| `position`          | `Position`         | `{x, y}` coordinates of the junction |
| `detection_radius`  | `float`            | Detection radius in metres           |
| `intersection_type` | `IntersectionType` | Same as `RawSensorData.sensorType`   |
| `radius`            | `float?`           | Only set for roundabouts             |

#### `Position`

| Field | Type    | Description                                     |
| ----- | ------- | ----------------------------------------------- |
| `x`   | `float` | X coordinate (longitude or SUMO net coordinate) |
| `y`   | `float` | Y coordinate (latitude or SUMO net coordinate)  |

#### `IntersectionMetrics`

| Field                   | Type      | Description                                       |
| ----------------------- | --------- | ------------------------------------------------- |
| `totalVehicles`         | `int`     | Total vehicles detected across all roads          |
| `totalQueueLength`      | `int`     | Sum of queue lengths across all roads             |
| `avgSpeedAll`           | `float`   | Average speed across all detected vehicles (km/h) |
| `globalCongestionLevel` | `float`   | Weighted congestion 0–1 across all roads          |
| `bottleneckRoad`        | `string?` | Road ID with highest saturation ratio             |
| `criticalTrafficLight`  | `string?` | TL ID with longest average waiting time           |
| `trafficLightCount`     | `int`     | Number of traffic lights at this junction         |

---

### 6.3 `Road`

One `Road` object per incoming edge detected at the junction.

| Field            | Type               | Description                                            |
| ---------------- | ------------------ | ------------------------------------------------------ |
| `roadId`         | `string`           | SUMO edge ID                                           |
| `direction`      | `RoadDirection`    | Cardinal or diagonal direction of this road            |
| `incomingEdgeId` | `string`           | SUMO incoming edge ID (same as `roadId` in most cases) |
| `lanes`          | `int`              | Number of lanes on this edge                           |
| `roadMetrics`    | `RoadMetrics`      | Speed, occupancy, capacity metrics                     |
| `queueMetrics`   | `QueueMetrics`     | Queue length and saturation metrics                    |
| `flowMetrics`    | `FlowMetrics`      | Vehicle counts and flow rate metrics                   |
| `laneDetails`    | `Lane[]`           | Per-lane breakdown                                     |
| `trafficLight`   | `TrafficLightData` | Full TL object, a ref, or `null`                       |
| `vehicles`       | `Vehicle[]`        | All vehicles on this road within `detection_radius`    |

#### `RoadMetrics`

| Field             | Type               | Description                                  |
| ----------------- | ------------------ | -------------------------------------------- |
| `length`          | `float`            | Edge length in metres                        |
| `speedLimit`      | `float`            | Posted speed limit (km/h)                    |
| `freeFlowSpeed`   | `float`            | Observed maximum speed (km/h)                |
| `capacity`        | `int`              | Theoretical capacity (vehicles/hour)         |
| `occupancyRate`   | `float`            | Current occupancy 0–1                        |
| `avgSpeed`        | `float`            | Average speed of all vehicles on road (km/h) |
| `minSpeed`        | `float`            | Minimum observed speed (km/h)                |
| `maxSpeed`        | `float`            | Maximum observed speed (km/h)                |
| `congestionLevel` | `CongestionLevel?` | Derived from `occupancyRate` thresholds      |
| `speedTrend`      | `float?`           | Change in avg speed per second (km/h/s)      |

#### `QueueMetrics`

| Field                    | Type    | Description                                             |
| ------------------------ | ------- | ------------------------------------------------------- |
| `queueLength`            | `int`   | Current number of queued vehicles                       |
| `maxQueueLengthObserved` | `int`   | Maximum queue seen in this session                      |
| `queueTrend`             | `float` | Vehicles/sec joining the queue (negative = dissipating) |
| `saturationRatio`        | `float` | `queueLength / capacity` 0–1                            |

#### `FlowMetrics`

| Field                   | Type    | Description                                     |
| ----------------------- | ------- | ----------------------------------------------- |
| `vehicleCount`          | `int`   | Vehicles currently on the road                  |
| `vehiclesExited`        | `int`   | Vehicles that left in the last sample window    |
| `vehiclesEntered`       | `int`   | Vehicles that entered in the last sample window |
| `flowRate`              | `float` | Vehicles/hour                                   |
| `utilizationRate`       | `float` | `flowRate / capacity` 0–1                       |
| `timeLastVehiclePassed` | `float` | Seconds since last vehicle passed the stop line |

---

### 6.4 `Lane`

Per-lane breakdown within a road.

| Field          | Type     | Description                               |
| -------------- | -------- | ----------------------------------------- |
| `laneId`       | `string` | SUMO lane ID (e.g. `edge_0`, `edge_1`)    |
| `vehicleCount` | `int`    | Vehicles currently on this lane           |
| `avgSpeed`     | `float`  | Average vehicle speed on this lane (km/h) |
| `occupancy`    | `float`  | Lane occupancy 0–1                        |
| `queueLength`  | `int`    | Queued vehicles on this lane              |

---

### 6.5 Traffic Light Types

#### `TrafficLightData` (union)

Either a full `TrafficLight` object, a `TrafficLightRef`, or `null` (uncontrolled road).

```
TrafficLightData = TrafficLight | TrafficLightRef | null
```

`TrafficLightRef` is used when multiple roads share the same physical signal (e.g. north and south run the same phase). Only the primary road carries the full object; others carry `{ "ref": "<tl_id>" }`.

#### `TrafficLight`

| Field             | Type                      | Description                    |
| ----------------- | ------------------------- | ------------------------------ |
| `trafficLightId`  | `string`                  | SUMO TL program ID             |
| `controlledRoads` | `string[]`                | Edge IDs controlled by this TL |
| `signal`          | `TrafficLightSignal`      | Current signal state           |
| `phaseProgram`    | `TrafficLightProgram`     | Full phase program             |
| `cycle`           | `TrafficLightCycle`       | Current position in the cycle  |
| `performance`     | `TrafficLightPerformance` | Clearance and waiting stats    |

#### `TrafficLightSignal`

| Field                 | Type                | Description                          |
| --------------------- | ------------------- | ------------------------------------ |
| `currentColor`        | `TrafficLightColor` | Current signal colour                |
| `timeInCurrentPhase`  | `float`             | Seconds elapsed in the current phase |
| `timeUntilNextSwitch` | `float`             | Seconds until next phase transition  |

#### `TrafficLightProgram`

| Field               | Type                  | Description                           |
| ------------------- | --------------------- | ------------------------------------- |
| `currentPhaseIndex` | `int`                 | Index of the active phase             |
| `totalPhases`       | `int`                 | Total number of phases in the program |
| `phases`            | `TrafficLightPhase[]` | Full phase list                       |

#### `TrafficLightPhase`

| Field         | Type     | Description                                   |
| ------------- | -------- | --------------------------------------------- |
| `index`       | `int`    | Phase index                                   |
| `name`        | `string` | Human-readable phase name (e.g. `"NS-green"`) |
| `state`       | `string` | SUMO state string (e.g. `"GGGrrr"`)           |
| `duration`    | `float`  | Nominal duration in seconds                   |
| `minDuration` | `float?` | Minimum duration (actuated control)           |
| `maxDuration` | `float?` | Maximum duration (actuated control)           |

#### `TrafficLightCycle`

| Field           | Type    | Description                                 |
| --------------- | ------- | ------------------------------------------- |
| `cycleDuration` | `float` | Total cycle duration in seconds             |
| `timeInCycle`   | `float` | Current position within the cycle (seconds) |
| `cycleNumber`   | `int`   | Absolute cycle count since simulation start |

#### `TrafficLightPerformance`

| Field                      | Type    | Description                                                |
| -------------------------- | ------- | ---------------------------------------------------------- |
| `vehiclesClearedThisPhase` | `int`   | Vehicles cleared during the current green phase            |
| `vehiclesClearedLastPhase` | `int`   | Vehicles cleared during the previous green phase           |
| `vehiclesWaitingForGreen`  | `int`   | Vehicles currently waiting for green                       |
| `maxWaitingTime`           | `float` | Maximum individual waiting time (seconds)                  |
| `avgWaitingTime`           | `float` | Average waiting time across all waiting vehicles (seconds) |

---

### 6.6 `Vehicle`

One entry per vehicle detected within `detection_radius` on a road.

| Field            | Type          | Description                                            |
| ---------------- | ------------- | ------------------------------------------------------ |
| `vehicleId`      | `string`      | SUMO vehicle ID                                        |
| `laneId`         | `string`      | Lane the vehicle currently occupies                    |
| `speed`          | `float`       | Current speed (km/h)                                   |
| `position`       | `float`       | Distance from the stop line in metres                  |
| `waitingTime`    | `float`       | Cumulative time the vehicle has been stopped (seconds) |
| `wasteTime`      | `float`       | Time stopped while signal was green (seconds)          |
| `acceleration`   | `float`       | Current acceleration (m/s²)                            |
| `vehicleType`    | `VehicleType` | Vehicle class enum                                     |
| `distanceToStop` | `float?`      | Estimated distance to the stop line (metres)           |

---

## 7. Error Handling

| Scenario                                   | Behaviour                                                                  |
| ------------------------------------------ | -------------------------------------------------------------------------- |
| TraCI disconnect mid-run                   | Log error, attempt reconnect once, then exit cleanly                       |
| `collect()` raises exception               | Log to file with `junction_id` + traceback, skip this sensor for this step |
| `HighwayClient.publish()` raises exception | Log warning, continue (stdout still works)                                 |
| Junction has no incoming edges             | Skip junction, log warning once at startup                                 |
| Unknown vehicle type from SUMO             | Map to `VehicleType.CAR`, log debug                                        |

---

## 8. Broker Topic Convention

Default pattern: `sumo/sensor/{id}/data` where `{id}` is the SUMO junction ID.

Example for junction `J3`: `sumo/sensor/J3/data`

Users can override the pattern in `broker.topic_pattern`; `{id}` is always substituted at publish time. The topic string is passed directly to `HighwayClient.publish()` as the first argument.

### 8.1 `HighwayClient` usage summary

| Operation          | Method called                                                                                 | Notes                                              |
| ------------------ | --------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Connect            | `from libs.rnneb_client import HighwayClient` then `HighwayClient(config, auto_connect=True)` | Blocks until `connect` event fires or timeout (5s) |
| Publish snapshot   | `client.publish(topic, json_bytes, qos=0)`                                                    | QoS 0, fire-and-forget                             |
| Disconnect on exit | `client.disconnect()`                                                                         | Sends `DISCONNECT` packet, closes socket           |
| Error handling     | `client.on_error(handler)`                                                                    | Logs warning, simulation continues                 |

### 8.2 Packet format

`HighwayClient` uses a custom binary protocol, not standard MQTT. The payload wire format for a `PUBLISH` packet is:

```
[u8  packet_type = 0x30]
[u8  flags       = (qos << 1) & 0x06]
[u16 payload_len]
[u16 topic_len][topic bytes]
[u16 packet_id]
[u64 offset = 0]
[N   data bytes  = UTF-8 encoded JSON]
```

The simulator always publishes with `offset = 0` and `qos = 0` (no PUBACK expected).

---

## 9. Intersection Type Mapping

SUMO junction types are mapped to `IntersectionType` enum values as follows:

| SUMO junction type          | IntersectionType                                            |
| --------------------------- | ----------------------------------------------------------- |
| `traffic_light`             | `FOUR_WAY` (default for signalised)                         |
| `traffic_light_unregulated` | `FOUR_WAY`                                                  |
| `priority`                  | Inferred from edge count: 2 = `T_JUNCTION`, 3+ = `FOUR_WAY` |
| `roundabout`                | `ROUNDABOUT`                                                |
| `right_before_left`         | `FOUR_WAY`                                                  |
| `unregulated`               | `CUSTOM`                                                    |
| `dead_end` / `internal`     | Skipped                                                     |

---

## 10. README Outline

- **Prerequisites**: Python 3.10+, SUMO 1.19+, `lxml` (no external broker library — `HighwayClient` is bundled in `libs/rnneb_client.py`)
- **Installation**: `pip install -e .`
- **Config**: copy `config.example.json`, fill in `sumo` and `mqtt` fields
- **Running**: `python -m sumo_sensor --config config.json`
- **Output**: description of stdout format and MQTT payload structure
- **Extending**: how to add a new intersection type mapping

---

## 11. Dependencies

| Package                          | Purpose                                                     | Version    |
| -------------------------------- | ----------------------------------------------------------- | ---------- |
| `traci` (bundled with SUMO)      | TraCI Python API                                            | SUMO 1.19+ |
| `libs/rnneb_client.py` (bundled) | Highway Broker client (`HighwayClient`) — no install needed | n/a        |
| `lxml`                           | `.net.xml` parsing                                          | >=4.9      |
| `dataclasses-json`               | Dataclass serialisation                                     | >=0.6      |
| `python-dotenv`                  | Optional env var support                                    | >=1.0      |

---

## 12. Out of Scope for v1

- `RLState` preprocessing — downstream RL agent responsibility
- RL action consumption via MQTT
- Remote TraCI (non-localhost)
- Unit / integration tests
- Docker / containerisation
- GUI or web dashboard
- Multi-simulation / federated scenarios
