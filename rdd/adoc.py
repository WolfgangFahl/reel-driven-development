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

import yaml

from rdd.hopset import HopSet
from rdd.recording import HopContent

PERSONS_FILE = "persons.yaml"


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
    ):
        """Initialize the document of the given reel.

        Args:
            hop_set: the reel with its Recording and its hops.
            folder: the recording folder the frames live in.
            persons: person name to the url they are identifiable by
                outside the wiki; a name that is not in it keeps its
                plain form, so a document renders before the mapping is
                complete and the gap is visible in it.
        """
        self.hop_set = hop_set
        self.recording = hop_set.recording
        self.folder = folder
        self.persons = persons if persons else {}

    @classmethod
    def of_folder(cls, folder: str) -> "RecordingDoc":
        """Get the document of the given recording folder.

        Args:
            folder: the recording folder.

        Returns:
            the document of its reel file.

        Raises:
            ValueError: if the folder carries no reel file.
        """
        hop_set = HopSet.of_dir(folder)
        if hop_set is None:
            raise ValueError(f"{HopSet.path_of(folder)} not found")
        persons = cls.persons_of(os.path.join(folder, PERSONS_FILE))
        doc = cls(hop_set, folder, persons=persons)
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
            f":imagesdir: {os.path.abspath(self.folder)}",
            "",
        ]
        facts = [str(fact) for fact in (rec.date, rec.platform) if fact]
        if rec.durationMin is not None:
            facts.append(f"{rec.durationMin} min")
        facts.append(f"{self.hop_set.hopCount} hops")
        lines += [" - ".join(facts), ""]
        if self.participants:
            links = [self.person_link(name) for name in self.participants]
            lines += [f"Participants: {', '.join(links)}", ""]
        return lines

    def hop_block(self, hop: HopContent) -> List[str]:
        """Get the asciidoc lines of one hop.

        Args:
            hop: the hop record.

        Returns:
            the lines of the hop block.
        """
        heading = hop.node if hop.node else hop.time
        lines = [f"== {hop.pos}. {heading}", "", f"{hop.time}", ""]
        if self.frame_path(hop):
            lines += [f"image::{hop.screenshot}[{heading},width=640]", ""]
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
        for hop in self.hop_set.hops:
            lines += self.hop_block(hop)
        doc = "\n".join(lines) + "\n"
        return doc

    def save(self, path: str) -> str:
        """Write the document to the given path.

        Args:
            path: the file to write.

        Returns:
            the path written.
        """
        with open(path, "w", encoding="utf-8") as adoc_file:
            adoc_file.write(self.asciidoc())
        return path
