"""Created on 2026-08-12.

command line interface of the reel review pass

see https://github.com/WolfgangFahl/reel-driven-development/issues/27

@author: wf
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from basemkit.base_cmd import BaseCmd

from rdd.reelreview import DEFAULT_HOST, DEFAULT_PORT, serve
from rdd.version import Version


class ReelReviewCmd(BaseCmd):
    """Serve a recording folder for the human in the loop review pass."""

    def __init__(self):
        """Initialize with the reel-driven-development version info."""
        super().__init__(Version())

    def add_arguments(self, parser: argparse.ArgumentParser):
        """Add the review arguments to the given parser.

        Args:
            parser: the parser to add arguments to.
        """
        super().add_arguments(parser)
        parser.add_argument(
            "folder", nargs="?", default=".", help="recording folder (default: .)"
        )
        parser.add_argument(
            "--host",
            default=DEFAULT_HOST,
            help="interface to listen on; the api needs no authentication, so"
            " opening this beyond localhost shares write access to the reel"
            " [default: %(default)s]",
        )
        parser.add_argument(
            "-p",
            "--port",
            type=int,
            default=DEFAULT_PORT,
            help="port to serve on [default: %(default)s]",
        )

    def handle_args(self, args: argparse.Namespace) -> bool:
        """Handle the parsed arguments by serving the folder.

        Args:
            args: parsed argument namespace.

        Returns:
            True if the arguments were handled.
        """
        handled = super().handle_args(args)
        if not handled:
            folder = Path(args.folder).expanduser().resolve()
            serve(folder, port=args.port, host=args.host)
            handled = True
        return handled


def main(argv: Optional[List[str]] = None) -> int:
    """Command line entry point of the review pass.

    Args:
        argv: command line arguments; defaults to sys.argv.

    Returns:
        exit code: 0 = OK, 1 = KeyboardInterrupt, 2 = Exception.
    """
    cmd = ReelReviewCmd()
    exit_code = cmd.run(argv)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
