"""
Data models for SUMO sensor simulator.
Python equivalents of TypeScript types for interoperability.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Union
from datetime import datetime


# ============================================================================
# ENUMS
# ============================================================================

class TrafficLightColor(str, Enum):
    """Traffic light color states"""
    GREEN = "g"
    YELLOW = "y"
    RED = "r"


class VehicleType(str, Enum):
    """Vehicle type classifications"""
    CAR = "car"
    TRUCK = "truck"
    BUS = "bus"
    MOTORCYCLE = "motorcycle"
    BICYCLE = "bicycle"


class IntersectionType(str, Enum):
    """Intersection type classifications"""
    FOUR_WAY = "4-way-intersection"
    ROUNDABOUT = "roundabout"
    T_JUNCTION = "t-junction"
    Y_JUNCTION = "y-junction"
    TRAFFIC_CIRCLE = "traffic-circle"
    CUSTOM = "custom"


class RoadDirection(str, Enum):
    """Road direction classifications"""
    NORTH = "north"
    SOUTH = "south"
    EAST = "east"
    WEST = "west"
    NORTHEAST = "northeast"
    NORTHWEST = "northwest"
    SOUTHEAST = "southeast"
    SOUTHWEST = "southwest"
    CUSTOM = "custom"


class CongestionLevel(str, Enum):
    """Congestion level classifications based on occupancy thresholds"""
    FREE = "free"          # < 20%
    LIGHT = "light"        # 20-40%
    MODERATE = "moderate"  # 40-60%
    HEAVY = "heavy"        # 60-80%
    CONGESTED = "congested"  # > 80%


# ============================================================================
# BASIC STRUCTURES
# ============================================================================

@dataclass
class Position:
    """2D position coordinates"""
    x: float
    y: float


@dataclass
class IntersectionGeometry:
    """Physical placement and detection configuration"""
    position: Position
    detection_radius: float
    intersection_type: IntersectionType
    radius: Optional[float] = None  # Only set for roundabouts


# ============================================================================
# VEHICLE
# ============================================================================

@dataclass
class Vehicle:
    """Vehicle detected within detection radius on a road"""
    vehicleId: str
    laneId: str
    speed: float  # km/h
    position: float  # Distance from stop line in metres
    waitingTime: float  # Cumulative time stopped (seconds)
    wasteTime: float  # Time stopped while signal was green (seconds)
    acceleration: float  # m/s²
    vehicleType: VehicleType
    distanceToStop: Optional[float] = None  # Estimated distance to stop line (metres)


# ============================================================================
# LANE
# ============================================================================

@dataclass
class Lane:
    """Per-lane breakdown within a road"""
    laneId: str
    vehicleCount: int
    avgSpeed: float  # km/h
    occupancy: float  # 0-1
    queueLength: int


# ============================================================================
# TRAFFIC LIGHT STRUCTURES
# ============================================================================

@dataclass
class TrafficLightSignal:
    """Current signal state"""
    currentColor: TrafficLightColor
    timeInCurrentPhase: float  # Seconds elapsed in current phase
    timeUntilNextSwitch: float  # Seconds until next phase transition


@dataclass
class TrafficLightPhase:
    """Single phase in traffic light program"""
    index: int
    name: str  # Human-readable phase name (e.g. "NS-green")
    state: str  # SUMO state string (e.g. "GGGrrr")
    duration: float  # Nominal duration in seconds
    minDuration: Optional[float] = None  # Minimum duration (actuated control)
    maxDuration: Optional[float] = None  # Maximum duration (actuated control)


@dataclass
class TrafficLightProgram:
    """Full phase program"""
    currentPhaseIndex: int
    totalPhases: int
    phases: List[TrafficLightPhase]


@dataclass
class TrafficLightCycle:
    """Current position in the cycle"""
    cycleDuration: float  # Total cycle duration in seconds
    timeInCycle: float  # Current position within cycle (seconds)
    cycleNumber: int  # Absolute cycle count since simulation start


@dataclass
class TrafficLightPerformance:
    """Clearance and waiting statistics"""
    vehiclesClearedThisPhase: int
    vehiclesClearedLastPhase: int
    vehiclesWaitingForGreen: int
    maxWaitingTime: float  # Seconds
    avgWaitingTime: float  # Seconds


@dataclass
class TrafficLight:
    """Full traffic light object"""
    trafficLightId: str
    controlledRoads: List[str]
    signal: TrafficLightSignal
    phaseProgram: TrafficLightProgram
    cycle: TrafficLightCycle
    performance: TrafficLightPerformance


@dataclass
class TrafficLightRef:
    """Reference to shared traffic light"""
    ref: str  # Traffic light ID


# Union type for traffic light data
TrafficLightData = Optional[Union[TrafficLight, TrafficLightRef]]


# ============================================================================
# METRICS
# ============================================================================

@dataclass
class RoadMetrics:
    """Speed, occupancy, capacity metrics for a road"""
    length: float  # Edge length in metres
    speedLimit: float  # Posted speed limit (km/h)
    freeFlowSpeed: float  # Observed maximum speed (km/h)
    capacity: int  # Theoretical capacity (vehicles/hour)
    occupancyRate: float  # Current occupancy 0-1
    avgSpeed: float  # Average speed of all vehicles on road (km/h)
    minSpeed: float  # Minimum observed speed (km/h)
    maxSpeed: float  # Maximum observed speed (km/h)
    congestionLevel: Optional[CongestionLevel] = None
    speedTrend: Optional[float] = None  # Change in avg speed per second (km/h/s)


@dataclass
class QueueMetrics:
    """Queue length and saturation metrics"""
    queueLength: int  # Current number of queued vehicles
    maxQueueLengthObserved: int  # Maximum queue seen in this session
    queueTrend: float  # Vehicles/sec joining queue (negative = dissipating)
    saturationRatio: float  # queueLength / capacity 0-1


@dataclass
class FlowMetrics:
    """Vehicle counts and flow rate metrics"""
    vehicleCount: int  # Vehicles currently on the road
    vehiclesExited: int  # Vehicles that left in last sample window
    vehiclesEntered: int  # Vehicles that entered in last sample window
    flowRate: float  # Vehicles/hour
    utilizationRate: float  # flowRate / capacity 0-1
    timeLastVehiclePassed: float  # Seconds since last vehicle passed stop line


@dataclass
class IntersectionMetrics:
    """Aggregated statistics across all roads"""
    totalVehicles: int
    totalQueueLength: int
    avgSpeedAll: float  # km/h
    globalCongestionLevel: float  # Weighted congestion 0-1
    bottleneckRoad: Optional[str] = None  # Road ID with highest saturation
    criticalTrafficLight: Optional[str] = None  # TL ID with longest avg waiting time
    trafficLightCount: int = 0


# ============================================================================
# ROAD
# ============================================================================

@dataclass
class Road:
    """One Road object per incoming edge at the junction"""
    roadId: str
    direction: RoadDirection
    incomingEdgeId: str
    lanes: int
    roadMetrics: RoadMetrics
    queueMetrics: QueueMetrics
    flowMetrics: FlowMetrics
    laneDetails: List[Lane]
    trafficLight: TrafficLightData
    vehicles: List[Vehicle]


# ============================================================================
# TOP-LEVEL: RAW SENSOR DATA
# ============================================================================

@dataclass
class RawSensorData:
    """Root object published to MQTT and printed to stdout"""
    sensorId: str
    sensorType: IntersectionType
    timestamp: str  # ISO 8601 timestamp
    geometry: IntersectionGeometry
    roads: List[Road]
    intersectionMetrics: IntersectionMetrics


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_congestion_level(occupancy: float) -> CongestionLevel:
    """Derive congestion level from occupancy rate"""
    if occupancy < 0.2:
        return CongestionLevel.FREE
    elif occupancy < 0.4:
        return CongestionLevel.LIGHT
    elif occupancy < 0.6:
        return CongestionLevel.MODERATE
    elif occupancy < 0.8:
        return CongestionLevel.HEAVY
    else:
        return CongestionLevel.CONGESTED


def map_sumo_vehicle_type(vtype: str) -> VehicleType:
    """Map SUMO vehicle type to VehicleType enum"""
    vtype_lower = vtype.lower()
    if "truck" in vtype_lower or "trailer" in vtype_lower:
        return VehicleType.TRUCK
    elif "bus" in vtype_lower:
        return VehicleType.BUS
    elif "motorcycle" in vtype_lower or "moped" in vtype_lower:
        return VehicleType.MOTORCYCLE
    elif "bicycle" in vtype_lower or "bike" in vtype_lower:
        return VehicleType.BICYCLE
    else:
        return VehicleType.CAR


def to_dict(obj):
    """Convert dataclass to dict recursively for JSON serialization"""
    if hasattr(obj, '__dataclass_fields__'):
        result = {}
        for field_name in obj.__dataclass_fields__:
            value = getattr(obj, field_name)
            if value is None:
                result[field_name] = None
            elif isinstance(value, Enum):
                result[field_name] = value.value
            elif isinstance(value, list):
                result[field_name] = [to_dict(item) for item in value]
            elif hasattr(value, '__dataclass_fields__'):
                result[field_name] = to_dict(value)
            else:
                result[field_name] = value
        return result
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, list):
        return [to_dict(item) for item in obj]
    else:
        return obj
