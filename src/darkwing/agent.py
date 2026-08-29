"""MVP3 Phase 2: VLM agent client for observation proposals.

Lightweight stdlib (urllib) REST client — no SDK bloat (REQ-6). Talks to
Gemini, sends downscaled keyframes + context, enforces the ObservationRecord
JSON schema on the response, returns a validated record.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from typing import Any, Dict, List, Optional

from darkwing.schema import ObservationRecord

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

SYSTEM_PROMPT = (
    "You are an expert ornithologist analyzing Chimney Swift nesting tower "
    "footage. Propose one observation record for the 60-second window shown. "
    "Output strict JSON matching the provided schema. Short-code maps:\n"
    " nesting_stage: no,bld,egg,nst,fld\n"
    " bill_use: na,mat,fd,egg,nst,ps,po,oth\n"
    " flights: in,out,chg,non\n"
    " awake: y,n,mbe,nap\n"
    " num_adults 0-10; num_near_nest 0-5 (0=NA). minutes_past_hour in 0,20,40."
)


def _b64(frames: List[bytes]) -> List[str]:
    return [base64.b64encode(f).decode("ascii") for f in frames]


def _gemini_payload(frames: List[bytes], ctx: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    parts: List[Dict[str, Any]] = [{"text": SYSTEM_PROMPT}, {"text": f"Window context: {json.dumps(ctx)}"}]
    for b in _b64(frames):
        parts.append({"inline_data": {"mime_type": "image/jpeg", "data": b}})
    return {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
        },
    }


def _extract_text(resp: Dict[str, Any]) -> str:
    return resp["candidates"][0]["content"]["parts"][0]["text"]


class AIObservationAgent:
    """Thin VLM client: keyframes + context -> validated ObservationRecord."""

    def __init__(self, api_key: Optional[str] = None, provider: Optional[str] = None) -> None:
        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise ValueError("No VLM API key: set GEMINI_API_KEY.")
        self.api_key = key
        self.provider = provider or "gemini"

    async def _post(self, url: str, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        # Using run_in_executor to make sync urllib call awaitable
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._sync_post, url, payload, headers)

    def _sync_post(self, url: str, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        req = urllib.request.Request(
            url, data=json.dumps(payload).encode(), headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=60) as r:  # noqa: S310 ( trusted URL )
            return json.loads(r.read().decode())

    async def propose_observation(
        self, frames: List[bytes], context_metadata: Dict[str, Any]
    ) -> ObservationRecord:
        schema = ObservationRecord.model_json_schema()
        if self.provider == "gemini":
            payload = _gemini_payload(frames, context_metadata, schema)
            url = f"{GEMINI_URL}?key={self.api_key}"
            headers = {"Content-Type": "application/json"}
        else:
            raise ValueError(f"Provider {self.provider} not supported.")
        resp = await self._post(url, payload, headers)
        text = _extract_text(resp)
        return ObservationRecord(**json.loads(text))
