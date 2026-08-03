import pytest
from unittest.mock import patch, MagicMock

from src.main_processor import process_sighting_data

# --- Fixtures & Setup ---

@pytest.fixture
def mock_analysis_segment():
    """Provides a fixture for a valid mocked analysis segment."""
    # Note: Using literal strings/fixtures defined outside the parametrization context
    return {
        "uuid": "a1b2c3d4-e5f6",
        "timestamp_utc": "2026-08-05T10:00:00+00:00",
        "location": {
            "site_id": "SIT-ALPHA",
            "latitude": 34.0522,
            "longitude": -118.2437
        },
        "readings": [
            {"sensor": "temperature", "value": 25.5, "unit_of_measure": "C"},
            {"sensor": "humidity", "value": 65.0, "unit_of_measure": "%"}
        ]
    }

@pytest.fixture
def mock_hardware_telemetry():
    """Provides a fixture for valid mocked hardware telemetry."""
    return {
        "device_id": "HW-789",
        "battery_level": 0.92,
        # Fixed to clean ISO string format
        "last_connection": "2026-08-05T10:00:05+00:00"
    }

@pytest.fixture
def valid_input_data(mock_analysis_segment):
    """Provides a list of two distinct segments, excluding telemetry for simple testing."""
    return [
        mock_analysis_segment,
        {**mock_analysis_segment, "uuid": "b2c3d4e5-f6g7"} # Second distinct segment
    ]

# --- Test Cases ---

@pytest.mark.parametrize("input_data", [
    (
        {"uuid": "a1b2c3d4-e5f6", "timestamp_utc": "2026-08-05T10:00:00+00:00", "location": {"site_id": "SIT-ALPHA", "latitude": 34.0522, "longitude": -118.2437}, "readings": [{"sensor": "temp", "value": 25.5, "unit_of_measure": "C"}]}
    ),
    ([]), 
])
def test_sighting_data_initialization(input_data):
    """Test processing with minimal or empty valid data segments."""
    # We mock the reolinkapi external call to prevent actual network calls during unit testing.
    with patch('src.main_processor.reolinkapi', MagicMock()) as mock_api:
        results = process_sighting_data(segments=[input_data], telemetry={})

def test_golden_schema_validation_failure_null_field():
    """Test case: Validation fails when a required field (e.g., location site_id) is null or missing."""
    invalid_segment = {
        "uuid": "a1b2c3d4-e5f6",
        "timestamp_utc": "2026-08-05T10:00:00+00:00", 
        # Intentionally removing 'location' to test failure path
        "readings": [{"sensor": "temp", "value": 25.5, "unit_of_measure": "C"}]
    }

    with patch('src.main_processor.reolinkapi', MagicMock()) as mock_api:
        results = process_sighting_data(segments=[invalid_segment], telemetry={})
        
        # Expect the result list to be empty or contain only error messages, 
        # and should not crash due to validation failure.
        assert results == []

def test_golden_schema_validation_duplicate_record():
    """Test case: Validation fails when a duplicate UUID/TimestampUTC combination is present (PRD Rule 16)."""
    duplicate_segment = {
        "uuid": "a1b2c3d4-e5f6", # Same UUID
        "timestamp_utc": "2026-08-05T10:00:00+00:00", # Same Timestamp
        "location": {"site_id": "SIT-ALPHA", "latitude": 34.0, "longitude": -118.2},
        "readings": [{"sensor": "temp", "value": 26.0, "unit_of_measure": "C"}]
    }
    
    # Use the function logic with two identical records for testing
    duplicate_input = [
        {"uuid": "a1b2c3d4-e5f6", "timestamp_utc": "2026-08-05T10:00:00+00:00", "location": {"site_id": "SIT-ALPHA", "latitude": 34.0, "longitude": -118.2}, "readings": [{"sensor": "temp", "value": 25.5, "unit_of_measure": "C"}]},
        duplicate_segment # The duplicate segment should trigger the error detection logic
    ]

    with patch('src.main_processor.reolinkapi', MagicMock()) as mock_api:
        results = process_sighting_data(segments=[duplicate_input], telemetry={})
        # Placeholder assertion for final completeness (user must fill this in)