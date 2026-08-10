"""Created on 2026-08-10.

command line interface of the asciidoc rendering of a reel

see https://github.com/WolfgangFahl/reel-driven-development/issues/23

@author: wf
"""

import argparse
import os
import sys
from typing import List, Optional

from basemkit.base_cmd import BaseCmd

from rdd.adoc import RecordingDoc
from rdd.quickcheck import QuickCheck
from rdd.version import Version


class ReelDocCmd(BaseCmd):
    """Render the reel of a recording folder as an asciidoc document."""

    def __init__(self):
        """Initialize with the reel-driven-development version info."""
        super().__init__(Version())

    def add_arguments(self, parser: argparse.ArgumentParser):
        """Add the document arguments to the given parser.

        Args:
            parser: the parser to add arguments to.
        """
        super().add_arguments(parser)
        parser.add_argument("folder", nargs="?", help="the recording folder")
        parser.add_argument(
            "-o", "--out", help="asciidoc file to write (default: in the folder)"
        )
        parser.add_argument(
            "--quickcheck",
            action="store_true",
            help="also write the single page quick check html",
        )
        parser.add_argument(
            "--width",
            type=int,
            default=640,
            help="width of an evidence frame in the document (default: 640) "
            "- the lever on the size of the pdf",
        )

    def handle_args(self, args: argparse.Namespace) -> bool:
        """Handle the parsed arguments by rendering the document.

        Args:
            args: parsed argument namespace.

        Returns:
            True if the arguments were handled.

        Raises:
            ValueError: if the folder argument is missing.
        """
        handled = super().handle_args(args)
        if not handled:
            if args.folder is None:
                raise ValueError("the folder argument is required")
            self.render(args)
            handled = True
        return handled

    def render(self, args: argparse.Namespace):
        """Render the reel of the given folder.

        Args:
            args: parsed argument namespace.
        """
        doc = RecordingDoc.of_folder(args.folder, width=args.width)
        recording = doc.recording
        name = recording.acronym or os.path.basename(os.path.abspath(args.folder))
        out_path = args.out
        if out_path is None:
            out_path = os.path.join(args.folder, f"{name}.adoc")
        doc.save(out_path)
        if args.quickcheck:
            check_path = os.path.join(args.folder, f"{name}-quickcheck.html")
            QuickCheck(doc).save(check_path)
        if not args.quiet:
            missing = [hop.pos for hop in doc.hop_set.hops if not doc.frame_path(hop)]
            if missing:
                print(f"frames missing for hops: {missing}", file=sys.stderr)
            unnamed = [hop.pos for hop in doc.hop_set.hops if not hop.node]
            if unnamed:
                print(
                    f"{len(unnamed)} hops carry no node - the hop set is "
                    f"detected, not curated",
                    file=sys.stderr,
                )
        print(f"{name}: {doc.hop_set.hopCount} hops -> {os.path.abspath(out_path)}")


def main(argv: Optional[List[str]] = None) -> int:
    """Command line entry point for the asciidoc rendering.

    Args:
        argv: command line arguments; defaults to sys.argv.

    Returns:
        exit code: 0 = OK, 1 = KeyboardInterrupt, 2 = Exception.
    """
    cmd = ReelDocCmd()
    exit_code = cmd.run(argv)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
