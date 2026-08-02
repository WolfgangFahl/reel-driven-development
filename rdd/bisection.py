"""Created on 2026-07-30.

@author: wf
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

from rdd.blockmae import BlockMAE
from rdd.progress import ProgressEmitter

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore


@dataclass
class ChangeBracket:
    """A content change bracketed by two sampled frames.

    The change happened between before and after; their distance is at
    most the sampling granularity, so the change is located at frame
    level.
    """

    before: float
    after: float
    score: float


@dataclass
class AbsenceProof:
    """Proof that no content change happened around a target time.

    Records the inspected window and the frames compared so that a no-
    screenshot claim is a proven result, never a sampling artifact.
    """

    target: float
    window: float
    granularity: float
    frames_compared: int


@dataclass
class BisectionResult:
    """Result of a narrative-driven bisection run over a video segment."""

    times: List[float] = field(default_factory=list)
    changes: List[ChangeBracket] = field(default_factory=list)
    absences: List[AbsenceProof] = field(default_factory=list)
    frames_sampled: int = 0


class BisectionSampler:
    """Multi-phase bisection frame sampler per issue #1.

    Phase 1 samples anchor frames (start, middle, end) plus a window
    around every transcript-named target. Phase 2 bisects every adjacent
    differing pair until the change is bracketed at frame granularity.
    Targets with no change in their window yield an AbsenceProof.
    """

    def __init__(
        self,
        segment,
        metric: Optional[BlockMAE] = None,
        granularity: Optional[float] = None,
        target_window: float = 5.0,
        compare_width: int = 640,
        progress: Optional[ProgressEmitter] = None,
    ):
        """Initialize the sampler.

        Args:
            segment: video segment offering frame_at, start, end, frame_step.
            metric: localized change metric; defaults to BlockMAE().
            granularity: minimal interval to bisect; defaults to one frame.
            target_window: seconds sampled around each transcript target.
            compare_width: width frames are downscaled to for comparison.
            progress: progress emitter; defaults to a renderer-less one.
        """
        self.segment = segment
        self.metric = metric if metric is not None else BlockMAE()
        step = granularity if granularity is not None else segment.frame_step
        self.granularity = step * 1.01
        self.target_window = target_window
        self.compare_width = compare_width
        self.progress = progress if progress is not None else ProgressEmitter()
        self.frame_cache: Dict[float, Optional[np.ndarray]] = {}
        self.pair_cache: Dict[Tuple[float, float], float] = {}

    def sample(self, time_sec: float) -> Optional[np.ndarray]:
        """Fetch and cache a downscaled grayscale frame for comparison.

        Args:
            time_sec: absolute video time in seconds.

        Returns:
            the comparison frame or None if unreadable.
        """
        key = round(time_sec, 4)
        if key not in self.frame_cache:
            frame = self.segment.frame_at(time_sec)
            if frame is not None:
                gray = self.metric.to_gray(frame)
                if cv2 is not None and gray.shape[1] > self.compare_width:
                    scale = self.compare_width / gray.shape[1]
                    size = (self.compare_width, int(gray.shape[0] * scale))
                    gray = cv2.resize(gray, size)
                frame = gray
            self.frame_cache[key] = frame
        cached = self.frame_cache[key]
        return cached

    def pair_score(self, time_a: float, time_b: float) -> float:
        """Compute and cache the change score between two sampled times.

        Args:
            time_a: earlier time in seconds.
            time_b: later time in seconds.

        Returns:
            the localized change score; 0.0 if a frame is unreadable.
        """
        key = (round(time_a, 4), round(time_b, 4))
        if key not in self.pair_cache:
            frame_a = self.sample(time_a)
            frame_b = self.sample(time_b)
            score = 0.0
            if frame_a is not None and frame_b is not None:
                score = self.metric.score(frame_a, frame_b)
            self.pair_cache[key] = score
        cached = self.pair_cache[key]
        return cached

    def differs(self, time_a: float, time_b: float) -> bool:
        """Decide whether the frames at two times differ.

        Args:
            time_a: earlier time in seconds.
            time_b: later time in seconds.

        Returns:
            True if the localized change score reaches the threshold.
        """
        is_changed = self.pair_score(time_a, time_b) >= self.metric.threshold
        return is_changed

    def run(self, targets: Optional[List[float]] = None) -> BisectionResult:
        """Run the multi-phase bisection over the segment.

        Args:
            targets: transcript-named mandatory capture times in seconds.

        Returns:
            the BisectionResult with brackets, absence proofs and counts.
        """
        targets = targets if targets is not None else []
        start = self.segment.start
        end = self.segment.end
        anchors = {start, (start + end) / 2.0, end}
        target_times = set()
        for target in targets:
            for offset in (-self.target_window, 0.0, self.target_window):
                target_times.add(min(max(target + offset, start), end))
        self.progress.emit("phase", phase="anchors", total=len(anchors))
        for anchor in sorted(anchors):
            self.sample(anchor)
            self.progress.emit(
                "sample", pos=anchor, frames=len(self.frame_cache), open=0
            )
        self.progress.emit("phase", phase="targets", total=len(target_times))
        for target_time in sorted(target_times):
            self.sample(target_time)
            self.progress.emit(
                "sample", pos=target_time, frames=len(self.frame_cache), open=0
            )
        times = anchors | target_times
        sorted_times = sorted(times)
        self.progress.emit("phase", phase="bisection")
        stable = False
        while not stable:
            stable = True
            inserts = []
            settled = 0
            for time_a, time_b in zip(sorted_times, sorted_times[1:]):
                gap = time_b - time_a
                if self.differs(time_a, time_b):
                    if gap > self.granularity:
                        inserts.append((time_a + time_b) / 2.0)
                    else:
                        settled += 1
                self.progress.emit(
                    "sample",
                    pos=time_a,
                    frames=len(self.frame_cache),
                    open=len(inserts),
                    brackets=settled,
                )
            if inserts:
                stable = False
                times.update(inserts)
                sorted_times = sorted(times)
        changes = []
        for time_a, time_b in zip(sorted_times, sorted_times[1:]):
            if self.differs(time_a, time_b):
                bracket = ChangeBracket(
                    before=time_a,
                    after=time_b,
                    score=self.pair_score(time_a, time_b),
                )
                changes.append(bracket)
                self.progress.emit(
                    "bracket",
                    pos=time_b,
                    before=round(time_a, 3),
                    after=round(time_b, 3),
                    score=round(bracket.score, 2),
                )
        absences = []
        for target in targets:
            lo = min(max(target - self.target_window, start), end)
            hi = min(max(target + self.target_window, start), end)
            in_window = [c for c in changes if lo <= c.after <= hi]
            if in_window:
                self.progress.emit(
                    "target",
                    pos=target,
                    resolution="found",
                    time=round(in_window[0].after, 3),
                )
            else:
                window_times = [t for t in sorted_times if lo <= t <= hi]
                proof = AbsenceProof(
                    target=target,
                    window=self.target_window,
                    granularity=self.granularity,
                    frames_compared=len(window_times),
                )
                absences.append(proof)
                self.progress.emit(
                    "target",
                    pos=target,
                    resolution="absent",
                    window=self.target_window,
                    granularity=round(self.granularity, 4),
                    frames_compared=proof.frames_compared,
                )
        result = BisectionResult(
            times=sorted_times,
            changes=changes,
            absences=absences,
            frames_sampled=len(self.frame_cache),
        )
        return result
