"""Created on 2026-08-08.

hop records of a graph walk

Schema: the Meeting context of https://contexts.bitplan.com
* https://contexts.bitplan.com/index.php/Concept:HopContent
* https://contexts.bitplan.com/index.php/Concept:Recording

@author: wf
"""

from typing import List, Optional

from basemkit.yamlable import lod_storable


@lod_storable
class Recording:
    """One recorded video of a session, with its processing state.

    The field names are the property names of
    https://contexts.bitplan.com/index.php/Concept:Recording
    and are never renamed: a Recording is a page in the Meeting context
    and is read back by the same names.

    A Recording is the record of a video, not the video itself; reading
    pictures from the file is the business of the specialization in
    rdd.frame.
    """

    name: Optional[str] = None
    date: Optional[str] = None
    durationMin: Optional[float] = None
    videoFile: Optional[str] = None
    platform: Optional[str] = None
    meeting: Optional[str] = None
    participants: Optional[str] = None
    language: Optional[str] = None
    computer: Optional[str] = None
    user: Optional[str] = None
    state: Optional[str] = None
    transcript: Optional[str] = None
    driveLink: Optional[str] = None
    hopCount: Optional[int] = None


@lod_storable
class HopContent:
    """One node visit in the graph walk of a Recording.

    The node is the page, screen or application reached by a context
    switch; the record says when it was reached and what happened there.

    The field names are the property names of
    https://contexts.bitplan.com/index.php/Concept:HopContent
    and are never renamed: a record is stored as a
    subobject on its Recording page and read back by the same names.
    """

    pos: int = 0
    time: str = ""
    node: Optional[str] = None
    url: Optional[str] = None
    summary: Optional[str] = None
    screenshot: Optional[str] = None
    recording: Optional[str] = None


@lod_storable
class HopContents:
    """The hops of one Recording.

    https://contexts.bitplan.com/index.php/Concept:Recording is linked to
    its hops 1:n via the recordingHops TopicLink, and the hopCount of the
    Recording must equal the number of hop records - that equality is the
    mechanical completeness control of the walk.
    """

    recording: Optional[str] = None
    hops: List[HopContent] = None

    def __post_init__(self):
        """Start with an empty hop list where none was given."""
        if self.hops is None:
            self.hops = []

    @property
    def hopCount(self) -> int:
        """The number of hop records, to be compared with the hopCount of the
        Recording."""
        hop_count = len(self.hops)
        return hop_count

    def add(self, hop: HopContent) -> HopContent:
        """Add a hop, giving it the next position and this recording.

        Args:
            hop: the hop record to add.

        Returns:
            the added hop.
        """
        hop.pos = len(self.hops) + 1
        hop.recording = self.recording
        self.hops.append(hop)
        return hop
