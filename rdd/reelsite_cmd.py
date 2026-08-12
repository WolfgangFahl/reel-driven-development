"""Created on 2026-08-12.

command line interface of the reel site

@author: wf
"""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from basemkit.base_cmd import BaseCmd

from rdd.reelsite import SiteConfig, serve
from rdd.version import Version


class ReelSiteCmd(BaseCmd):
    """Serve the reel site of an organization."""

    def __init__(self):
        """Initialize with the reel-driven-development version info."""
        super().__init__(Version())

    def add_arguments(self, parser: argparse.ArgumentParser):
        """Add the site arguments to the given parser.

        Args:
            parser: the parser to add arguments to.
        """
        super().add_arguments(parser)
        parser.add_argument(
            "-c",
            "--config",
            default="~/.rdd/reelsite.yaml",
            help="site configuration yaml [default: %(default)s]",
        )
        parser.add_argument(
            "--host", default="127.0.0.1", help="interface to listen on"
        )
        parser.add_argument("-p", "--port", type=int, help="port to serve on")
        parser.add_argument("-s", "--serve", action="store_true", help="serve the site")

    def handle_args(self, args: argparse.Namespace) -> bool:
        """Handle the parsed arguments by serving the site.

        Args:
            args: parsed argument namespace.

        Returns:
            True if the arguments were handled.
        """
        handled = super().handle_args(args)
        if not handled and args.serve:
            config_path = Path(args.config).expanduser()
            if not config_path.exists():
                raise ValueError(f"no site configuration at {config_path}")
            config = SiteConfig.of_file(str(config_path))
            if args.port:
                config.port = args.port
            serve(config, host=args.host)
            handled = True
        return handled


def main(argv: Optional[List[str]] = None) -> int:
    """Command line entry point of the reel site.

    Args:
        argv: command line arguments; defaults to sys.argv.

    Returns:
        exit code: 0 = OK, 1 = KeyboardInterrupt, 2 = Exception.
    """
    cmd = ReelSiteCmd()
    exit_code = cmd.run(argv)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
