"""Created on 2026-08-08.

hop detection by bisection over a reel

@author: wf
"""

import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Tuple

from rdd.frame import Frame, FrameChange, Reel
from rdd.recording import HopContent, HopContents


@dataclass
class Bracket:
    """A content change captured between two frames.

    Issue #1 requires every change to be bracketed by a captured frame
    before it and a captured frame after it. A bracket is that pair: the
    change happened after before and not later than after, and the two
    frames are the evidence of both sides.
    """

    before: Frame
    after: Frame
    score: float

    @property
    def start_sec(self) -> float:
        """Position of the frame before the change in seconds."""
        start_sec = self.before.time_sec
        return start_sec

    @property
    def end_sec(self) -> float:
        """Position of the frame after the change in seconds."""
        end_sec = self.after.time_sec
        return end_sec

    @property
    def width_sec(self) -> float:
        """How closely the change is bracketed, in seconds."""
        width_sec = self.end_sec - self.start_sec
        return width_sec

    @property
    def timecode(self) -> str:
        """The bracket as a readable time range."""
        timecode = f"{self.before.timecode}-{self.after.timecode}"
        return timecode


@dataclass
class Finding:
    """One result of a detection, valid on its own.

    The detector reports findings while it runs instead of returning a
    result at the end, so a caller can judge the run and use what is known
    so far at any moment - see discussions #11 and #12.
    """

    kind: str
    start_sec: float
    end_sec: float
    score: float = 0.0
    bracket: Optional[Bracket] = None


@dataclass
class Coverage:
    """What a run knows about itself at a given moment."""

    total_sec: float = 0.0
    resolved_sec: float = 0.0
    open_intervals: int = 0
    frames_read: int = 0
    brackets: int = 0

    @property
    def fraction(self) -> float:
        """Fraction of the segment that is resolved."""
        fraction = 0.0
        if self.total_sec > 0:
            fraction = self.resolved_sec / self.total_sec
        return fraction


