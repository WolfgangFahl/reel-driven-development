"""Created on 2026-07-30.

@author: wf
"""

import json
import tempfile
from pathlib import Path

from basemkit.basetest import Basetest

from rdd.bisection import ChangeBracket
from rdd.hopdetection import HopDetection, parse_time
from tests.video_cache import TEST_SEGMENT_END, TEST_SEGMENT_START, get_test_video


class TestHopDetection(Basetest):
    """Test hop detection - acceptance per issue #1."""

    def setUp(self, debug=False, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)

    def test_parse_time(self):
        """Time parsing must accept seconds and MM:SS."""
        self.assertEqual(1200.0, parse_time("1200"))
        self.assertEqual(1200.0, parse_time("20:00"))
        self.assertEqual(1260.5, parse_time("21:00.5"))

    def test_group_brackets(self):
        """A burst of changes must form one hop group; a stability gap must
        start a new group."""

        def bracket(before: float) -> ChangeBracket:
            grouped = ChangeBracket(before=before, after=before + 0.04, score=20.0)
            return grouped

        scroll_burst = [bracket(10.0), bracket(10.2), bracket(10.5)]
        next_hop = [bracket(15.0)]
        groups = HopDetection.group_brackets(scroll_burst + next_hop, min_stable=1.0)
        self.assertEqual(2, len(groups))
        self.assertEqual(3, len(groups[0]))
        self.assertEqual(1, len(groups[1]))
        self.assertEqual([], HopDetection.group_brackets([], min_stable=1.0))

    def test_acceptance_video_segment(self):
        """Acceptance: the 20:00-21:00 segment of the test video yields
        hops, evidence frames and the hop JSON records."""
        if self.inPublicCI():
            self.skipTest("test video not available in public CI")
        video_path = get_test_video()
        if video_path is None:
            self.skipTest("test video could not be downloaded")
        hop_detection = HopDetection(
            video_path,
            start=TEST_SEGMENT_START,
            end=TEST_SEGMENT_END,
        )
        hops = hop_detection.detect()
        self.assertGreaterEqual(len(hops), 1)
        result = hop_detection.result
        grid_frames = (TEST_SEGMENT_END - TEST_SEGMENT_START) * 25
        self.assertLess(result.frames_sampled, grid_frames)
        with tempfile.TemporaryDirectory() as out_dir:
            json_path = hop_detection.save(hops, out_dir)
            self.assertTrue(json_path.exists())
            with json_path.open() as json_file:
                report = json.load(json_file)
            self.assertEqual(len(hops), len(report["hops"]))
            for hop in report["hops"]:
                self.assertTrue((Path(out_dir) / hop["screenshot"]).exists())
        if self.debug:
            print(
                f"{len(hops)} hops from {result.frames_sampled} frames "
                f"(grid: {grid_frames:.0f})"
            )
            for hop in hops:
                print(f"  {hop.time} {hop.node} {hop.summary}")
