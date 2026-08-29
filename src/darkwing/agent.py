"""MVP3 Phase 2: VLM agent client for observation proposals.

Lightweight stdlib (urllib) REST client — no SDK bloat (REQ-6). Talks to
Gemini or OpenAI, sends downscaled keyframes + context, enforces the
ObservationRecord JSON schema on the response, returns a validated record.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.request
from typing import Any, Dict, List, Optional

from darkwing.schema import ObservationRecord

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

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


def _openai_payload(frames: List[bytes], ctx: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    content: List[Dict[str, Any]] = [
        {"type": "text", "text": SYSTEM_PROMPT + f"\nWindow context: {json.dumps(ctx)}"}
    ]
    for b in _b64(frames):
        content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}})
    return {
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": content}],
        "response_format": {"type": "json_schema", "json_schema": {"name": "ObservationRecord", "schema": schema, "strict": True}},
    }


def _extract_text(resp: Dict[str, Any], provider: str) -> str:
    if provider == "gemini":
        return resp["candidates"][0]["content"]["parts"][0]["text"]
    return resp["choices"][0]["message"]["content"]


class AIObservationAgent:
    """Thin VLM client: keyframes + context -> validated ObservationRecord."""

    def __init__(self, api_key: Optional[str] = None, provider: Optional[str] = None) -> None:
        key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise ValueError("No VLM API key: set GEMINI_API_KEY or OPENAI_API_KEY.")
        self.api_key = key
        self.provider = provider or ("gemini" if os.environ.get("GEMINI_API_KEY") else "openai")

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
            payload = _openai_payload(frames, context_metadata, schema)
            url = OPENAI_URL
            headers = {"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"}
        resp = await self._post(url, payload, headers)
        text = _extract_text(resp, self.provider)
        return ObservationRecord(**json.loads(text))
