"""Created on 2026-08-10.

tests for the asciidoc rendering of a reel

The fixtures name no real participant: a test travels with the public
source, and who took part in a recording does not.

@author: wf
"""

import os
import tempfile

from basemkit.basetest import Basetest

from rdd.adoc import RecordingDoc
from rdd.hopset import HopSet
from rdd.recording import HopContent, Recording
from rdd.transcript import Transcript, TranscriptSegment


class TestAdoc(Basetest):
    """Test the asciidoc rendering of a reel file."""

    def setUp(self, debug=False, profile=True):
        """Set up a reel of two hops."""
        Basetest.setUp(self, debug=debug, profile=profile)
        self.hop_set = HopSet(
            recording=Recording(
                name="Demo/Walk-2026-08-08",
                acronym="Demo-Walk-2026-08",
                date="2026-08-08",
                platform="Zoom",
                participants="Ada Lovelace, Alan Turing",
                language="en",
                durationMin=28.0,
            ),
            hops=[
                HopContent(
                    pos=1,
                    time="00:01",
                    node="Zoom active speaker",
                    summary="no browser on screen",
                    screenshot="hop-00h00m01s.jpg",
                ),
                HopContent(
                    pos=2,
                    time="02:07",
                    node="Wikipedia Main Page",
                    url="https://en.wikipedia.org/wiki/Main_Page",
                    summary="the main page loads",
                    screenshot="hop-00h02m07s.jpg",
                ),
            ],
        )

    def test_hop_count_is_derived(self):
        """Test that the hop count is the length of the hop list."""
        self.assertEqual(2, self.hop_set.hopCount)

    def test_person_link(self):
        """Test that an unmapped person keeps their plain name."""
        doc = RecordingDoc(
            self.hop_set,
            folder="/no/such/folder",
            persons={"Ada Lovelace": "https://www.wikidata.org/wiki/Q7259"},
        )
        self.assertEqual(
            "https://www.wikidata.org/wiki/Q7259[Ada Lovelace]",
            doc.person_link("Ada Lovelace"),
        )
        self.assertEqual("Alan Turing", doc.person_link("Alan Turing"))

    def test_language_follows_the_recording(self):
        """Test that the headings are those of Template:RecordingDetails."""
        self.hop_set.recording.summary = "worum es geht"
        self.hop_set.recording.language = "de"
        doc = RecordingDoc(self.hop_set, folder="/no/such/folder")
        adoc = doc.asciidoc()
        self.assertIn("== Zusammenfassung", adoc)
        self.assertIn("== Graph Walk", adoc)
        self.assertIn("Teilnehmer:", adoc)
        # a language we have no labels for falls back to english
        self.hop_set.recording.language = "fr"
        self.assertEqual("Summary", RecordingDoc(self.hop_set, ".").label("summary"))

    def test_transcript(self):
        """Test that the improved transcript is rendered with its speakers."""
        transcript = Transcript(
            segments=[
                TranscriptSegment(
                    pos=1, start="00:00", speaker="Ada Lovelace", text="hello"
                )
            ]
        )
        doc = RecordingDoc(
            self.hop_set, folder="/no/such/folder", transcript=transcript
        )
        adoc = doc.asciidoc()
        self.assertIn("== Transcript", adoc)
        self.assertIn("Ada Lovelace:: hello", adoc)
        # a reel without an improved transcript shows no empty heading
        self.assertNotIn("== Transcript", RecordingDoc(self.hop_set, ".").asciidoc())

    def test_asciidoc(self):
        """Test that the document carries a block per hop and no broken
        image."""
        doc = RecordingDoc(self.hop_set, folder="/no/such/folder")
        adoc = doc.asciidoc()
        self.assertIn("= Demo/Walk-2026-08-08", adoc)
        self.assertIn("2 hops", adoc)
        self.assertIn("== 1. Zoom active speaker", adoc)
        self.assertIn("== 2. Wikipedia Main Page", adoc)
        self.assertIn("https://en.wikipedia.org/wiki/Main_Page", adoc)
        # the frames are not in this folder, so no image is claimed
        self.assertNotIn("image::", adoc)

    def test_of_folder(self):
        """Test that a document is built from the reel file of a folder."""
        with tempfile.TemporaryDirectory() as folder:
            self.hop_set.save(HopSet.path_of(folder), version="test", date="2026-08-10")
            frame = os.path.join(folder, "hop-00h00m01s.jpg")
            with open(frame, "wb") as frame_file:
                frame_file.write(b"not a real jpeg")
            doc = RecordingDoc.of_folder(folder)
            self.assertEqual(2, doc.hop_set.hopCount)
            adoc = doc.asciidoc()
            # the frame that is there is claimed, the other one is not
            self.assertIn("hop-00h00m01s.jpg", adoc)
            self.assertNotIn("hop-00h02m07s.jpg", adoc)
