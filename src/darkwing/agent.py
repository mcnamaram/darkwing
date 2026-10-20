"""MVP3 Phase 2: VLM agent client for observation proposals.

Provider-agnostic agent using OpenAI-compatible API format.
Works with any provider (Ollama, OpenRouter, vLLM, llama.cpp, LM Studio, etc.)
that exposes a /v1/chat/completions endpoint.
"""
from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any, Dict, List, Optional

import httpx
from dotenv import load_dotenv

load_dotenv()

from darkwing.schema import ObservationRecord

# Trace logging
_TRACING_ENABLED = os.environ.get('DARKWING_TRACE_AGENT', '').lower() in ('1', 'true', 'yes')
_logger = logging.getLogger(__name__)
if _TRACING_ENABLED:
    if not _logger.handlers:
        _handler = logging.StreamHandler()
        _handler.setFormatter(logging.Formatter('[AGENT] %(message)s'))
        _logger.addHandler(_handler)
        _logger.setLevel(logging.DEBUG)
    _logger.propagate = False  # avoid duplicate output via root logger


def _trace(msg: str) -> None:
    """Emit a trace message when DARKWING_TRACE_AGENT=1."""
    if _TRACING_ENABLED:
        _logger.debug(msg)

# System prompt for Chimney Swift observation analysis
SYSTEM_PROMPT = """You are an expert ornithologist analyzing Chimney Swift nesting tower footage.
Propose one observation record for the 60-second window shown. Output strict JSON matching the provided schema.
Short-code maps:
nesting_stage: no,bld,egg,nst,fld
bill_use: na,mat,fd,egg,nst,ps,po,oth
flights: in,out,chg,non
awake: y,n,mbe,nap
num_adults 0-10; num_near_nest 0-5 (0=NA). minutes_past_hour in 0,20,40."""


def _b64(frames: List[bytes]) -> List[str]:
    """Encode JPEG frames to base64 strings."""
    return [base64.b64encode(f).decode("ascii") for f in frames]


class AIObservationAgent:
    """Provider-agnostic VLM client: frames + context -> ObservationRecord.

    Reads configuration from environment variables:
    - VLM_BASE_URL: OpenAI-compatible API endpoint
    - VLM_MODEL: Model identifier
    - VLM_API_KEY: API key
    - VLM_PROVIDER: Human-readable provider label
    """

    def __init__(self, provider: Optional[str] = None) -> None:
        # Read all required config from environment
        self.base_url = os.getenv("VLM_BASE_URL")
        self.model = os.getenv("VLM_MODEL")
        self.api_key = os.getenv("VLM_API_KEY")
        env_provider = os.getenv("VLM_PROVIDER")

        # Provider parameter overrides env, but env is required by default
        self.provider = provider or env_provider

        if not self.base_url:
            raise ValueError("VLM_BASE_URL environment variable is required")
        if not self.model:
            raise ValueError("VLM_MODEL environment variable is required")
        if not self.api_key:
            raise ValueError("VLM_API_KEY environment variable is required")
        if not self.provider:
            raise ValueError("VLM_PROVIDER environment variable is required")

    async def _post(
        self,
        client: httpx.AsyncClient,
        messages: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Make async POST request to the LLM endpoint."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 1000,
            "temperature": 0.1,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        response = await client.post(
            f"{self.base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=60.0,
        )
        response.raise_for_status()
        return response.json()

    async def propose_observation(
        self, frames: List[bytes], context_metadata: Dict[str, Any]
    ) -> ObservationRecord:
        """Propose an observation by analyzing frames with the VLM.

        Args:
            frames: JPEG-encoded frame bytes
            context_metadata: Additional context (tower, date, hour, etc.)

        Returns:
            ObservationRecord validated against the schema
        """
        if not frames:
            raise ValueError("No frames provided for observation proposal")

        # Build the messages payload
        # For VLM agents, we send context + base64 frames as part of user message
        # Many providers accept image_url with base64 data
        images_b64 = _b64(frames)

        # Construct user content: context metadata + image frames
        user_content: Dict[str, Any] = {
            "type": "text",
            "text": f"Window context (additional metadata): {json.dumps(context_metadata)}",
        }

        # For providers that support vision (Ollama, OpenAI GPT-4V), include image frames
        # For providers without vision, the frames are just metadata for context
        content_items: List[Dict[str, Any]] = [user_content]

        # Add image frames as base64-encoded content
        # Ollama's OpenAI-compatible endpoint requires data URI prefix: data:image/jpeg;base64,<b64>
        for img_b64 in images_b64[:5]:  # Limit to 5 frames to control token count
            content_items.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                }
            )

        messages: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": content_items,
            },
        ]

        # Make the async HTTP request using httpx
        async with httpx.AsyncClient() as client:
            response = await self._post(client, messages)

        # Extract JSON from the model's response
        choices = response.get("choices", [])
        if not choices:
            raise ValueError("No choices in LLM response")

        msg = choices[0].get("message", {})

        # Try content first, then reasoning field (some reasoning models like gemma4
        # put the final output in reasoning rather than content)
        message_content = msg.get("content", "")
        if not message_content:
            message_content = msg.get("reasoning", "")
        if not message_content:
            raise ValueError(
                "No content in LLM response message "
                f"(tried 'content' and 'reasoning' fields; message keys: {list(msg.keys())})"
            )

        # Debug: print raw content for troubleshooting
        _trace(f"VLM raw response content: {message_content[:200]}...")

        # Parse the JSON response from the model
        try:
            # Find JSON in the response (handles optional text before/after)
            json_str = message_content.strip()
            if not json_str.startswith("{"):
                # Try to find JSON in the response
                start = message_content.find("{")
                end = message_content.rfind("}") + 1
                if start >= 0 and end > start:
                    json_str = message_content[start:end]
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse JSON from LLM response: {e}")

        # Merge context fields the VLM may have missed
        # Context keys: tower, date, hour, minute, detector_version
        # Schema fields: tower, date_str, hour, minutes_past_hour
        if "tower" not in data and "tower" in context_metadata:
            data["tower"] = context_metadata["tower"]
        if "date_str" not in data and "date" in context_metadata:
            data["date_str"] = context_metadata["date"]
        if "hour" not in data and "hour" in context_metadata:
            data["hour"] = context_metadata["hour"]
        if "minutes_past_hour" not in data and "minute" in context_metadata:
            data["minutes_past_hour"] = context_metadata["minute"]

        # Validate against the ObservationRecord schema
        record = ObservationRecord.model_validate(data)
        return record


def get_adapter() -> AIObservationAgent:
    """Factory: returns instantiated AIObservationAgent for the configured provider."""
    return AIObservationAgent()


def create_agent() -> AIObservationAgent:
    """Factory: returns an AIObservationAgent instance (alias for get_adapter)."""
    return get_adapter()