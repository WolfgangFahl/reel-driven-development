"""Created on 2026-08-08.

@author: wf
"""

import argparse
import os
import sys
import time
from typing import List, Optional

from basemkit.base_cmd import BaseCmd

from rdd.frame import Reel
from rdd.hopdetect import BisectionHopDetector, Finding
from rdd.timeline import Timeline
from rdd.version import Version


class RddCmd(BaseCmd):
    """Reel Driven Development command line interface."""

    def __init__(self):
        """Initialize with the reel-driven-development version info."""
        super().__init__(Version())
        self.detector = None

    @staticmethod
    def time_of(text: Optional[str]) -> Optional[float]:
        """Convert a time argument to seconds.

        Args:
            text: mm:ss, hh:mm:ss or a number of seconds; None stays None.

        Returns:
            the time in seconds or None.
        """
        time_sec = None
        if text is not None:
            parts = text.split(":")
            time_sec = 0.0
            for part in parts:
                time_sec = time_sec * 60.0 + float(part)
        return time_sec

    def add_arguments(self, parser: argparse.ArgumentParser):
        """Add the hop detection arguments to the given parser.

        Args:
            parser: the parser to add arguments to.
        """
        super().add_arguments(parser)
        parser.add_argument("video", nargs="?", help="path of the reel to analyze")
        parser.add_argument("--start", help="segment start as mm:ss or seconds")
        parser.add_argument("--end", help="segment end as mm:ss or seconds")
        parser.add_argument(
            "-o", "--out", default="hops", help="output directory (default: hops)"
        )
        parser.add_argument(
            "--settle",
            type=float,
            default=1.0,
            help="seconds without change that end a hop (default: 1.0)",
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
            self.detect(args)
            handled = True
        return handled

    def show(self, finding: Finding):
        """Show a finding on stderr as it is made.

        Args:
            finding: the finding to show.
        """
        coverage = self.detector.coverage
        print(
            f"{finding.kind:9s} {finding.start_sec:8.2f}-{finding.end_sec:8.2f}s "
            f"score {finding.score:6.1f} | "
            f"{coverage.frames_read:5d} frames read, "
            f"{coverage.brackets:4d} brackets, "
            f"{coverage.fraction:5.1%} resolved",
            file=sys.stderr,
        )

    def detect(self, args: argparse.Namespace):
        """Run the hop detection on the given arguments.

        Args:
            args: parsed argument namespace.
        """
        reel = Reel(args.video)
        on_finding = self.show if args.debug else None
        self.detector = BisectionHopDetector(reel, on_finding=on_finding)
        started = time.time()
        start_sec = self.time_of(args.start) or 0.0
        end_sec = self.time_of(args.end)
        brackets = self.detector.detect(start_sec=start_sec, end_sec=end_sec)
        hops = self.detector.hops(settle_sec=args.settle, out_dir=args.out)
        yaml_path = os.path.join(args.out, "hops.yaml")
        hops.save_to_yaml_file(yaml_path)
        coverage = self.detector.coverage
        if not args.quiet:
            timeline = Timeline(start_sec, end_sec or reel.duration_sec)
            print(
                timeline.render(brackets, coverage.resolved_sec, hops), file=sys.stderr
            )
        print(
            f"{reel.videoFile}: {hops.hopCount} hops from {len(brackets)} brackets, "
            f"{coverage.frames_read} of {reel.frame_count} frames read, "
            f"{coverage.fraction:.1%} of {coverage.total_sec:.1f}s resolved "
            f"in {time.time() - started:.1f}s -> {yaml_path}"
        )


def main(argv: Optional[List[str]] = None) -> int:
    """Command line entry point for hop detection.

    Args:
        argv: command line arguments; defaults to sys.argv.

    Returns:
        exit code: 0 = OK, 1 = KeyboardInterrupt, 2 = Exception.
    """
    cmd = RddCmd()
    exit_code = cmd.run(argv)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
