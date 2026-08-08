"""Created on 2026-08-08.

@author: wf
"""

import os

from basemkit.basetest import Basetest

from rdd.frame import Frame
from rdd.hopdetect import BisectionHopDetector, Bracket, Reel


class TestHopDetect(Basetest):
    """Test the bisection hop detection."""

    def setUp(self, debug=False, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)
        self.reel_path = "examples/genwiki-walk/genwiki-walk.mp4"

    def test_bracket(self):
        """A bracket must report where and how closely a change is caught."""
        before = Frame.make(frame_num=100, fps=25.0)
        after = Frame.make(frame_num=110, fps=25.0)
        bracket = Bracket(before=before, after=after, score=42.0)
        self.assertEqual(4.0, bracket.start_sec)
        self.assertEqual(4.4, bracket.end_sec)
        self.assertAlmostEqual(0.4, bracket.width_sec, places=6)
        self.assertEqual("00:04-00:04", bracket.timecode)

    def test_reel_and_detection(self):
        """The bisection must bracket changes reading far fewer frames than the
        reel has, and every bracket must be refined to the floor."""
        if not os.path.isfile(self.reel_path):
            return
        reel = Reel(self.reel_path)
        self.assertEqual(25.0, reel.fps)
        self.assertTrue(reel.duration_sec > 59)
        self.assertTrue(len(reel.keyframes) > 0)
        findings = []
        detector = BisectionHopDetector(reel, on_finding=findings.append)
        brackets = detector.detect(0.0, 30.0)
        self.assertTrue(len(brackets) > 0)
        bracket_findings = [f for f in findings if f.kind == "bracket"]
        unchanged = [f for f in findings if f.kind == "unchanged"]
        self.assertEqual(len(brackets), len(bracket_findings))
        self.assertTrue(len(unchanged) > 0)
        self.assertTrue(detector.coverage.frames_read < reel.frame_count / 2)
        tolerance = 1.0 / reel.fps
        for bracket in brackets:
            self.assertTrue(bracket.width_sec <= detector.min_gap_sec + tolerance)
        if self.debug:
            print(
                f"{len(brackets)} brackets, "
                f"{detector.coverage.frames_read} frames read of "
                f"{reel.frame_count}, "
                f"coverage {detector.coverage.fraction:.1%}"
            )

    def test_segment_outside_reel(self):
        """A segment outside the reel must raise instead of being clamped."""
        if not os.path.isfile(self.reel_path):
            return
        reel = Reel(self.reel_path)
        detector = BisectionHopDetector(reel)
        with self.assertRaises(ValueError):
            detector.detect(1200.0, 1260.0)
