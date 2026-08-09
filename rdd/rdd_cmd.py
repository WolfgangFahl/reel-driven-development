"""Created on 2026-08-08.

@author: wf
"""

import argparse
import sys
from typing import List, Optional

from basemkit.base_cmd import BaseCmd

from rdd.config import HopConfig
from rdd.frame import Reel
from rdd.hopdetector import HopDetector
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

    def get_config(self, args: argparse.Namespace) -> HopConfig:
        """Get the configuration the given arguments select.

        Args:
            args: parsed argument namespace.

        Returns:
            the configuration of this run.
        """
        config = HopConfig(
            detector=args.detector,
            start_sec=self.time_of(args.start),
            end_sec=self.time_of(args.end),
        )
        return config

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
            "--progress",
            action="store_true",
            help="show the progress bar - a run over a reel takes minutes "
            "and must not be silent",
        )
        parser.add_argument(
            "--detector",
            choices=HopDetector.get_detector_names(),
            default="Content",
            help="scene detector to find the hops with (default: Content) "
            "- see https://www.scenedetect.com/benchmarks/",
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

    def detect(self, args: argparse.Namespace):
        """Run the hop detection on the given arguments.

        Args:
            args: parsed argument namespace.
        """
        reel = Reel(args.video)
        self.detector = HopDetector(reel)
        config = self.get_config(args)
        hops = self.detector.hops(config, out_dir=args.out, progress=args.progress)
        if not args.quiet:
            for hop in hops.hops:
                print(f"{hop.pos:3d} {hop.time} {hop.screenshot}", file=sys.stderr)
        print(
            f"{reel.videoFile}: {hops.hopCount} hops "
            f"from {args.detector} over {reel.frame_count} frames -> {args.out}"
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
