"""Created on 2026-08-08.

@author: wf
"""

import os
import time

from basemkit.basetest import Basetest

from rdd.frame import Reel
from rdd.hopdetect import BisectionHopDetector


class TestSceneDetect(Basetest):
    """Compare the built-in scene detector with the bisection."""

    def setUp(self, debug=False, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)
        self.reel_path = "examples/genwiki-walk/genwiki-walk.mp4"

    def test_candidates_and_cost(self):
        """The built-in detector must be usable as a candidate source, and both
        ways must be measurable against each other."""
        if not os.path.isfile(self.reel_path):
            return
        reel = Reel(self.reel_path)
        started = time.time()
        candidates = reel.scene_candidates()
        scene_sec = time.time() - started
        detector = BisectionHopDetector(reel)
        started = time.time()
        brackets = detector.detect()
        bisect_sec = time.time() - started
        self.assertTrue(len(candidates) > 0)
        self.assertTrue(len(brackets) > 0)
        self.assertTrue(detector.coverage.frames_read < reel.frame_count / 2)
        if self.debug:
            print(
                f"scene detector: {len(candidates)} candidates, "
                f"{reel.frame_count} frames decoded, {scene_sec:.1f}s\n"
                f"bisection: {len(brackets)} brackets, "
                f"{detector.coverage.frames_read} frames read, {bisect_sec:.1f}s"
            )
