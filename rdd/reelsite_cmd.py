"""Created on 2026-08-12.

command line interface of the reel site

@author: wf
"""

import argparse
import os
import sys
from pathlib import Path
from typing import List, Optional

from basemkit.base_cmd import BaseCmd

from rdd.mint import Mint
from rdd.rdd_site import RddSiteConfig, Reviews, serve
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
            default=RddSiteConfig.DEFAULT_PATH,
            help="site configuration yaml [default: %(default)s]",
        )
        parser.add_argument(
            "--host", default="127.0.0.1", help="interface to listen on"
        )
        parser.add_argument("-p", "--port", type=int, help="port to serve on")
        parser.add_argument("-s", "--serve", action="store_true", help="serve the site")
        parser.add_argument(
            "--init",
            action="store_true",
            help="initialize the site: seed the owner and mint the owner token",
        )
        parser.add_argument(
            "--mint",
            metavar="PERSON",
            help="mint a review token for the given person",
        )
        parser.add_argument(
            "--meeting", default="", help="the meeting a minted review belongs to"
        )
        parser.add_argument(
            "--reels",
            nargs="+",
            default=[],
            metavar="ACRONYM",
            help="the reels a minted review grants",
        )

    def handle_args(self, args: argparse.Namespace) -> bool:
        """Handle the parsed arguments - init, mint or serve.

        Args:
            args: parsed argument namespace.

        Returns:
            True if the arguments were handled.
        """
        handled = super().handle_args(args)
        if handled:
            return handled
        config = RddSiteConfig.of_path(args.config)
        if args.port:
            config.port = args.port
        if args.init:
            self.init_site(config)
            handled = True
        elif args.mint:
            mint = Mint(config)
            url = mint.mint_review(args.mint, args.meeting, args.reels)
            print(url)
            handled = True
        elif args.serve:
            config_path = Path(args.config).expanduser()
            if not config_path.exists():
                raise ValueError(f"no site configuration at {config_path}")
            reviews_file = os.path.expanduser(Reviews.DEFAULT_PATH)
            if not os.path.isfile(reviews_file) and sys.stdin.isatty():
                # per the Owner bootstrap decision the first interactive
                # start is installation mode - the owner is asked here;
                # a non-interactive start serves the installation state
                self.init_site(config)
            serve(config, host=args.host)
            handled = True
        return handled

    def init_site(self, config: RddSiteConfig):
        """Run installation mode - seed the owner interactively.

        Per the Owner bootstrap decision the owner link is shown once
        on the interactive terminal and written to a mode 600 file; it
        goes nowhere else.

        Args:
            config: the site configuration.
        """
        mint = Mint(config)
        username = input("owner username: ").strip()
        name = input("owner full name: ").strip()
        email = input("owner email: ").strip()
        url = input("owner url: ").strip()
        owner_url = mint.init_site(username, name, email, url)
        print(f"owner link (also in {mint.owner_link_path}, mode 600):")
        print(owner_url)


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
