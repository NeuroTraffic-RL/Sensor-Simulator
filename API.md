# SUMO Sensor Simulator - API Documentation

**Version 1.0**

This document describes the data format published by the SUMO Sensor Simulator to the Highway Broker (MQTT).

---

## Table of Contents

1. [Message Transport](#message-transport)
2. [Data Structure](#data-structure)
3. [Complete Example](#complete-example)
4. [Field Reference](#field-reference)
5. [Enumerations](#enumerations)
6. [Usage Examples](#usage-examples)

---

## Message Transport

### MQTT Topic Pattern

```
sumo/sensor/{sensorId}/data
```

**Examples:**

- `sumo/sensor/12449750784/data`
- `sumo/sensor/custom_sensor_1/data`

The topic pattern is configurable via the `broker.topic_pattern` setting in your config file.

### Message Properties

| Property      | Value                                       |
| ------------- | ------------------------------------------- |
| **QoS**       | 0 (at most once)                            |
| **Format**    | JSON (UTF-8 encoded)                        |
| **Encoding**  | Compact (no pretty-print)                   |
| **Frequency** | Configurable per sensor (default: 1 second) |

---

## Data Structure

### Root Object: `RawSensorData`

```typescript
{
  sensorId: string,              // Unique sensor/junction ID
  sensorType: IntersectionType,  // Type of intersection
  timestamp: string,             // ISO 8601 timestamp (UTC)
  geometry: IntersectionGeometry,
  roads: Road[],
  intersectionMetrics: IntersectionMetrics
}
```

---

### `IntersectionGeometry`

Physical placement and detection configuration.

```typescript
{
  position: {
    x: number,  // X coordinate in meters
    y: number   // Y coordinate in meters
  },
  detection_radius: number,     // Detection radius in meters
  intersection_type: IntersectionType,
  radius?: number              // Only for roundabouts
}
```

---

### `Road`

One object per incoming edge at the junction.

```typescript
{
  roadId: string,               // SUMO edge ID
  direction: RoadDirection,     // N/S/E/W/NE/NW/SE/SW/custom
  incomingEdgeId: string,       // Same as roadId
  lanes: number,                // Number of lanes
  roadMetrics: RoadMetrics,
  queueMetrics: QueueMetrics,
  flowMetrics: FlowMetrics,
  laneDetails: Lane[],
  trafficLight: TrafficLight | TrafficLightRef | null,
  vehicles: Vehicle[]
}
```

---

### `RoadMetrics`

Speed, occupancy, and capacity metrics for a road.

```typescript
{
  length: number,              // Edge length in meters
  speedLimit: number,          // Posted speed limit (km/h)
  freeFlowSpeed: number,       // Observed maximum speed (km/h)
  capacity: number,            // Theoretical capacity (vehicles/hour)
  occupancyRate: number,       // Current occupancy 0-1
  avgSpeed: number,            // Average speed of all vehicles (km/h)
  minSpeed: number,            // Minimum observed speed (km/h)
  maxSpeed: number,            // Maximum observed speed (km/h)
  congestionLevel?: CongestionLevel,  // free/light/moderate/heavy/congested
  speedTrend?: number          // Change in avg speed (km/h/s), null initially
}
```

---

### `QueueMetrics`

Queue length and saturation metrics.

```typescript
{
  queueLength: number,           // Current number of queued vehicles
  maxQueueLengthObserved: number,// Maximum queue seen in this session
  queueTrend: number,            // Vehicles/sec joining queue (negative = dissipating)
  saturationRatio: number        // queueLength / capacity (0-1)
}
```

---

### `FlowMetrics`

Vehicle counts and flow rate metrics.

```typescript
{
  vehicleCount: number,          // Vehicles currently on the road
  vehiclesExited: number,        // Vehicles that left in last sample window
  vehiclesEntered: number,       // Vehicles that entered in last sample window
  flowRate: number,              // Vehicles/hour
  utilizationRate: number,       // flowRate / capacity (0-1)
  timeLastVehiclePassed: number  // Seconds since last vehicle passed stop line
}
```

---

### `Lane`

Per-lane breakdown within a road.

```typescript
{
  laneId: string,        // SUMO lane ID (format: edgeId_laneIndex)
  vehicleCount: number,  // Vehicles on this lane
  avgSpeed: number,      // Average speed (km/h)
  occupancy: number,     // Lane occupancy (0-1)
  queueLength: number    // Queued vehicles on this lane
}
```

---

### `TrafficLight`

Full traffic light object (first occurrence).

```typescript
{
  trafficLightId: string,
  controlledRoads: string[],     // List of controlled road IDs
  signal: {
    currentColor: TrafficLightColor,  // "g", "y", or "r"
    timeInCurrentPhase: number,       // Seconds elapsed in current phase
    timeUntilNextSwitch: number       // Seconds until next phase transition
  },
  phaseProgram: {
    currentPhaseIndex: number,
    totalPhases: number,
    phases: [
      {
        index: number,
        name: string,              // e.g., "NS-green"
        state: string,             // SUMO state string (e.g., "GGGrrr")
        duration: number,          // Nominal duration in seconds
        minDuration?: number,      // Minimum duration (actuated control)
        maxDuration?: number       // Maximum duration (actuated control)
      }
    ]
  },
  cycle: {
    cycleDuration: number,   // Total cycle duration (seconds)
    timeInCycle: number,     // Current position within cycle (seconds)
    cycleNumber: number      // Absolute cycle count since simulation start
  },
  performance: {
    vehiclesClearedThisPhase: number,
    vehiclesClearedLastPhase: number,
    vehiclesWaitingForGreen: number,
    maxWaitingTime: number,    // Seconds
    avgWaitingTime: number     // Seconds
  }
}
```

---

### `TrafficLightRef`

Reference to a traffic light already defined (subsequent occurrences).

```typescript
{
    ref: string; // Traffic light ID (refers to previously published TrafficLight)
}
```

---

### `Vehicle`

Vehicle detected within detection radius on a road.

```typescript
{
  vehicleId: string,
  laneId: string,
  speed: number,            // km/h
  position: number,         // Distance from stop line in meters
  waitingTime: number,      // Cumulative time stopped (seconds)
  wasteTime: number,        // Time stopped while signal was green (seconds)
  acceleration: number,     // m/s²
  vehicleType: VehicleType, // car/truck/bus/motorcycle/bicycle
  distanceToStop?: number   // Estimated distance to stop line (meters)
}
```

---

### `IntersectionMetrics`

Aggregated statistics across all roads.

```typescript
{
  totalVehicles: number,               // Total vehicles at intersection
  totalQueueLength: number,            // Total queued vehicles
  avgSpeedAll: number,                 // Average speed across all vehicles (km/h)
  globalCongestionLevel: number,       // Weighted congestion (0-1)
  bottleneckRoad?: string,             // Road ID with highest saturation
  criticalTrafficLight?: string,       // TL ID with longest avg waiting time
  trafficLightCount: number            // Number of traffic lights at intersection
}
```

---

## Enumerations

### `IntersectionType`

```typescript
type IntersectionType =
    | "4-way-intersection"
    | "t-junction"
    | "y-junction"
    | "roundabout"
    | "traffic-circle"
    | "custom";
```

### `RoadDirection`

```typescript
type RoadDirection =
    | "north"
    | "south"
    | "east"
    | "west"
    | "northeast"
    | "northwest"
    | "southeast"
    | "southwest"
    | "custom";
```

### `TrafficLightColor`

```typescript
type TrafficLightColor = "g" | "y" | "r"; // green, yellow, red
```

### `VehicleType`

```typescript
type VehicleType = "car" | "truck" | "bus" | "motorcycle" | "bicycle";
```

### `CongestionLevel`

Derived from occupancy rate thresholds:

```typescript
type CongestionLevel =
    | "free" // < 20%
    | "light" // 20-40%
    | "moderate" // 40-60%
    | "heavy" // 60-80%
    | "congested"; // > 80%
```

---

## Complete Example

### Minimal Example (No Vehicles)

```json
{
    "sensorId": "12449750784",
    "sensorType": "4-way-intersection",
    "timestamp": "2026-03-17T20:30:45Z",
    "geometry": {
        "position": {
            "x": 3542.67,
            "y": 3891.23
        },
        "detection_radius": 80.0,
        "intersection_type": "4-way-intersection",
        "radius": null
    },
    "roads": [],
    "intersectionMetrics": {
        "totalVehicles": 0,
        "totalQueueLength": 0,
        "avgSpeedAll": 0.0,
        "globalCongestionLevel": 0.0,
        "bottleneckRoad": null,
        "criticalTrafficLight": null,
        "trafficLightCount": 0
    }
}
```

---

### Full Example (With Traffic)

```json
{
    "sensorId": "12449750784",
    "sensorType": "4-way-intersection",
    "timestamp": "2026-03-17T20:30:45Z",
    "geometry": {
        "position": {
            "x": 3542.67,
            "y": 3891.23
        },
        "detection_radius": 80.0,
        "intersection_type": "4-way-intersection",
        "radius": null
    },
    "roads": [
        {
            "roadId": "edge_123",
            "direction": "north",
            "incomingEdgeId": "edge_123",
            "lanes": 2,
            "roadMetrics": {
                "length": 150.5,
                "speedLimit": 50.0,
                "freeFlowSpeed": 50.0,
                "capacity": 3600,
                "occupancyRate": 0.35,
                "avgSpeed": 32.5,
                "minSpeed": 0.0,
                "maxSpeed": 48.2,
                "congestionLevel": "light",
                "speedTrend": -2.3
            },
            "queueMetrics": {
                "queueLength": 5,
                "maxQueueLengthObserved": 8,
                "queueTrend": 0.5,
                "saturationRatio": 0.14
            },
            "flowMetrics": {
                "vehicleCount": 12,
                "vehiclesExited": 2,
                "vehiclesEntered": 3,
                "flowRate": 1200.0,
                "utilizationRate": 0.33,
                "timeLastVehiclePassed": 1.5
            },
            "laneDetails": [
                {
                    "laneId": "edge_123_0",
                    "vehicleCount": 6,
                    "avgSpeed": 28.3,
                    "occupancy": 0.3,
                    "queueLength": 2
                },
                {
                    "laneId": "edge_123_1",
                    "vehicleCount": 6,
                    "avgSpeed": 36.7,
                    "occupancy": 0.4,
                    "queueLength": 3
                }
            ],
            "trafficLight": {
                "trafficLightId": "tl_junction_123",
                "controlledRoads": ["edge_123", "edge_124"],
                "signal": {
                    "currentColor": "r",
                    "timeInCurrentPhase": 15.2,
                    "timeUntilNextSwitch": 4.8
                },
                "phaseProgram": {
                    "currentPhaseIndex": 2,
                    "totalPhases": 4,
                    "phases": [
                        {
                            "index": 0,
                            "name": "NS-green",
                            "state": "GGGrrr",
                            "duration": 30.0,
                            "minDuration": 10.0,
                            "maxDuration": 45.0
                        },
                        {
                            "index": 1,
                            "name": "NS-yellow",
                            "state": "yyyrrr",
                            "duration": 3.0,
                            "minDuration": null,
                            "maxDuration": null
                        },
                        {
                            "index": 2,
                            "name": "EW-green",
                            "state": "rrrGGG",
                            "duration": 20.0,
                            "minDuration": 10.0,
                            "maxDuration": 35.0
                        },
                        {
                            "index": 3,
                            "name": "EW-yellow",
                            "state": "rrryyy",
                            "duration": 3.0,
                            "minDuration": null,
                            "maxDuration": null
                        }
                    ]
                },
                "cycle": {
                    "cycleDuration": 56.0,
                    "timeInCycle": 48.2,
                    "cycleNumber": 42
                },
                "performance": {
                    "vehiclesClearedThisPhase": 0,
                    "vehiclesClearedLastPhase": 0,
                    "vehiclesWaitingForGreen": 0,
                    "maxWaitingTime": 0.0,
                    "avgWaitingTime": 0.0
                }
            },
            "vehicles": [
                {
                    "vehicleId": "veh_001",
                    "laneId": "edge_123_0",
                    "speed": 0.0,
                    "position": 5.2,
                    "waitingTime": 15.2,
                    "wasteTime": 0.0,
                    "acceleration": 0.0,
                    "vehicleType": "car",
                    "distanceToStop": 5.2
                },
                {
                    "vehicleId": "veh_002",
                    "laneId": "edge_123_1",
                    "speed": 45.8,
                    "position": 82.5,
                    "waitingTime": 0.0,
                    "wasteTime": 0.0,
                    "acceleration": 1.2,
                    "vehicleType": "car",
                    "distanceToStop": 68.0
                },
                {
                    "vehicleId": "veh_003",
                    "laneId": "edge_123_0",
                    "speed": 0.0,
                    "position": 12.8,
                    "waitingTime": 10.5,
                    "wasteTime": 0.0,
                    "acceleration": 0.0,
                    "vehicleType": "truck",
                    "distanceToStop": 12.8
                }
            ]
        }
    ],
    "intersectionMetrics": {
        "totalVehicles": 12,
        "totalQueueLength": 5,
        "avgSpeedAll": 30.5,
        "globalCongestionLevel": 0.35,
        "bottleneckRoad": "edge_123",
        "criticalTrafficLight": null,
        "trafficLightCount": 1
    }
}
```

---

## Field Reference

### Key Metrics for Traffic Analysis

| Metric                  | Field Path                                 | Type  | Description              | Use Case                   |
| ----------------------- | ------------------------------------------ | ----- | ------------------------ | -------------------------- |
| **Congestion Level**    | `roads[].roadMetrics.congestionLevel`      | enum  | Current congestion state | Traffic light optimization |
| **Queue Length**        | `roads[].queueMetrics.queueLength`         | int   | Vehicles waiting         | Queue management           |
| **Saturation Ratio**    | `roads[].queueMetrics.saturationRatio`     | float | Queue vs capacity        | Bottleneck detection       |
| **Average Speed**       | `roads[].roadMetrics.avgSpeed`             | float | Mean speed of vehicles   | Flow efficiency            |
| **Occupancy Rate**      | `roads[].roadMetrics.occupancyRate`        | float | Road utilization         | Capacity planning          |
| **Flow Rate**           | `roads[].flowMetrics.flowRate`             | float | Vehicles per hour        | Throughput analysis        |
| **Waiting Time**        | `vehicles[].waitingTime`                   | float | Time vehicle is stopped  | Delay analysis             |
| **Traffic Light Phase** | `roads[].trafficLight.signal.currentColor` | enum  | Current signal state     | Signal coordination        |
| **Speed Trend**         | `roads[].roadMetrics.speedTrend`           | float | Speed change rate        | Congestion prediction      |

---

## Usage Examples

### Python - Subscribe to Sensor Data

```python
import sys
sys.path.insert(0, 'libs')
from rnneb_client import HighwayClient
import json

def on_message(message):
    """Handle incoming sensor data"""
    data = json.loads(message['data'])

    print(f"Sensor: {data['sensorId']}")
    print(f"Total vehicles: {data['intersectionMetrics']['totalVehicles']}")
    print(f"Queue length: {data['intersectionMetrics']['totalQueueLength']}")

    for road in data['roads']:
        print(f"  Road {road['roadId']}:")
        print(f"    Speed: {road['roadMetrics']['avgSpeed']:.1f} km/h")
        print(f"    Congestion: {road['roadMetrics']['congestionLevel']}")

client = HighwayClient({
    'host': 'localhost',
    'port': 1883,
    'client_id': 'sensor-consumer'
})

# Subscribe to all sensors
client.subscribe('sumo/sensor/+/data', on_message)

# Or subscribe to specific sensor
client.subscribe('sumo/sensor/12449750784/data', on_message)
```

### JavaScript/TypeScript - Process Sensor Data

```typescript
import { HighwayClient } from "./highway-client";

interface RawSensorData {
    sensorId: string;
    sensorType: string;
    timestamp: string;
    geometry: IntersectionGeometry;
    roads: Road[];
    intersectionMetrics: IntersectionMetrics;
}

const client = new HighwayClient({
    host: "localhost",
    port: 1883,
    clientId: "sensor-consumer-ts",
});

client.subscribe("sumo/sensor/+/data", (message) => {
    const data: RawSensorData = JSON.parse(message.data);

    // Calculate average congestion
    const avgCongestion =
        data.roads.reduce(
            (sum, road) => sum + road.roadMetrics.occupancyRate,
            0,
        ) / data.roads.length;

    console.log(
        `Sensor ${data.sensorId}: ${(avgCongestion * 100).toFixed(1)}% congested`,
    );
});
```

### Extract Traffic Light Timings

```python
def extract_traffic_light_info(sensor_data):
    """Extract traffic light timing information"""
    for road in sensor_data['roads']:
        tl = road.get('trafficLight')

        if tl and 'trafficLightId' in tl:  # Full traffic light object
            print(f"Traffic Light: {tl['trafficLightId']}")
            print(f"  Current: {tl['signal']['currentColor']}")
            print(f"  Time in phase: {tl['signal']['timeInCurrentPhase']:.1f}s")
            print(f"  Time until switch: {tl['signal']['timeUntilNextSwitch']:.1f}s")
            print(f"  Cycle: {tl['cycle']['cycleNumber']} ({tl['cycle']['cycleDuration']:.0f}s)")
```

### Detect Congestion Patterns

```python
def detect_congestion(sensor_data):
    """Detect congested roads at an intersection"""
    congested_roads = []

    for road in sensor_data['roads']:
        metrics = road['roadMetrics']
        queue = road['queueMetrics']

        # Check multiple congestion indicators
        if (metrics.get('congestionLevel') in ['heavy', 'congested'] or
            queue['saturationRatio'] > 0.7 or
            metrics['avgSpeed'] < 15.0):  # Very slow traffic

            congested_roads.append({
                'road_id': road['roadId'],
                'congestion_level': metrics.get('congestionLevel'),
                'saturation': queue['saturationRatio'],
                'avg_speed': metrics['avgSpeed'],
                'queue_length': queue['queueLength']
            })

    return congested_roads
```

---

## Notes

1. **Null Values**: Fields marked with `?` may be `null` or omitted if not applicable
2. **Timestamps**: All timestamps are in UTC with ISO 8601 format
3. **Units**:
    - Distance: meters
    - Speed: km/h
    - Acceleration: m/s²
    - Time: seconds
    - Coordinates: SUMO simulation coordinates (meters)
4. **Traffic Light References**: To save bandwidth, traffic lights are sent in full on first occurrence, then referenced by ID on subsequent roads
5. **Update Frequency**: Configurable per sensor (default: 1 second)
6. **Custom Positions**: Sensors at custom positions may have empty `roads` arrays if no edges are within detection radius

---

## Version History

- **v1.0** (2026-03-17): Initial release

---

For implementation details and configuration, see [README.md](README.md).
