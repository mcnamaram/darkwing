"""End-to-end pipeline test for the VLM agent integration.

Verifies the full flow: detection -> VLM agent -> ObservationRecord.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from unittest import mock

import pytest

from darkwing.agent import AIObservationAgent
from darkwing.schema import ObservationRecord


@pytest.fixture
def ollama_env(monkeypatch):
    """Set up Ollama environment variables."""
    monkeypatch.setenv("VLM_BASE_URL", "http://localhost:11434/v1")
    monkeypatch.setenv("VLM_MODEL", "gemma4:12b")
    monkeypatch.setenv("VLM_API_KEY", "ollama")
    monkeypatch.setenv("VLM_PROVIDER", "ollama")


@pytest.mark.asyncio
async def test_full_pipeline_with_mocked_ollama(ollama_env, tmp_path):
    """Test the complete VLM pipeline: detection -> agent -> record."""
    fake_frames = [b"\xff\xd8fakejpg1\xff\xd9", b"\xff\xd8fakejpg2\xff\xd9"]

    agent = AIObservationAgent()
    assert agent.provider == "ollama"
    assert agent.base_url == "http://localhost:11434/v1"
    assert agent.model == "gemma4:12b"

    mock_response = mock.Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [{
            "message": {
                "content": json.dumps({
                    "tower": 3,
                    "date_str": "06/15/2026",
                    "hour": 6,
                    "minutes_past_hour": 0,
                    "num_adults": 2,
                    "nesting_stage": "nst",
                    "bill_use": ["fd"],
                    "flights": ["in"],
                    "num_near_nest": 1,
                    "awake": "y"
                })
            }
        }]
    }

    with mock.patch("httpx.AsyncClient.post", return_value=mock_response) as mock_post:
        context = {"window_id": "T3_06152026_0600"}
        record = await agent.propose_observation(fake_frames, context)

        mock_post.assert_called_once()
        call_url = mock_post.call_args[0][0]
        assert call_url == "http://localhost:11434/v1/chat/completions"

        payload = mock_post.call_args[1]["json"]
        assert payload["model"] == "gemma4:12b"
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"

        assert isinstance(record, ObservationRecord)
        assert record.tower == 3
        assert record.num_adults == 2
        assert record.nesting_stage == "nst"
        assert record.bill_use == ["fd"]
        assert record.flights == ["in"]
        assert record.num_near_nest == 1
        assert record.awake == "y"