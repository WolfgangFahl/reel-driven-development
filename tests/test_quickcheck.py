"""Created on 2026-08-10.

tests for the quick check page

@author: wf
"""

import os
import tempfile

from basemkit.basetest import Basetest

from rdd.adoc import RecordingDoc
from rdd.hopset import HopSet
from rdd.quickcheck import QuickCheck
from rdd.recording import HopContent, Recording


class TestQuickCheck(Basetest):
    """Test the single page quick check."""

    def setUp(self, debug=False, profile=True):
        """Set up a german reel of two hops."""
        Basetest.setUp(self, debug=debug, profile=profile)
        self.hop_set = HopSet(
            recording=Recording(
                name="Demo/Walk-2026-08-08",
                acronym="Demo-Walk-2026-08",
                language="de",
            ),
            hops=[
                HopContent(pos=1, time="00:01", node="Zoom", summary="Kameravideo"),
                HopContent(pos=2, time="02:07", node="Hauptseite", summary="lädt"),
            ],
        )

    def test_answers_in_the_language_of_the_recording(self):
        """Test that a german reel asks in german."""
        doc = RecordingDoc(self.hop_set, folder="/no/such/folder")
        page = QuickCheck(doc).html()
        for answer in ("ok", "weg", "ändern"):
            self.assertIn(f"> {answer}</label>", page)
        self.assertIn('lang="de"', page)
        # three answers per hop, nothing more
        self.assertEqual(3, page.count('type="radio" name="a1"'))
        self.assertEqual(3, page.count('type="radio" name="a2"'))

    def test_page_is_self_contained(self):
        """Test that the page carries its frame instead of linking it."""
        with tempfile.TemporaryDirectory() as folder:
            self.hop_set.hops[0].screenshot = "hop-00h00m01s.jpg"
            frame = os.path.join(folder, "hop-00h00m01s.jpg")
            with open(frame, "wb") as frame_file:
                frame_file.write(b"not a real jpeg")
            doc = RecordingDoc(self.hop_set, folder=folder, width=0)
            page = QuickCheck(doc).html()
            self.assertIn("data:image/jpeg;base64,", page)
            self.assertNotIn('<img src="hop-', page)

    def test_html_is_escaped(self):
        """Test that a summary can not break the page."""
        self.hop_set.hops[0].summary = 'ein <script>alert("x")</script> Text'
        doc = RecordingDoc(self.hop_set, folder="/no/such/folder")
        page = QuickCheck(doc).html()
        self.assertNotIn("<script>alert", page)
        self.assertIn("&lt;script&gt;", page)
