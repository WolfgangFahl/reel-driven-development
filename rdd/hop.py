"""Created on 2026-07-30.

@author: wf
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Hop:
    """A hop is a node visit in a screen-share reel.

    Every context switch (page, browser tab, application) and every
    relevant interaction (submenu open, filter select, zoom, sort) is a
    hop per the HopContent model of Reel Driven Development.
    """

    pos: int
    time: str
    node: str
    url: Optional[str] = None
    summary: Optional[str] = None
    screenshot: Optional[str] = None
