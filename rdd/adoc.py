"""Created on 2026-08-10.

asciidoc rendering of a reel

The reel file carries the Recording, the run configuration and the hops.
The wiki templates render that model as wikitext; the templates here
render the same model as asciidoc, so page and document say the same
thing. The document is a build artefact of the folder - anyone holding
the folder can rebuild it, with no wiki in the path.

see https://github.com/WolfgangFahl/reel-driven-development/issues/23

@author: wf
"""

import os
from typing import Dict, List, Optional

import cv2
import yaml

from rdd.hopset import HopSet
from rdd.recording import HopContent
from rdd.transcript import Transcript

PERSONS_FILE = "persons.yaml"

# the headings of Template:RecordingDetails, so page and document say the
# same thing in the same words; English is the fallback
LABELS = {
    "en": {
        "summary": "Summary",
        "walk": "Graph Walk",
        "transcript": "Transcript",
        "participants": "Participants",
        "hops": "hops",
    },
    "de": {
        "summary": "Zusammenfassung",
        "walk": "Graph Walk",
        "transcript": "Transkript",
        "participants": "Teilnehmer",
        "hops": "Hops",
    },
}


class RecordingDoc:
    """The asciidoc document of one reel.

    One block per hop - the frame, when it was reached, the node and what
    happened there - so a reviewer reads their own walk and can write
    into the rendered pdf beside every step.
    """

    def __init__(
        self,
        hop_set: HopSet,
        folder: str,
        persons: Optional[Dict[str, str]] = None,
        transcript: Optional[Transcript] = None,
        width: int = 640,
    ):
        """Initialize the document of the given reel.

        Args:
            hop_set: the reel with its Recording and its hops.
            folder: the recording folder the frames live in.
            persons: person name to the url they are identifiable by
                outside the wiki; a name that is not in it keeps its
                plain form, so a document renders before the mapping is
                complete and the gap is visible in it.
            transcript: the improved transcript, None where the folder
                carries none.
            width: width of an evidence frame in the document.
        """
        self.hop_set = hop_set
        self.recording = hop_set.recording
        self.folder = folder
        self.persons = persons if persons else {}
        self.transcript = transcript
        self.width = width

    @property
    def lang(self) -> str:
        """The language of the Recording, English where it carries none."""
        language = self.recording.language if self.recording else None
        doc_lang = language if language in LABELS else "en"
        return doc_lang

    def label(self, key: str) -> str:
        """Get the heading of the given section in the document language.

        Args:
            key: the section key.

        Returns:
            the heading.
        """
        heading = LABELS[self.lang][key]
        return heading

    @classmethod
    def of_folder(cls, folder: str, **kwargs) -> "RecordingDoc":
        """Get the document of the given recording folder.

        Args:
            folder: the recording folder.
            kwargs: passed on to the constructor, e.g. the frame width.

        Returns:
            the document of its reel file.

        Raises:
            ValueError: if the folder carries no reel file.
        """
        hop_set = HopSet.of_dir(folder)
        if hop_set is None:
            raise ValueError(f"{HopSet.path_of(folder)} not found")
        persons = cls.persons_of(os.path.join(folder, PERSONS_FILE))
        doc = cls(
            hop_set,
            folder,
            persons=persons,
            transcript=Transcript.of_dir(folder),
            **kwargs,
        )
        return doc

    @classmethod
    def persons_of(cls, yaml_path: str) -> Dict[str, str]:
        """Read the person mapping of the given file.

        Args:
            yaml_path: file of name to url entries.

        Returns:
            the mapping, empty where the file is not there - the mapping
            grows with the reels and is not a precondition of a document.
        """
        persons = {}
        if os.path.isfile(yaml_path):
            with open(yaml_path, encoding="utf-8") as yaml_file:
                persons = yaml.safe_load(yaml_file) or {}
        return persons

    @property
    def participants(self) -> List[str]:
        """The participants as the Recording names them."""
        names = []
        if self.recording and self.recording.participants:
            names = [
                name.strip()
                for name in self.recording.participants.split(",")
                if name.strip()
            ]
        return names

    def person_link(self, name: str) -> str:
        """Get the asciidoc form of the given person.

        Args:
            name: the person as the Recording names them.

        Returns:
            a link where the person has a url, the plain name otherwise.
        """
        person_url = self.persons.get(name)
        adoc_link = f"{person_url}[{name}]" if person_url else name
        return adoc_link

    @property
    def images_dir(self) -> str:
        """The directory the document takes its frames from.

        A frame is a full screen capture; embedding it at full
        resolution is what makes a document of two dozen hops too heavy
        to mail. The scaled copies live in a hidden directory of the
        recording folder, derived and rebuildable, so the evidence
        frames themselves stay untouched.
        """
        frames_dir = self.folder
        if self.width:
            frames_dir = os.path.join(self.folder, f".frames-{self.width}")
        return frames_dir

    def scale_frames(self) -> int:
        """Write the scaled copies of the evidence frames.

        Returns:
            the number of frames written.
        """
        scaled = 0
        if not self.width:
            return scaled
        os.makedirs(self.images_dir, exist_ok=True)
        for hop in self.hop_set.hops:
            source = self.frame_path(hop)
            if source is None:
                continue
            target = os.path.join(self.images_dir, hop.screenshot)
            if os.path.isfile(target):
                continue
            image = cv2.imread(source)
            if image is None:
                continue
            height, source_width = image.shape[:2]
            if source_width > self.width:
                height = int(round(height * self.width / source_width))
                image = cv2.resize(
                    image, (self.width, height), interpolation=cv2.INTER_AREA
                )
            cv2.imwrite(target, image)
            scaled += 1
        return scaled

    def frame_path(self, hop: HopContent) -> Optional[str]:
        """Get the file path of the evidence frame of the given hop.

        Args:
            hop: the hop record.

        Returns:
            the path of the frame, None where the hop has none or the
            frame is not in the folder - a missing frame is left out of
            the document rather than rendered as a broken image.
        """
        path = None
        if hop.screenshot:
            candidate = os.path.join(self.folder, hop.screenshot)
            if os.path.isfile(candidate):
                path = candidate
        return path

    def header(self) -> List[str]:
        """Get the document header lines."""
        rec = self.recording
        title = rec.name or rec.acronym or rec.videoFile or "reel"
        lines = [
            f"= {title}",
            ":doctype: article",
            ":toc: left",
            ":icons: font",
            f":lang: {rec.language}" if rec.language else ":lang: en",
            # the frames are named relative to the folder, so the document
            # travels with it and the same source renders inside the zip
            f":imagesdir: {os.path.abspath(self.images_dir)}",
            "",
        ]
        facts = [str(fact) for fact in (rec.date, rec.platform) if fact]
        if rec.durationMin is not None:
            facts.append(f"{rec.durationMin} min")
        facts.append(f"{self.hop_set.hopCount} {self.label('hops')}")
        lines += [" - ".join(facts), ""]
        if self.participants:
            links = [self.person_link(name) for name in self.participants]
            lines += [f"{self.label('participants')}: {', '.join(links)}", ""]
        if rec.summary:
            lines += [f"== {self.label('summary')}", "", rec.summary, ""]
        return lines

    def transcript_block(self) -> List[str]:
        """Get the asciidoc lines of the improved transcript.

        Returns:
            the lines, empty where the folder carries no transcript - a
            reel may be documented before its transcript is improved.
        """
        lines = []
        if self.transcript and self.transcript.segments:
            lines = [f"== {self.label('transcript')}", ""]
            for segment in self.transcript.segments:
                speaker = segment.speaker if segment.speaker else ""
                lines.append(f"`{segment.start}` {speaker}:: {segment.text}")
            lines.append("")
        return lines

    def hop_block(self, hop: HopContent) -> List[str]:
        """Get the asciidoc lines of one hop.

        Args:
            hop: the hop record.

        Returns:
            the lines of the hop block.
        """
        heading = hop.node if hop.node else hop.time
        lines = [f"=== {hop.pos}. {heading}", "", f"{hop.time}", ""]
        if self.frame_path(hop):
            lines += [f"image::{hop.screenshot}[{heading},width={self.width}]", ""]
        if hop.url:
            lines += [f"{hop.url}[{hop.url}]", ""]
        if hop.summary:
            lines += [hop.summary, ""]
        return lines

    def asciidoc(self) -> str:
        """Get the whole document as asciidoc.

        Returns:
            the asciidoc source.
        """
        lines = self.header()
        if self.hop_set.hops:
            lines += [f"== {self.label('walk')}", ""]
            for hop in self.hop_set.hops:
                lines += self.hop_block(hop)
        lines += self.transcript_block()
        doc = "\n".join(lines) + "\n"
        return doc

    def save(self, path: str) -> str:
        """Write the document to the given path.

        Args:
            path: the file to write.

        Returns:
            the path written.
        """
        self.scale_frames()
        with open(path, "w", encoding="utf-8") as adoc_file:
            adoc_file.write(self.asciidoc())
        return path
