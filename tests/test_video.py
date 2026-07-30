"""Created on 2026-07-30.

@author: wf
"""

import tempfile
from pathlib import Path

from basemkit.basetest import Basetest

from rdd.video import VideoSegment


class TestVideoSegment(Basetest):
    """Test VideoSegment error distinction per issue #2."""

    def setUp(self, debug=False, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)

    def test_missing_file(self):
        """A non-existing path must raise FileNotFoundError."""
        with self.assertRaises(FileNotFoundError):
            VideoSegment("/no/such/video.mp4")

    def test_undecodable_file(self):
        """An existing but undecodable file must raise ValueError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            bogus_path = Path(tmp_dir) / "bogus.mp4"
            bogus_path.write_bytes(b"this is not a video")
            with self.assertRaises(ValueError):
                VideoSegment(str(bogus_path))
