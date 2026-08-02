"""Created on 2026-07-30.

@author: wf
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from basemkit.base_cmd import BaseCmd

from rdd.bisection import BisectionResult, BisectionSampler, ChangeBracket
from rdd.blockmae import BlockMAE
from rdd.hop import Hop
from rdd.progress import JsonlRenderer, ProgressEmitter, TqdmRenderer, mmss
from rdd.version import Version
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
        granularity: Optional[float] = None,
        target_window: float = 5.0,
        compare_width: int = 640,
        progress: Optional[ProgressEmitter] = None,
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
            granularity: minimal interval the bisection refines to in
                seconds; defaults to one frame.
            target_window: seconds sampled around each transcript target.
            compare_width: width frames are downscaled to for comparison.
            progress: progress emitter; defaults to a renderer-less one.
        """
        self.video_path = video_path
        self.start = start
        self.end = end
        self.targets = targets if targets is not None else []
        self.metric = metric if metric is not None else BlockMAE()
        self.prefix = prefix
        self.min_stable = min_stable
        self.granularity = granularity
        self.target_window = target_window
        self.compare_width = compare_width
        self.progress = progress if progress is not None else ProgressEmitter()
        self.result: Optional[BisectionResult] = None
        self.groups: List[List[ChangeBracket]] = []

    def parameters(self) -> dict:
        """Collect the effective parameter set of this detection.

        The set is recorded in hops.json so that a hop set carries the
        values that produced it and a run is reproducible from its own
        output - see issue #4.

        Returns:
            dict of parameter name to effective value; granularity is
            None when the per-video one-frame default applies.
        """
        params = {
            "threshold": self.metric.threshold,
            "blocks_x": self.metric.blocks_x,
            "blocks_y": self.metric.blocks_y,
            "region": list(self.metric.region) if self.metric.region else None,
            "min_stable": self.min_stable,
            "granularity": self.granularity,
            "target_window": self.target_window,
            "compare_width": self.compare_width,
            "prefix": self.prefix,
        }
        return params

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
        region = self.metric.region
        if region is not None and not BlockMAE.is_fractional(region):
            # normalize a pixel region against the native resolution so
            # that the compare_width downscale can not shift it
            x, y, width, height = region
            self.metric.region = (
                x / segment.width,
                y / segment.height,
                width / segment.width,
                height / segment.height,
            )
        self.progress.emit(
            "run_start",
            video=self.video_path,
            start=self.start,
            end=segment.end,
            parameters=self.parameters(),
        )
        sampler = BisectionSampler(
            segment,
            self.metric,
            granularity=self.granularity,
            target_window=self.target_window,
            compare_width=self.compare_width,
            progress=self.progress,
        )
        self.result = sampler.run(self.targets)
        self.progress.emit("phase", phase="grouping")
        self.groups = self.group_brackets(self.result.changes, self.min_stable)
        hops = []
        for pos, group in enumerate(self.groups, start=1):
            first = group[0]
            last = group[-1]
            max_score = max(bracket.score for bracket in group)
            hop = Hop(
                pos=pos,
                time=mmss(last.after),
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
        self.progress.emit("phase", phase="emit")
        for hop, group in zip(hops, self.groups):
            frame = segment.frame_at(group[-1].after)
            if frame is not None:
                image_path = out_path / f"{hop.node}.jpg"
                cv2.imwrite(str(image_path), frame)
                hop.screenshot = image_path.name
            self.progress.emit(
                "hop",
                pos=group[-1].after,
                hop_pos=hop.pos,
                time=hop.time,
                screenshot=hop.screenshot,
            )
        segment.close()
        report = {
            "video": self.video_path,
            "start": self.start,
            "end": self.end,
            "parameters": self.parameters(),
            "frames_sampled": result.frames_sampled,
            "hops": [asdict(hop) for hop in hops],
            "absences": [asdict(proof) for proof in result.absences],
        }
        json_path = out_path / "hops.json"
        with json_path.open("w") as json_file:
            json.dump(report, json_file, indent=2)
        self.progress.emit(
            "run_end",
            frames_sampled=result.frames_sampled,
            brackets=len(result.changes),
            groups=len(self.groups),
            hops=len(hops),
            absences=len(result.absences),
            status="ok",
        )
        return json_path


def parse_region(value: str) -> tuple:
    """Parse a region of interest given as x,y,width,height.

    Pixel values refer to the native video frame; fractional values
    (width and height <= 1) are resolution independent - see issue #5.

    Args:
        value: e.g. "0,0,1708,1080" or "0,0,0.89,1.0".

    Returns:
        (x, y, width, height) as floats.

    Raises:
        ValueError: if the value has no four comma-separated numbers.
    """
    parts = value.split(",")
    if len(parts) != 4:
        raise ValueError(f"region needs x,y,width,height - got {value}")
    region = tuple(float(part) for part in parts)
    return region


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


class HopdetectCmd(BaseCmd):
    """Hopdetect command line interface.

    BITPlan house-standard CLI per the BaseCmd pattern of pybasemkit.
    Every parameter that influences the hop set is a flag here so that
    a run is reproducible from its command line - see issue #4.
    """

    def __init__(self):
        """Initialize with the reel-driven-development version info."""
        super().__init__(Version())

    def add_arguments(self, parser: argparse.ArgumentParser):
        """Add the hopdetect arguments to the given parser.

        Args:
            parser: the parser to add arguments to.
        """
        super().add_arguments(parser)
        parser.add_argument("video", nargs="?", help="path of the video file")
        parser.add_argument(
            "--start", default="0", help="segment start (seconds or MM:SS)"
        )
        parser.add_argument(
            "--end", default=None, help="segment end (seconds or MM:SS)"
        )
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
            help="block-MAE change threshold (gray levels)",
        )
        parser.add_argument(
            "--min-stable",
            type=float,
            default=1.0,
            help="seconds of stability separating two hops",
        )
        parser.add_argument(
            "--blocks-x",
            type=int,
            default=16,
            help="block grid columns; a finer grid raises the score of a "
            "small-area change, so choose together with --threshold",
        )
        parser.add_argument(
            "--blocks-y",
            type=int,
            default=9,
            help="block grid rows; see --blocks-x",
        )
        parser.add_argument(
            "--granularity",
            type=float,
            default=None,
            help="minimal bisection interval in seconds; default one frame",
        )
        parser.add_argument(
            "--target-window",
            type=float,
            default=5.0,
            help="seconds sampled around each transcript target",
        )
        parser.add_argument(
            "--compare-width",
            type=int,
            default=640,
            help="width frames are downscaled to before comparison; a block "
            "must stay wide enough to average meaningfully, see --blocks-x",
        )
        parser.add_argument(
            "--prefix",
            default="hop",
            help="evidence frame name prefix",
        )
        parser.add_argument(
            "--region",
            default=None,
            help="region of interest x,y,width,height the change metric is "
            "restricted to - pixel or fractional values; evidence frames "
            "stay full frames",
        )
        parser.add_argument(
            "--progress",
            action="store_true",
            help="show a progress bar; phase 1 is determinate, the adaptive "
            "bisection shows the known quantities instead of a percentage",
        )
        parser.add_argument(
            "--progress-details",
            default=None,
            metavar="PATH",
            help="write machine-readable progress as JSONL to PATH; - means " "stderr",
        )
        parser.add_argument(
            "--progress-every",
            type=float,
            default=1.0,
            help="minimum seconds between JSONL sample events",
        )

    def handle_args(self, args: argparse.Namespace) -> bool:
        """Handle the parsed arguments by running the detection.

        Args:
            args: parsed argument namespace.

        Returns:
            True if the arguments were handled.

        Raises:
            ValueError: if the video argument is missing.
        """
        handled = super().handle_args(args)
        if not handled:
            if args.video is None:
                raise ValueError("the video argument is required")
            hop_detection = from_args(args)
            details_file = None
            if args.progress_details is not None:
                if args.progress_details == "-":
                    details_stream = sys.stderr
                else:
                    details_file = open(args.progress_details, "w")
                    details_stream = details_file
                renderer = JsonlRenderer(
                    details_stream, progress_every=args.progress_every
                )
                hop_detection.progress.attach(renderer)
            if args.progress:
                hop_detection.progress.attach(TqdmRenderer())
            hops = hop_detection.detect()
            json_path = hop_detection.save(hops, args.out)
            if details_file is not None:
                details_file.close()
            result = hop_detection.result
            frames_sampled = result.frames_sampled if result is not None else 0
            print(
                f"{len(hops)} hops from {frames_sampled} sampled frames "
                f"-> {json_path}"
            )
            handled = True
        return handled


