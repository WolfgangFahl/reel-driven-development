"""Created on 2026-08-14.

rdd - the dispatcher command of Reel Driven Development

rdd is the name of what we do, so rdd is the one command name a user
has to know; each subcommand forwards to the tool of the pipeline and
the tool names stay available as entry points of their own.

@author: wf
"""

import argparse
import importlib
import sys
from typing import Dict, List, Optional

from basemkit.base_cmd import BaseCmd

from rdd.version import Version

# the modules are named, not imported - a subcommand's dependency chain
# (detect and doc need cv2 and with it libGL) must not load unless that
# subcommand is dispatched: a headless serving host runs rdd site
# without any display library
SUBCOMMANDS: Dict[str, str] = {
    "detect": "rdd.hopdetect_cmd",
    "doc": "rdd.adoc_cmd",
    "review": "rdd.reelreview_cmd",
    "site": "rdd.reelsite_cmd",
}

# the detection chain is the hopdetect extra - a review only install
# carries neither cv2 nor scenedetect, and the answer of these two
# subcommands is the install line, not an import traceback
HOPDETECT_SUBCOMMANDS = {"detect", "doc"}


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


def dispatch(subcommand: str, module_name: str, argv: List[str]) -> int:
    """Import the module of a subcommand and run it.

    Args:
        subcommand: the subcommand as given on the command line.
        module_name: the module implementing the subcommand.
        argv: the arguments of the subcommand.

    Returns:
        the exit code of the subcommand, or 3 if the detection
        dependencies of the subcommand are not installed.
    """
    try:
        module = importlib.import_module(module_name)
        exit_code = module.main(argv)
    except ImportError as ex:
        if subcommand not in HOPDETECT_SUBCOMMANDS:
            raise
        print(
            f"rdd {subcommand} needs the detection dependencies - {ex.name} is missing",
            file=sys.stderr,
        )
        print(
            "pip install 'reel-driven-development[hopdetect]'",
            file=sys.stderr,
        )
        exit_code = 3
    return exit_code


def main(argv: Optional[List[str]] = None) -> int:
    """Command line entry point of the rdd dispatcher.

    Args:
        argv: command line arguments; defaults to sys.argv.

    Returns:
        the exit code of the subcommand, or 0 = OK, 1 =
        KeyboardInterrupt, 2 = Exception of the dispatcher itself.
    """
    args = sys.argv[1:] if argv is None else argv
    module_name = SUBCOMMANDS.get(args[0]) if args else None
    if module_name is not None:
        exit_code = dispatch(args[0], module_name, args[1:])
    else:
        cmd = RddCmd()
        exit_code = cmd.run(args)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