class BisectionHopDetector:
    """Find the content changes of a reel by bisection.

    A linear sweep decodes every frame to find the few positions where the
    content changes - measured over an internal corpus, about two per
    minute. The bisection instead probes, compares and refines only where
    two probes differ, so the cost follows the number of changes rather
    than the length of the reel.

    Two properties keep the cost down:

    * probes are snapped to key frames where an index is available, since
      those are the positions that seek without decoding forward
    * refinement stops at min_gap_sec, because a hop is a human act and
      hop boundaries can not lie closer together than a human can act
    """

    def __init__(
        self,
        reel: Reel,
        frame_change: Optional[FrameChange] = None,
        min_gap_sec: float = 0.4,
        on_finding: Optional[Callable[[Finding], None]] = None,
    ):
        """Initialize the detector.

        Args:
            reel: the reel to analyze.
            frame_change: the change criterion; defaults to FrameChange().
            min_gap_sec: refinement floor in seconds - the shortest interval
                a hop boundary is refined to.
            on_finding: called with every Finding as it is made.
        """
        self.reel = reel
        self.frame_change = frame_change if frame_change is not None else FrameChange()
        self.min_gap_sec = min_gap_sec
        self.on_finding = on_finding
        self.coverage = Coverage()
        self.brackets: List[Bracket] = []
        self._cache: Dict[int, Frame] = {}

    @property
    def min_gap_frames(self) -> int:
        """The refinement floor in frames."""
        min_gap_frames = max(1, int(round(self.min_gap_sec * self.reel.fps)))
        return min_gap_frames

    def frame_at(self, frame_num: int) -> Optional[Frame]:
        """Read a frame once and remember it.

        Args:
            frame_num: the frame number to read.

        Returns:
            the Frame or None past the end of the reel.
        """
        frame = self._cache.get(frame_num)
        if frame is None:
            frame = self.reel.frame_at(frame_num)
            if frame is not None:
                self._cache[frame_num] = frame
                self.coverage.frames_read += 1
        return frame

    def report(self, finding: Finding):
        """Report a finding to the caller.

        Args:
            finding: the finding to report.
        """
        self.coverage.resolved_sec += finding.end_sec - finding.start_sec
        if finding.bracket is not None:
            self.brackets.append(finding.bracket)
            self.coverage.brackets += 1
        if self.on_finding is not None:
            self.on_finding(finding)

    def probes_of(self, start_frame: int, end_frame: int) -> List[int]:
        """Choose the positions of the first sweep.

        The key frames inside the segment are the cheap probes; the segment
        bounds are always probed so that the whole segment is covered.

        Args:
            start_frame: first frame of the segment.
            end_frame: last frame of the segment.

        Returns:
            the ascending list of probe positions.
        """
        positions = {start_frame, end_frame}
        for frame_num in self.reel.keyframes:
            if start_frame < frame_num < end_frame:
                positions.add(frame_num)
        probes = sorted(positions)
        return probes

    def changed(self, frame_a: Frame, frame_b: Frame) -> Tuple[bool, float]:
        """Compare two frames.

        Args:
            frame_a: the earlier frame.
            frame_b: the later frame.

        Returns:
            whether the content changed, and the score.
        """
        score = self.frame_change.score(frame_a, frame_b)
        is_changed = score >= self.frame_change.threshold
        result = (is_changed, score)
        return result

    def bisect(self, frame_a: Frame, frame_b: Frame, score: float):
        """Refine an interval known to contain a change.

        Args:
            frame_a: frame at the start of the interval.
            frame_b: frame at the end of the interval.
            score: the score of the two frames.
        """
        gap = frame_b.frame_num - frame_a.frame_num
        if gap <= self.min_gap_frames:
            bracket = Bracket(before=frame_a, after=frame_b, score=score)
            self.report(
                Finding(
                    kind="bracket",
                    start_sec=bracket.start_sec,
                    end_sec=bracket.end_sec,
                    score=score,
                    bracket=bracket,
                )
            )
        else:
            middle = self.frame_at(frame_a.frame_num + gap // 2)
            if middle is None:
                bracket = Bracket(before=frame_a, after=frame_b, score=score)
                self.report(
                    Finding(
                        kind="bracket",
                        start_sec=bracket.start_sec,
                        end_sec=bracket.end_sec,
                        score=score,
                        bracket=bracket,
                    )
                )
            else:
                self.resolve(frame_a, middle)
                self.resolve(middle, frame_b)

    def resolve(self, frame_a: Frame, frame_b: Frame):
        """Decide an interval: unchanged, or refine it.

        Args:
            frame_a: frame at the start of the interval.
            frame_b: frame at the end of the interval.
        """
        is_changed, score = self.changed(frame_a, frame_b)
        start_sec = self.reel.time_of(frame_a.frame_num)
        end_sec = self.reel.time_of(frame_b.frame_num)
        if is_changed:
            self.bisect(frame_a, frame_b, score)
        else:
            self.report(
                Finding(
                    kind="unchanged",
                    start_sec=start_sec,
                    end_sec=end_sec,
                    score=score,
                )
            )

    def detect(
        self, start_sec: float = 0.0, end_sec: Optional[float] = None
    ) -> List[Bracket]:
        """Detect the content changes of a segment of the reel.

        Args:
            start_sec: start of the segment in seconds.
            end_sec: end of the segment in seconds; None means the end of
                the reel.

        Returns:
            the brackets found, ascending by position.

        Raises:
            ValueError: if the segment lies outside the reel.
        """
        if end_sec is None:
            end_sec = self.reel.duration_sec
        if start_sec < 0 or end_sec > self.reel.duration_sec or start_sec >= end_sec:
            raise ValueError(
                f"segment {start_sec}-{end_sec} is not inside the "
                f"reel 0-{self.reel.duration_sec:.2f}"
            )
        self.coverage = Coverage(total_sec=end_sec - start_sec)
        self.brackets = []
        start_frame = self.reel.frame_num_of(start_sec)
        end_frame = min(self.reel.frame_num_of(end_sec), self.reel.frame_count - 1)
        probes = self.probes_of(start_frame, end_frame)
        frames = [self.frame_at(frame_num) for frame_num in probes]
        pairs = [
            (frames[i], frames[i + 1])
            for i in range(len(frames) - 1)
            if frames[i] is not None and frames[i + 1] is not None
        ]
        self.coverage.open_intervals = len(pairs)
        for frame_a, frame_b in pairs:
            self.resolve(frame_a, frame_b)
            self.coverage.open_intervals -= 1
        self.brackets.sort(key=lambda bracket: bracket.before.frame_num)
        brackets = self.brackets
        return brackets

    def groups_of(self, settle_sec: float = 1.0) -> List[List[Bracket]]:
        """Group the brackets into hops.

        A hop is a state the walk arrives at, not a single change: opening
        a page, scrolling it and letting it render is one arrival made of
        many changes. Brackets therefore belong to the same hop while they
        keep following each other, and a new hop starts only after the
        content has stayed still for settle_sec.

        Args:
            settle_sec: seconds without change that end a hop.

        Returns:
            the brackets grouped per hop, in order.
        """
        groups: List[List[Bracket]] = []
        for bracket in self.brackets:
            is_new = True
            if groups:
                previous = groups[-1][-1]
                is_new = bracket.start_sec - previous.end_sec >= settle_sec
            if is_new:
                groups.append([bracket])
            else:
                groups[-1].append(bracket)
        return groups

    def hops(
        self, settle_sec: float = 1.0, out_dir: Optional[str] = None
    ) -> HopContents:
        """Turn the brackets into hop records with an evidence frame each.

        The evidence frame of a hop is the frame at which its content has
        settled - the state the walk arrived at, not the blur on the way
        there. node, url and summary of the walk stay empty: they come from
        the transcript and are never guessed from the picture.

        Args:
            settle_sec: seconds without change that end a hop.
            out_dir: directory the evidence frames are written to; None
                writes no frames and leaves the screenshot empty.

        Returns:
            the hops of this run.
        """
        hop_contents = HopContents(recording=self.reel.videoFile)
        for group in self.groups_of(settle_sec):
            settled = group[-1].after
            pos = len(hop_contents.hops) + 1
            screenshot = None
            if out_dir is not None:
                os.makedirs(out_dir, exist_ok=True)
                screenshot = f"hop{pos:02d}.jpg"
                settled.save(os.path.join(out_dir, screenshot))
            max_score = max(bracket.score for bracket in group)
            summary = (
                f"{len(group)} change(s) "
                f"[{group[0].start_sec:.2f}s,{group[-1].end_sec:.2f}s], "
                f"max score {max_score:.1f}, settled at {settled.time_sec:.2f}s"
            )
            hop_contents.add(
                HopContent(
                    time=settled.timecode,
                    summary=summary,
                    screenshot=screenshot,
                )
            )
        return hop_contents
