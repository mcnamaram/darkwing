"""Pydantic AI VLM agent client for observation proposals.

Pydantic AI agent using Ollama/OpenRouter provider via Pydantic's NativeOutput.
Provides structured bird presence detection and full observation proposals with
built-in validation and retry logic.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
load_dotenv()  # load .env variables (e.g. LOGFIRE_TOKEN)

from pydantic import BaseModel, Field
from pydantic_ai import Agent, NativeOutput, ModelRetry, RunContext
from pydantic_ai.models.ollama import OllamaModel
from pydantic_ai.providers.ollama import OllamaProvider
from pydantic_ai import messages

import logfire
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

# Binary system prompt for bird-presence detection (uncertainty resolution only).
BINARY_SYSTEM_PROMPT = """You are an expert ornithologist reviewing surveillance footage.
Your only task: answer YES or NO — are one or more Chimney Swifts or other birds visible in the observation window?
Answer with exactly one word: YES or NO. Do not include any explanation or reasoning.

Use high confidence when the bird is clearly visible and persistent. Use lower
confidence when the bird is brief, small, or partially obscured. Only answer YES
when you are confident a bird is present. Only answer NO when you are confident
no bird is present."""

# Bird detection result for binary check (replaces AIObservationAgent.detect_bird)
class BirdDetection(BaseModel):
    """Binary bird presence check result."""
    bird_present: bool = Field(
        description="Are one or more Chimney Swifts or other birds visible?"
    )
    confidence: float = Field(ge=0.0, le=1.0, description="Detection confidence 0-1")

# Initialize Logfire for observability (defensive - don't fail import if not configured)
try:
    logfire.configure()
    logfire.instrument_pydantic_ai()       # full agent run traces
    logfire.instrument_httpx(capture_all=True)  # raw prompts/responses for debugging
except Exception:
    # Logfire not configured - continue without observability
    pass

# Agent for full observation proposal
observation_agent = Agent(
    model=OllamaModel(
        model_name=os.getenv("VLM_MODEL", "qwen3-vl:8b"),
        provider=OllamaProvider(base_url=os.getenv("VLM_BASE_URL", "http://localhost:11434/v1")),
    ),
    name='chimney_swift_observation_agent',
    instructions=SYSTEM_PROMPT,
    output_type=NativeOutput(ObservationRecord),
    retries={'output': 2, 'invalid_json': 2},
)

# Agent for binary bird presence check
binary_agent = Agent(
    model=OllamaModel(
        model_name=os.getenv("VLM_MODEL", "qwen3-vl:8b"),
        provider=OllamaProvider(base_url=os.getenv("VLM_BASE_URL", "http://localhost:11434/v1")),
    ),
    name='binary_bird_presence_agent',
    instructions=BINARY_SYSTEM_PROMPT,
    output_type=NativeOutput(BirdDetection),
    retries={'output': 1, 'invalid_json': 1},
)

# Output validators (business logic at boundary)
@observation_agent.output_validator
async def validate_observation_logic(ctx: RunContext[None], output: ObservationRecord) -> ObservationRecord:
    """Enforce ornithological invariants that the VLM might miss."""
    # 1. If num_adults > 0, at least one flight code must make sense
    if output.num_adults > 0 and not output.flights:
        raise ModelRetry("num_adults > 0 but flights list is empty. Add 'in' or 'out' or 'non'.")

    # 2. Nesting stage consistency: if egg/nst/fld, num_near_nest should be > 0
    if output.nesting_stage in ('egg', 'nst', 'fld') and output.num_near_nest == 0:
        # Allow but warn — might be eggs/nestlings not visible
        pass  # soft constraint, not a hard retry

    return output

# Minimum confidence threshold for VLM to confirm bird presence.
# Below this threshold, the VLM is uncertain and we don't promote SKIP→REVIEW.
VLM_CONFIDENCE_THRESHOLD = float(os.environ.get('VLM_CONFIDENCE_THRESHOLD', '0.6'))

@binary_agent.output_validator
async def validate_bird_detection(ctx: RunContext[None], output: BirdDetection) -> BirdDetection:
    """Sanity-check the binary detection.

    Reject low-confidence positive detections (bird_present=True below threshold),
    but allow high-confidence negatives (bird_present=False with any confidence)
    so Phase 1 demotion (REVIEW/MANUAL→SKIP) can confidently remove false positives.
    """
    if output.bird_present and output.confidence < VLM_CONFIDENCE_THRESHOLD:
        raise ModelRetry(
            f"bird_present=True with low confidence ({output.confidence}). "
            f"Either raise confidence or set bird_present=False."
        )
    return output

def _build_user_prompt(frames: List[bytes], context: Dict, label: str) -> list:
    """Convert JPEG frames + context metadata into a pydantic AI user prompt.

    Pydantic AI 2.x expects the user_prompt argument to be either a string or a
    sequence of UserContent items (BinaryImage, TextContent, ImageUrl, etc.).
    The keyword argument `prompt=` is no longer accepted — pass positionally.
    """
    parts = [messages.TextContent(content=f"{label} Window context: {json.dumps(context)}")]
    for frame in frames:
        parts.append(messages.BinaryImage(data=frame, media_type="image/jpeg"))
    return parts


# Service layer functions for detector integration
def detect_bird_presence(frames: List[bytes], context: Dict) -> bool:
    """Binary bird presence check — called when detector is uncertain (SKIP with blobs,
    or borderline cases). Uses the fast binary agent.

    Integration: detector.py classify_window() verdict MANUAL/SKIP with blobs -> call this
    """
    try:
        result = binary_agent.run_sync(
            _build_user_prompt(frames, context, "Binary bird check:")
        )
        return result.output.bird_present
    except Exception as exc:
        try:
            logfire.error("Binary bird detection failed", exc_info=exc, context=context)
        except Exception:
            pass
        # Fail-safe: if VLM fails, default to NO (don't auto-detect birds)
        return False

def propose_observation(frames: List[bytes], context: Dict) -> ObservationRecord:
    """Full observation proposal — called for REVIEW windows after frame extraction.
    Returns validated ObservationRecord ready for CSV/form submission.

    Integration: agent_payload.py extract_motion_frames() -> frames -> this function
    """
    try:
        result = observation_agent.run_sync(
            _build_user_prompt(frames, context, "Observation proposal:")
        )
        record: ObservationRecord = result.output  # validated by NativeOutput + validator
        return record
    except Exception as exc:
        try:
            logfire.error("Observation proposal failed", exc_info=exc, context=context)
        except Exception:
            pass
        # Fail-safe: return minimal valid record with context defaults
        return _fallback_observation(context)

def _fallback_observation(context: Dict) -> ObservationRecord:
    """Construct a minimal valid record when VLM fails."""
    from datetime import datetime
    date = context.get('date', datetime.now().strftime('%m/%d/%Y'))
    hour = context.get('hour', 12)
    minute = context.get('minute', 0)
    # Snap minute to 0, 20, 40
    snapped = min([0, 20, 40], key=lambda m: abs(m - minute))
    return ObservationRecord(
        tower=context.get('tower', 1),
        date_str=date,
        hour=hour,
        minutes_past_hour=snapped,
        num_adults=0,
        nesting_stage='no',
        bill_use=['na'],
        flights=['non'],
        num_near_nest=0,
        awake='nap',
        notes='VLM failed; auto-generated fallback',
    )

# Factory functions (backwards compatible with existing code)
def get_adapter() -> Agent:
    """Factory: returns observation proposal agent — replaces AIObservationAgent."""
    return observation_agent

def create_agent() -> Agent:
    """Factory: returns an observation proposal agent instance (alias for get_adapter)."""
    return get_adapter()

# For backwards compatibility with cli.py's vlm_agent type annotation
# The CLI expects an AIObservationAgent instance with detect_bird and propose_observation methods
class VLMClientAdapter:
    """Adapter for backwards compatibility with existing cli.py code.

    This class provides the detect_bird and propose_observation methods
    expected by the existing code while using the new Pydantic AI backend.
    """

    async def detect_bird(
        self, frames: List[bytes], context_metadata: Dict[str, Any]
    ) -> tuple[bool, float]:
        """Binary bird detection with confidence (for Phase 0 uncertainty resolution).

        Returns (bird_present, confidence) where bird_present is bool and
        confidence is 0.0–1.0.
        """
        result = await binary_agent.run(
            _build_user_prompt(frames, context_metadata, "Binary bird check:")
        )
        output = result.output
        return output.bird_present, output.confidence

    async def propose_observation(self, frames: List[bytes], context_metadata: Dict[str, Any]) -> ObservationRecord:
        """Observation proposal for backwards compatibility."""
        result = await observation_agent.run(
            _build_user_prompt(frames, context_metadata, "Observation proposal:")
        )
        return result.output

# Create adapter instance for backwards compatibility
vlm_client_adapter = VLMClientAdapter()