"""Created on 2026-08-02.

@author: wf
"""

from dataclasses import dataclass

import rdd


@dataclass
class Version:
    """Version information for reel-driven-development."""

    name: str = "reel-driven-development"
    version: str = rdd.__version__
    date: str = "2026-07-30"
    updated: str = "2026-08-02"
    description: str = (
        "Reel Driven Development - turn recorded user walks "
        "into domain stories and outcome objects"
    )
    authors: str = "Wolfgang Fahl"
    doc_url: str = "https://wiki.bitplan.com/index.php/Reel_Driven_Development"
    chat_url: str = (
        "https://github.com/WolfgangFahl/reel-driven-development/discussions"
    )
    cm_url: str = "https://github.com/WolfgangFahl/reel-driven-development"
