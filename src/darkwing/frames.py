"""Frame sources for the detector.

A frame source is any iterator of ``np.ndarray`` BGR frames. This module
provides a local-file source (OpenCV VideoCapture) used for offline
processing and tests. A camera/RTSP source will implement the same iterator
protocol (plan R7) behind the same factory.

The contract: ``FrameSource`` yields frames; consumers apply ``sample_every``
themselves via :func:`darkwing.detector.iter_frames`.
"""
from __future__ import annotations

import abc
from pathlib import Path
from typing import Iterator, Optional

import cv2
import numpy as np


class FrameSource(abc.ABC):
    @abc.abstractmethod
    def frames(self) -> Iterator[np.ndarray]: ...

    @property
    @abc.abstractmethod
    def fps(self) -> Optional[float]: ...

    def close(self) -> None:  # pragma: no cover - default no-op
        pass


class LocalVideoSource(FrameSource):
    """Reads frames from a local video file (mp4)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        if not self.path.exists():
            raise FileNotFoundError(f"video not found: {self.path}")
        self._cap = cv2.VideoCapture(str(self.path))
        if not self._cap.isOpened():
            raise RuntimeError(f"cannot open video: {self.path}")
        self._fps = self._cap.get(cv2.CAP_PROP_FPS)

    @property
    def fps(self) -> Optional[float]:
        return self._fps or None

    def frames(self) -> Iterator[np.ndarray]:
        while True:
            ok, frame = self._cap.read()
            if not ok or frame is None:
                break
            yield frame

    def close(self) -> None:
        self._cap.release()


class SyntheticSource(FrameSource):
    """Test/demo source: emits generated frames (moving blob, static, glare).

    ``events`` is a list of (frame_index, kind) where kind in
    {"blob", "glare", "static"}. Used by unit tests to exercise the pipeline
    without real footage.
    """

    def __init__(self, n_frames: int = 300, w: int = 320, h: int = 180,
                 events: Optional[list] = None, fps: float = 25.0) -> None:
        self.n = n_frames
        self.w, self.h = w, h
        self.events = events or []
        self._fps = fps

    @property
    def fps(self) -> Optional[float]:
        return self._fps

    def frames(self) -> Iterator[np.ndarray]:
        base = np.full((self.h, self.w, 3), 60, np.uint8)  # grey wall
        for i in range(self.n):
            frame = base.copy()
            for ev_idx, kind in self.events:
                if ev_idx != i:
                    continue
                if kind == "blob":
                    cx = int(self.w * 0.5)
                    cy = int(self.h * 0.5)
                    cv2.circle(frame, (cx, cy), 8, (0, 0, 0), -1)
                elif kind == "glare":
                    frame[:] = 220  # whole-frame brightness jump = glare
            yield frame


def open_source(kind: str, **kwargs) -> FrameSource:
    """Factory (plan R7: camera client behind the same factory later)."""
    if kind == "local":
        return LocalVideoSource(kwargs["path"])
    if kind == "synthetic":
        return SyntheticSource(fps=kwargs.get("fps") or 25.0)
    raise ValueError(f"unknown frame source kind: {kind!r}")
