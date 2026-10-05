"""Tests for MVP3 Phase 2 VLM agent client (agent.py)."""
from __future__ import annotations

import asyncio
import json
from unittest import mock

import httpx
import pytest

from darkwing.agent import AIObservationAgent
from darkwing.schema import ObservationRecord


def _fake_frames(n=2) -> list[bytes]:
    return [b"\xff\xd8fakejpg%d\xff\xd9" % i for i in range(n)]


def test_init_requires_vlm_provider(monkeypatch):
    """Agent init fails when VLM_PROVIDER is not set (other vars already configured)."""
    # Set all other required vars first, then delete only VLM_PROVIDER
    monkeypatch.setenv("VLM_BASE_URL", "http://test.example.com/v1")
    monkeypatch.setenv("VLM_MODEL", "test-model")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.delenv("VLM_PROVIDER", raising=False)
    with pytest.raises(ValueError, match="VLM_PROVIDER"):
        AIObservationAgent()


def test_init_requires_all_config(monkeypatch):
    """Agent init requires all four VLM env vars."""
    # Set only three of four required vars
    monkeypatch.setenv("VLM_BASE_URL", "http://test")
    monkeypatch.setenv("VLM_MODEL", "test-model")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.delenv("VLM_PROVIDER", raising=False)

    with pytest.raises(ValueError, match="VLM_PROVIDER"):
        AIObservationAgent()


def test_provider_label_stored(monkeypatch):
    """VLM_PROVIDER value is stored as provider label."""
    monkeypatch.setenv("VLM_BASE_URL", "http://test")
    monkeypatch.setenv("VLM_MODEL", "test-model")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.setenv("VLM_PROVIDER", "test-provider")

    agent = AIObservationAgent()
    assert agent.provider == "test-provider"


def test_uses_configured_base_url_and_model(monkeypatch):
    """Agent uses VLM_BASE_URL and VLM_MODEL from environment."""
    monkeypatch.setenv("VLM_BASE_URL", "http://custom.example.com/v1")
    monkeypatch.setenv("VLM_MODEL", "custom-model")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.setenv("VLM_PROVIDER", "custom")

    agent = AIObservationAgent()
    assert agent.base_url == "http://custom.example.com/v1"
    assert agent.model == "custom-model"


@pytest.mark.asyncio
async def test_propose_observation_parses_llm_response(monkeypatch):
    """propose_observation calls LLM and parses JSON response into ObservationRecord."""
    monkeypatch.setenv("VLM_BASE_URL", "http://test.example.com/v1")
    monkeypatch.setenv("VLM_MODEL", "test-model")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.setenv("VLM_PROVIDER", "test")

    agent = AIObservationAgent()

    # Mock httpx.AsyncClient.post to return a valid LLM response
    mock_response = mock.Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "tower": 3,
                    "date_str": "09/23/2026",
                    "hour": 14,
                    "minutes_past_hour": 20,
                    "num_adults": 5,
                    "nesting_stage": "nst",
                    "bill_use": ["fd"],
                    "flights": ["in"],
                    "num_near_nest": 2,
                    "awake": "y"
                })
            }
        }]
    }

    with mock.patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        frames = _fake_frames(2)
        context = {"window_id": "T3_09232026_1420"}
        record = await agent.propose_observation(frames, context)

        # Verify the HTTP call was made to correct endpoint
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "http://test.example.com/v1/chat/completions"
        assert kwargs["json"]["model"] == "test-model"
        assert len(kwargs["json"]["messages"]) == 2
        assert kwargs["json"]["messages"][0]["role"] == "system"

        # Verify the parsed record
        assert isinstance(record, ObservationRecord)
        assert record.tower == 3
        assert record.num_adults == 5
        assert record.nesting_stage == "nst"
        assert record.bill_use == ["fd"]
        assert record.flights == ["in"]
        assert record.num_near_nest == 2
        assert record.awake == "y"


@pytest.mark.asyncio
async def test_propose_observation_handles_llm_error(monkeypatch):
    """propose_observation handles HTTP errors from LLM endpoint."""
    monkeypatch.setenv("VLM_BASE_URL", "http://test.example.com/v1")
    monkeypatch.setenv("VLM_MODEL", "test-model")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.setenv("VLM_PROVIDER", "test")

    agent = AIObservationAgent()

    # Mock httpx to raise an HTTP error
    mock_response = mock.Mock()
    mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
        "500 Server Error", request=mock.Mock(), response=mock.Mock()
    )

    with mock.patch("httpx.AsyncClient.post", return_value=mock_response):
        frames = _fake_frames(1)
        context = {"window_id": "T1_09232026_1200"}

        with pytest.raises(httpx.HTTPStatusError):
            await agent.propose_observation(frames, context)


@pytest.mark.asyncio
async def test_propose_observation_handles_invalid_json(monkeypatch):
    """propose_observation handles invalid JSON from LLM."""
    monkeypatch.setenv("VLM_BASE_URL", "http://test.example.com/v1")
    monkeypatch.setenv("VLM_MODEL", "test-model")
    monkeypatch.setenv("VLM_API_KEY", "test-key")
    monkeypatch.setenv("VLM_PROVIDER", "test")

    agent = AIObservationAgent()

    # Mock httpx to return response with invalid JSON
    mock_response = mock.Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": "This is not JSON"
            }
        }]
    }

    with mock.patch("httpx.AsyncClient.post", return_value=mock_response):
        frames = _fake_frames(1)
        context = {"window_id": "T1_09232026_1200"}

        with pytest.raises(ValueError, match="Failed to parse JSON"):
            await agent.propose_observation(frames, context)