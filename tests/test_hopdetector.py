"""Created on 2026-08-08.

@author: wf
"""

import os

from basemkit.basetest import Basetest
from basemkit.profiler import Profiler

from rdd.config import HopConfig
from rdd.frame import Reel
from rdd.hopdetector import HopDetector


class TestSceneDetect(Basetest):
    """Compare the scene detectors the library offers on our example reel."""

    def setUp(self, debug=True, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)
        current_folder = os.path.dirname(__file__)
        self.reel_path = os.path.join(
            current_folder, "..", "examples", "genwiki-walk", "genwiki-walk.mp4"
        )

    def get_reel(self) -> Reel:
        """Get the example reel."""
        reel = Reel(self.reel_path)
        return reel

    def test_all_detectors(self):
        """Every detector of the library must run over the reel and answer cut
        positions inside the reel in ascending order."""
        reel = self.get_reel()
        hop_detector = HopDetector(reel)
        cuts = {}
        for name, _detector in HopDetector.get_detectors():
            profiler = Profiler(name, profile=self.debug)
            frame_nums = hop_detector.scenes(HopConfig(detector=name))
            profiler.time(f" - {len(frame_nums)} cuts")
            cuts[name] = frame_nums
            self.assertEqual(sorted(frame_nums), frame_nums)
            for frame_num in frame_nums:
                self.assertTrue(0 <= frame_num <= reel.frame_count)
        self.assertTrue(any(frame_nums for frame_nums in cuts.values()))
