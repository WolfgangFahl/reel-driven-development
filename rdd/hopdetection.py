"""Created on 2026-07-30.

@author: wf
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from rdd.bisection import BisectionResult, BisectionSampler, ChangeBracket
from rdd.blockmae import BlockMAE
from rdd.hop import Hop
from rdd.video import VideoSegment

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore


class HopDetection:
    """Detect hops in a video segment per issue #1.

    Runs the transcript-anchored multi-phase bisection over the segment
    and turns every bracketed content change into a Hop with a
    representative evidence frame.
    """

    def __init__(
        self,
        video_path: str,
        start: float = 0.0,
        end: Optional[float] = None,
        targets: Optional[List[float]] = None,
        metric: Optional[BlockMAE] = None,
        prefix: str = "hop",
        min_stable: float = 1.0,
    ):
        """Initialize the detection.

        Args:
            video_path: path of the video file.
            start: segment start in seconds.
            end: segment end in seconds; defaults to the video duration.
            targets: transcript-named mandatory capture times in seconds.
            metric: localized change metric; defaults to BlockMAE().
            prefix: file name prefix for evidence frames.
            min_stable: seconds of stability separating two hops; a burst
                of changes (scrolling, page rendering) is one hop.
        """
        self.video_path = video_path
        self.start = start
        self.end = end
        self.targets = targets if targets is not None else []
        self.metric = metric if metric is not None else BlockMAE()
        self.prefix = prefix
        self.min_stable = min_stable
        self.result: Optional[BisectionResult] = None
        self.groups: List[List[ChangeBracket]] = []

    @staticmethod
    def mmss(time_sec: float) -> str:
        """Format seconds as MM:SS.

        Args:
            time_sec: time in seconds.

        Returns:
            zero-padded MM:SS string.
        """
        minutes = int(time_sec) // 60
        seconds = int(time_sec) % 60
        formatted = f"{minutes:02d}:{seconds:02d}"
        return formatted

    @staticmethod
    def group_brackets(
        changes: List[ChangeBracket], min_stable: float
    ) -> List[List[ChangeBracket]]:
        """Group temporally adjacent change brackets into hop groups.

        A burst of frame-level changes (scrolling, page rendering, video
        playback) is one hop: a new group starts only after the content
        stayed stable for min_stable seconds - measured on the GenWiki
        acceptance segment where raw brackets peaked at 18 per second
        while the narrative visited one page.

        Args:
            changes: change brackets ordered by time.
            min_stable: seconds of stability separating two groups.

        Returns:
            the groups, each a non-empty list of brackets.
        """
        groups: List[List[ChangeBracket]] = []
        current: List[ChangeBracket] = []
        for bracket in changes:
            if current and bracket.before - current[-1].after >= min_stable:
                groups.append(current)
                current = []
            current.append(bracket)
        if current:
            groups.append(current)
        return groups

    def detect(self) -> List[Hop]:
        """Run the bisection and derive the hops.

        Returns:
            hops ordered by position, one per settled content state.
        """
        segment = VideoSegment(self.video_path, self.start, self.end)
        sampler = BisectionSampler(segment, self.metric)
        self.result = sampler.run(self.targets)
        self.groups = self.group_brackets(self.result.changes, self.min_stable)
        hops = []
        for pos, group in enumerate(self.groups, start=1):
            first = group[0]
            last = group[-1]
            max_score = max(bracket.score for bracket in group)
            hop = Hop(
                pos=pos,
                time=self.mmss(last.after),
                node=f"{self.prefix}{pos:02d}",
                summary=f"{len(group)} change(s) "
                f"[{first.before:.2f}s,{last.after:.2f}s], "
                f"max score {max_score:.1f}, "
                f"settled at {last.after:.2f}s",
            )
            hops.append(hop)
        segment.close()
        return hops

    def save(self, hops: List[Hop], out_dir: str) -> Path:
        """Save evidence frames and the hop JSON records.

        Args:
            hops: the detected hops.
            out_dir: output directory, created if needed.

        Returns:
            path of the written JSON file.

        Raises:
            ImportError: if OpenCV is not available.
        """
        if cv2 is None:
            raise ImportError("opencv is required to save evidence frames")
        out_path = Path(out_dir)
        out_path.mkdir(parents=True, exist_ok=True)
        segment = VideoSegment(self.video_path, self.start, self.end)
        result = self.result if self.result is not None else BisectionResult()
        for hop, group in zip(hops, self.groups):
            frame = segment.frame_at(group[-1].after)
            if frame is not None:
                image_path = out_path / f"{hop.node}.jpg"
                cv2.imwrite(str(image_path), frame)
                hop.screenshot = image_path.name
        segment.close()
        report = {
            "video": self.video_path,
            "start": self.start,
            "end": self.end,
            "frames_sampled": result.frames_sampled,
            "hops": [asdict(hop) for hop in hops],
            "absences": [asdict(proof) for proof in result.absences],
        }
        json_path = out_path / "hops.json"
        with json_path.open("w") as json_file:
            json.dump(report, json_file, indent=2)
        return json_path


def parse_time(value: str) -> float:
    """Parse a time given as seconds or as MM:SS.

    Args:
        value: e.g. "1200", "20:00".

    Returns:
        the time in seconds.
    """
    seconds = 0.0
    if ":" in value:
        minutes_part, seconds_part = value.split(":", 1)
        seconds = int(minutes_part) * 60 + float(seconds_part)
    else:
        seconds = float(value)
    return seconds


def main(argv: Optional[List[str]] = None) -> int:
    """Command line entry point for hop detection.

    Args:
        argv: command line arguments; defaults to sys.argv.

    Returns:
        exit code 0 on success.
    """
    parser = argparse.ArgumentParser(description="RDD hop detection")
    parser.add_argument("video", help="path of the video file")
    parser.add_argument("--start", default="0", help="segment start (seconds or MM:SS)")
    parser.add_argument("--end", default=None, help="segment end (seconds or MM:SS)")
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="transcript-named capture time (seconds or MM:SS), repeatable",
    )
    parser.add_argument(
        "--out", default="hops", help="output directory for frames and JSON"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=12.0,
        help="block-MAE change threshold",
    )
    parser.add_argument(
        "--min-stable",
        type=float,
        default=1.0,
        help="seconds of stability separating two hops",
    )
    args = parser.parse_args(argv)
    metric = BlockMAE(threshold=args.threshold)
    end = parse_time(args.end) if args.end is not None else None
    hop_detection = HopDetection(
        video_path=args.video,
        start=parse_time(args.start),
        end=end,
        targets=[parse_time(t) for t in args.target],
        metric=metric,
        min_stable=args.min_stable,
    )
    hops = hop_detection.detect()
    json_path = hop_detection.save(hops, args.out)
    result = hop_detection.result
    frames_sampled = result.frames_sampled if result is not None else 0
    print(f"{len(hops)} hops from {frames_sampled} sampled frames -> {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
