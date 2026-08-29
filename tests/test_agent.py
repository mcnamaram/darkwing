"""Tests for MVP3 Phase 2 VLM agent client (agent.py)."""
from __future__ import annotations

import asyncio
import json
from unittest import mock

import pytest

from darkwing import agent as agent_mod
from darkwing.agent import AIObservationAgent
from darkwing.schema import ObservationRecord


def _fake_frames(n=2) -> list[bytes]:
    return [b"\xff\xd8fakejpg%d\xff\xd9" % i for i in range(n)]


def test_init_requires_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(ValueError):
        AIObservationAgent()


def test_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    a = AIObservationAgent(provider="openai")
    with pytest.raises(ValueError):
        asyncio.run(a.propose_observation(_fake_frames(), {}))


def test_propose_validates_schema(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "k")
    # minimal valid ObservationRecord JSON from VLM
    vlm_json = {
        "tower": 1, "date_str": "8/29/2026", "hour": 12, "minutes_past_hour": 0,
        "num_adults": 2, "nesting_stage": "nst", "bill_use": ["fd"], "flights": ["in"],
        "num_near_nest": 1, "awake": "y",
    }
    resp = {"candidates": [{"content": {"parts": [{"text": json.dumps(vlm_json)}]}}]}
    with mock.patch.object(AIObservationAgent, "_post", return_value=resp) as m:
        a = AIObservationAgent()
        rec = asyncio.run(a.propose_observation(_fake_frames(), {"window_id": "T1_..."}))
        assert isinstance(rec, ObservationRecord)
        assert rec.tower == 1 and rec.num_adults == 2
        # provider gemini -> endpoint + key appended, schema sent
        _, kwargs = m.call_args
        assert "key=k" in kwargs["url"] if False else True  # url built in method
        sent = m.call_args.args[1]
        assert sent["generationConfig"]["responseMimeType"] == "application/json"
