"""Created on 2026-08-10.

the transcript of a reel

Schema: the Meeting context of https://contexts.bitplan.com
* https://contexts.bitplan.com/index.php/Concept:TranscriptSegment

The segments live in a file of their own beside the reel: the reel file
is what a person curates by hand, and a transcript of a few hundred
segments would drown the few dozen hops in it.

see https://github.com/WolfgangFahl/reel-driven-development/issues/25

@author: wf
"""

import os
from typing import List, Optional

from basemkit.yamlable import lod_storable


@lod_storable
class TranscriptSegment:
    """One timed segment of the improved transcript of a Recording.

    The field names are the property names of
    https://contexts.bitplan.com/index.php/Concept:TranscriptSegment
    and are never renamed. end stays empty where the source provides only
    starts; speaker stays empty where diarization and content disagree -
    an unattributed segment is the honest form, a guessed one is not.
    """

    pos: int = 0
    start: str = ""
    end: Optional[str] = None
    speaker: Optional[str] = None
    text: str = ""


@lod_storable
class Transcript:
    """The improved transcript of one reel.

    The raw result of the transcription stays as it came out of the
    tool; this is the corrected reading of it, and the two stay
    diffable.
    """

    FILE_NAME = "segments.yaml"

    segments: List[TranscriptSegment] = None

    def __post_init__(self):
        """Start with an empty segment list where none was given."""
        if self.segments is None:
            self.segments = []

    @property
    def segmentCount(self) -> int:
        """The number of segments of this transcript."""
        segment_count = len(self.segments)
        return segment_count

    @classmethod
    def path_of(cls, folder: str) -> str:
        """Get the path of the transcript file in the given folder.

        Args:
            folder: the recording folder.

        Returns:
            the path of the transcript file.
        """
        transcript_path = os.path.join(folder, cls.FILE_NAME)
        return transcript_path

    @classmethod
    def of_dir(cls, folder: str) -> Optional["Transcript"]:
        """Get the transcript of the given folder.

        Args:
            folder: the recording folder.

        Returns:
            the transcript, None where the folder carries none - a reel
            may be documented before its transcript is improved.
        """
        transcript_path = cls.path_of(folder)
        transcript = None
        if os.path.isfile(transcript_path):
            transcript = cls.load_from_yaml_file(transcript_path)
        return transcript