def get_parser() -> argparse.ArgumentParser:
    """Create the hopdetect argument parser.

    Returns:
        the configured argument parser including the BaseCmd standard
        options.
    """
    cmd = HopdetectCmd()
    parser = cmd.get_arg_parser()
    return parser


def from_args(args: argparse.Namespace) -> HopDetection:
    """Build a HopDetection from parsed command line arguments.

    Args:
        args: parsed hopdetect arguments.

    Returns:
        the configured HopDetection.
    """
    region = parse_region(args.region) if args.region is not None else None
    metric = BlockMAE(
        blocks_x=args.blocks_x,
        blocks_y=args.blocks_y,
        threshold=args.threshold,
        region=region,
    )
    end = parse_time(args.end) if args.end is not None else None
    hop_detection = HopDetection(
        video_path=args.video,
        start=parse_time(args.start),
        end=end,
        targets=[parse_time(t) for t in args.target],
        metric=metric,
        prefix=args.prefix,
        min_stable=args.min_stable,
        granularity=args.granularity,
        target_window=args.target_window,
        compare_width=args.compare_width,
    )
    return hop_detection


def main(argv: Optional[List[str]] = None) -> int:
    """Command line entry point for hop detection.

    Args:
        argv: command line arguments; defaults to sys.argv.

    Returns:
        exit code: 0 = OK, 1 = KeyboardInterrupt, 2 = Exception.
    """
    cmd = HopdetectCmd()
    exit_code = cmd.run(argv)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
