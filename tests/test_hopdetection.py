"""Created on 2026-07-30.

@author: wf
"""

import json
import tempfile
from pathlib import Path

from basemkit.basetest import Basetest

from rdd.bisection import ChangeBracket
from rdd.hopdetection import (
    HopDetection,
    from_args,
    get_parser,
    parse_region,
    parse_time,
)
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

    def test_parse_region(self):
        """Issue #5: region parsing must accept pixel and fractional forms and
        reject malformed values."""
        self.assertEqual((0.0, 0.0, 1708.0, 1080.0), parse_region("0,0,1708,1080"))
        self.assertEqual((0.0, 0.0, 0.89, 1.0), parse_region("0,0,0.89,1.0"))
        with self.assertRaises(ValueError):
            parse_region("0,0,100")

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

    def argv_from_parameters(self, video: str, params: dict) -> list:
        """Rebuild a hopdetect command line from a recorded parameter set.

        Args:
            video: path of the video file.
            params: the parameter dict as recorded in hops.json.

        Returns:
            argv list reproducing the run per issue #4.
        """
        argv = [video]
        for name, value in params.items():
            if value is not None:
                flag = "--" + name.replace("_", "-")
                if isinstance(value, (list, tuple)):
                    value = ",".join(str(part) for part in value)
                argv.extend([flag, str(value)])
        return argv

    def test_parameter_flags(self):
        """Issue #4: every detection parameter must be settable via the CLI and
        reappear in the recorded parameter set."""
        argv = [
            "reel.mp4",
            "--threshold",
            "8.5",
            "--blocks-x",
            "32",
            "--blocks-y",
            "18",
            "--min-stable",
            "2.0",
            "--granularity",
            "0.2",
            "--target-window",
            "3.0",
            "--compare-width",
            "320",
            "--prefix",
            "walk",
        ]
        args = get_parser().parse_args(argv)
        hop_detection = from_args(args)
        expected = {
            "threshold": 8.5,
            "blocks_x": 32,
            "blocks_y": 18,
            "region": None,
            "min_stable": 2.0,
            "granularity": 0.2,
            "target_window": 3.0,
            "compare_width": 320,
            "prefix": "walk",
        }
        self.assertEqual(expected, hop_detection.parameters())

    def test_parameter_round_trip(self):
        """Issue #4: a run must be reproducible from the parameter set recorded
        in its own hops.json."""
        params = {
            "threshold": 9.0,
            "blocks_x": 8,
            "blocks_y": 8,
            "region": [0.0, 0.0, 0.875, 1.0],
            "min_stable": 1.5,
            "granularity": None,
            "target_window": 4.0,
            "compare_width": 480,
            "prefix": "h",
        }
        argv = self.argv_from_parameters("reel.mp4", params)
        args = get_parser().parse_args(argv)
        hop_detection = from_args(args)
        self.assertEqual(params, hop_detection.parameters())

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
