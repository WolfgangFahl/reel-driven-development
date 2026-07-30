"""Created on 2026-07-30.

@author: wf
"""

from typing import Optional

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore


class VideoSegment:
    """A time segment of a video file with frame access by timestamp."""

    def __init__(self, path: str, start: float = 0.0, end: Optional[float] = None):
        """Open the video and fix the segment bounds.

        Args:
            path: path of the video file.
            start: segment start in seconds.
            end: segment end in seconds; defaults to the video duration.

        Raises:
            ImportError: if OpenCV is not available.
            ValueError: if the video cannot be opened.
        """
        if cv2 is None:
            raise ImportError("opencv is required for VideoSegment")
        self.path = path
        self.cap = cv2.VideoCapture(path)
        if not self.cap.isOpened():
            raise ValueError(f"can not open video {path}")
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_count = self.cap.get(cv2.CAP_PROP_FRAME_COUNT)
        self.video_duration = frame_count / self.fps if frame_count else 0.0
        self.start = start
        self.end = end if end is not None else self.video_duration
        self.frame_step = 1.0 / self.fps

    def frame_at(self, time_sec: float) -> Optional[np.ndarray]:
        """Read the frame at the given absolute video time.

        Args:
            time_sec: absolute time in seconds, clamped to the segment.

        Returns:
            the BGR frame array or None if the read failed.
        """
        frame = None
        clamped = min(max(time_sec, self.start), self.end)
        self.cap.set(cv2.CAP_PROP_POS_MSEC, clamped * 1000.0)
        ok, img = self.cap.read()
        if ok:
            frame = img
        return frame

    def duration(self) -> float:
        """Return the segment duration in seconds."""
        seconds = self.end - self.start
        return seconds

    def close(self) -> None:
        """Release the underlying video capture."""
        self.cap.release()
