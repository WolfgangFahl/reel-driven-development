"""Created on 2026-08-08.

@author: wf
"""

import argparse
import sys
from typing import List, Optional

from basemkit.base_cmd import BaseCmd

from rdd.version import Version


class RddCmd(BaseCmd):
    """Reel Driven Development command line interface."""

    def __init__(self):
        """Initialize with the reel-driven-development version info."""
        super().__init__(Version())

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
            "--progress",
            nargs="?",
            type=float,
            const=1.0,
            default=None,
            help="report progress on stderr every n wall clock seconds "
            "(default: 1.0 when given without a value)",
        )
        parser.add_argument(
            "--no-bar", action="store_true", help="suppress the progress bar"
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
            # code for using scene detect missing
            handled = True
        return handled


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
