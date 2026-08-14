"""Created on 2026-08-14.

rdd - the dispatcher command of Reel Driven Development

rdd is the name of what we do, so rdd is the one command name a user
has to know; each subcommand forwards to the tool of the pipeline and
the tool names stay available as entry points of their own.

@author: wf
"""

import argparse
import sys
from typing import Callable, Dict, List, Optional

from basemkit.base_cmd import BaseCmd

from rdd import adoc_cmd, hopdetect_cmd, reelreview_cmd, reelsite_cmd
from rdd.version import Version

SUBCOMMANDS: Dict[str, Callable[[Optional[List[str]]], int]] = {
    "detect": hopdetect_cmd.main,
    "doc": adoc_cmd.main,
    "review": reelreview_cmd.main,
    "site": reelsite_cmd.main,
}


class RddCmd(BaseCmd):
    """The rdd dispatcher - answers what rdd can do.

    Dispatching itself happens in main before argument parsing, so a
    subcommand owns its own arguments; this class only serves the case
    of no subcommand - the standard options and the list of
    subcommands.
    """

    def __init__(self):
        """Initialize with the reel-driven-development version info."""
        super().__init__(Version())

    def add_arguments(self, parser: argparse.ArgumentParser):
        """Add the subcommand overview to the given parser.

        Args:
            parser: the parser to add arguments to.
        """
        super().add_arguments(parser)
        parser.description = (
            "Reel Driven Development - subcommands: "
            "detect (find the hops of a reel), "
            "doc (generate the reel document), "
            "review (serve one reel for review), "
            "site (serve, initialize or mint for the reel site); "
            "rdd <subcommand> --help shows the arguments of a subcommand"
        )

    def handle_args(self, args: argparse.Namespace) -> bool:
        """Handle the parsed arguments - without a subcommand the help is
        the answer.

        Args:
            args: parsed argument namespace.

        Returns:
            True if the arguments were handled.
        """
        handled = super().handle_args(args)
        if not handled:
            self.parser.print_help()
            handled = True
        return handled


def main(argv: Optional[List[str]] = None) -> int:
    """Command line entry point of the rdd dispatcher.

    Args:
        argv: command line arguments; defaults to sys.argv.

    Returns:
        the exit code of the subcommand, or 0 = OK, 1 =
        KeyboardInterrupt, 2 = Exception of the dispatcher itself.
    """
    args = sys.argv[1:] if argv is None else argv
    subcommand = SUBCOMMANDS.get(args[0]) if args else None
    if subcommand is not None:
        exit_code = subcommand(args[1:])
    else:
        cmd = RddCmd()
        exit_code = cmd.run(args)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
