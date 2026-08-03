# data_types.py
from typing import TypedDict, List

class LocationMetadata(TypedDict):
    site_id: str
    latitude: float
    longitude: float

class SensorReading(TypedDict):
    sensor: str
    value: float
    unit_of_measure: str
    # Added for future proofing/schema compliance check
    validated_at_epoch: int | None # Time when the data point was processed by our system

class SightingRecord(TypedDict):
    uuid: str
    timestamp_utc: str
    location: LocationMetadata
    sensor_readings: list[SensorReading]
    metadata: dict # Placeholder for device/telemetry integration

# Exporting the classes defined above makes them reusable components across the project.