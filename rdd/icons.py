"""Created on 2026-08-12.

the material icons a reel site draws in its menu

The BITPlan applications wear the material icon set that quasar loads for
nicegui. A reel site may not load a font from a foreign host - the Review UI
stack decision requires that the browser loads nothing but the reel site - so
the handful of icons the menu needs travel as inline svg path data taken from
https://github.com/google/material-design-icons (Apache-2.0), same names, same
shapes.

@author: wf
"""

import re
import urllib.parse
from pathlib import Path
from typing import Dict

# material icon name -> path data of the 24x24 svg
ICONS: Dict[str, str] = {
    "menu": "M3 18h18v-2H3v2zm0-5h18v-2H3v2zm0-7v2h18V6H3z",
    "home": "M10 20v-6h4v6h5v-8h3L12 3 2 12h3v8z",
    "movie": (
        "M18 4l2 4h-3l-2-4h-2l2 4h-3l-2-4H8l2 4H7L5 4H4c-1.1 0-1.99.9-1.99 2"
        "L2 18c0 1.1.9 2 2 2h16c1.1 0 2-.9 2-2V4h-4z"
    ),
    "bug_report": (
        "M20 8h-2.81c-.45-.78-1.07-1.45-1.82-1.96L17 4.41 15.59 3l-2.17 2.17"
        "C12.96 5.06 12.49 5 12 5c-.49 0-.96.06-1.41.17L8.41 3 7 4.41l1.62 1.63"
        "C7.88 6.55 7.26 7.22 6.81 8H4v2h2.09c-.05.33-.09.66-.09 1v1H4v2h2v1"
        "c0 .34.04.67.09 1H4v2h2.81c1.04 1.79 2.97 3 5.19 3s4.15-1.21 5.19-3H20"
        "v-2h-2.09c.05-.33.09-.66.09-1v-1h2v-2h-2v-1c0-.34-.04-.67-.09-1H20V8z"
        "m-6 8h-4v-2h4v2zm0-4h-4v-2h4v2z"
    ),
    "help": (
        "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"
        "m1 17h-2v-2h2v2zm2.07-7.75l-.9.92C13.45 12.9 13 13.5 13 15h-2v-.5"
        "c0-1.1.45-2.1 1.17-2.83l1.24-1.26c.37-.36.59-.86.59-1.41 0-1.1-.9-2-2-2"
        "s-2 .9-2 2H8c0-2.21 1.79-4 4-4s4 1.79 4 4c0 .88-.36 1.68-.93 2.25z"
    ),
    "info": (
        "M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2z"
        "m1 15h-2v-6h2v6zm0-8h-2V7h2v2z"
    ),
}


def svg(name: str, size: str = "1.2em") -> str:
    """Render the named material icon as an inline svg.

    Args:
        name: material icon name e.g. home.
        size: css length for width and height.

    Returns:
        the svg markup, drawn in the current text color.

    Raises:
        ValueError: if the icon is not one of the shipped ones.
    """
    path = ICONS.get(name)
    if path is None:
        available = ", ".join(sorted(ICONS.keys()))
        raise ValueError(f"unknown icon {name} - available: {available}")
    markup = (
        f'<svg viewBox="0 0 24 24" width="{size}" height="{size}" '
        f'fill="currentColor" aria-hidden="true"><path d="{path}"/></svg>'
    )
    return markup


def topic_svg_source(name: str) -> str:
    """The SVG source of the named topic icon.

    The topic icons are the house-authored ones of
    https://contexts.bitplan.com/index.php/Icons/SVG - shipped as
    resources of the package per issue #47.

    Args:
        name: topic icon name e.g. Recording or HopContent.

    Returns:
        the SVG source.

    Raises:
        FileNotFoundError: if the icon is not one of the shipped ones.
    """
    path = Path(__file__).parent / "resources" / f"{name}.svg"
    source = path.read_text()
    return source


def topic_svg(name: str, size: str = "3em") -> str:
    """Render the named topic icon as an inline svg of the given size.

    Args:
        name: topic icon name e.g. Recording or HopContent.
        size: css length for width and height.

    Returns:
        the svg markup at the given size.
    """
    source = topic_svg_source(name)
    markup = re.sub(
        r'width="64" height="64"',
        f'width="{size}" height="{size}"',
        source,
        count=1,
    ).strip()
    return markup


def favicon_link(name: str = "Recording") -> str:
    """The favicon link of the named topic icon as a data uri.

    A reel site page loads nothing but the reel site per the Review UI
    stack decision, so the favicon travels inline.

    Args:
        name: topic icon name e.g. Recording.

    Returns:
        the link markup for the html head.
    """
    source = topic_svg_source(name)
    data = urllib.parse.quote(source)
    link = f'<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,{data}">'
    return link
