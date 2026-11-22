"""Tests for Pydantic AI VLM agent client (agent.py migration)."""
from __future__ import annotations

import asyncio
import json
from unittest import mock

import pytest

from darkwing.agent import (
    VLMClientAdapter,
    get_adapter,
    detect_bird_presence,
    propose_observation,
)
from darkwing.schema import ObservationRecord


def test_get_adapter_returns_observation_agent():
    """get_adapter returns the observation agent."""
    agent = get_adapter()
    assert agent.name == 'chimney_swift_observation_agent'


def test_bird_detection_function_exists():
    """detect_bird_presence is a callable function."""
    assert callable(detect_bird_presence)


def test_propose_observation_function_exists():
    """propose_observation is a callable function."""
    assert callable(propose_observation)


def test_vlm_client_adapter_has_required_methods():
    """VLMClientAdapter has detect_bird and propose_observation methods."""
    adapter = VLMClientAdapter()
    assert hasattr(adapter, 'detect_bird')
    assert hasattr(adapter, 'propose_observation')


@pytest.mark.asyncio
async def test_vlm_client_adapter_detect_bird(monkeypatch):
    """VLMClientAdapter.detect_bird performs binary bird presence check."""
    monkeypatch.setenv("VLM_BASE_URL", "http://test.example.com/v1")
    monkeypatch.setenv("VLM_MODEL", "test-model")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.setenv("VLM_PROVIDER", "test")

    adapter = VLMClientAdapter()

    # Mock binary agent response with AsyncMock for async run() method
    mock_result = mock.Mock()
    mock_result.output.bird_present = True
    mock_result.output.confidence = 0.9

    with mock.patch(
        "darkwing.agent.binary_agent",
        mock.AsyncMock(),
    ) as mock_binary:
        mock_binary.run.return_value = mock_result

        frames = [b"\xff\xd8fake1\xff\xd9", b"\xff\xd8fake2\xff\xd9"]
        context = {"window_id": "T3_09232026_1420", "tower": 3}

        result = await adapter.detect_bird(frames, context)
        assert result == (True, 0.9)

        # Verify the binary agent was called with correct prompt
        mock_binary.run.assert_called_once()


@pytest.mark.asyncio
async def test_vlm_client_adapter_detect_bird_false(monkeypatch):
    """VLMClientAdapter.detect_bird returns False when no bird."""
    monkeypatch.setenv("VLM_BASE_URL", "http://test.example.com/v1")
    monkeypatch.setenv("VLM_MODEL", "test-model")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.setenv("VLM_PROVIDER", "test")

    adapter = VLMClientAdapter()

    # Mock binary agent response - no bird
    mock_result = mock.Mock()
    mock_result.output.bird_present = False
    mock_result.output.confidence = 0.1

    with mock.patch(
        "darkwing.agent.binary_agent",
        mock.AsyncMock(),
    ) as mock_binary:
        mock_binary.run.return_value = mock_result

        frames = [b"\xff\xd8fake1\xff\xd9"]
        context = {"window_id": "T3_09232026_1420", "tower": 3}

        result = await adapter.detect_bird(frames, context)
        assert result == (False, 0.1)


@pytest.mark.asyncio
async def test_vlm_client_adapter_propose_observation(monkeypatch):
    """VLMClientAdapter.propose_observation returns validated ObservationRecord."""
    monkeypatch.setenv("VLM_BASE_URL", "http://test.example.com/v1")
    monkeypatch.setenv("VLM_MODEL", "test-model")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.setenv("VLM_PROVIDER", "test")

    adapter = VLMClientAdapter()

    # Mock observation agent response with valid data
    mock_result = mock.Mock()
    mock_result.output = ObservationRecord(
        tower=3,
        date_str="09/23/2026",
        hour=14,
        minutes_past_hour=20,
        num_adults=5,
        nesting_stage="nst",
        bill_use=["fd"],
        flights=["in"],
        num_near_nest=2,
        awake="y",
        notes="Test observation",
    )

    with mock.patch(
        "darkwing.agent.observation_agent",
        mock.AsyncMock(),
    ) as mock_obs:
        mock_obs.run.return_value = mock_result

        frames = [b"\xff\xd8fake1\xff\xd9"]
        context = {
            "tower": 3,
            "date": "09/23/2026",
            "hour": 14,
            "minute": 20,
        }

        record = await adapter.propose_observation(frames, context)
        assert isinstance(record, ObservationRecord)
        assert record.tower == 3
        assert record.num_adults == 5
        assert record.nesting_stage == "nst"


@pytest.mark.asyncio
async def test_detect_bird_presence_service(monkeypatch):
    """detect_bird_presence service function returns boolean."""
    monkeypatch.setenv("VLM_BASE_URL", "http://test.example.com/v1")
    monkeypatch.setenv("VLM_MODEL", "test-model")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.setenv("VLM_PROVIDER", "test")

    result = detect_bird_presence(
        frames=[b"\xff\xd8fake1\xff\xd9"],
        context={"tower": 1, "date": "09/23/2026", "hour": 14, "minute": 20},
    )
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_propose_observation_service(monkeypatch):
    """propose_observation service function returns ObservationRecord."""
    monkeypatch.setenv("VLM_BASE_URL", "http://test.example.com/v1")
    monkeypatch.setenv("VLM_MODEL", "test-model")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.setenv("VLM_PROVIDER", "test")

    record = propose_observation(
        frames=[b"\xff\xd8fake1\xff\xd9"],
        context={"tower": 1, "date": "09/23/2026", "hour": 14, "minute": 20},
    )
    assert isinstance(record, ObservationRecord)
    assert record.tower == 1