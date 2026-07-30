"""Created on 2026-07-30.

@author: wf
"""

import numpy as np
from basemkit.basetest import Basetest

from rdd.blockmae import BlockMAE


class TestBlockMAE(Basetest):
    """Test the localized block-MAE change metric."""

    def setUp(self, debug=False, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)
        self.metric = BlockMAE()

    def make_frame(self) -> np.ndarray:
        """Create a plain gray 720p test frame."""
        frame = np.full((720, 1280), 128, dtype=np.uint8)
        return frame

    def test_identical_frames(self):
        """Identical frames must score zero and report no change."""
        frame = self.make_frame()
        self.assertEqual(0.0, self.metric.score(frame, frame))
        self.assertFalse(self.metric.changed(frame, frame))

    def test_localized_change(self):
        """A dropdown-sized change must be detected although the global mean
        stays far below the threshold."""
        frame_a = self.make_frame()
        frame_b = self.make_frame()
        frame_b[100:180, 200:400] = 255  # ~1.7% of the frame
        global_mae = float(
            np.abs(frame_a.astype(np.float32) - frame_b.astype(np.float32)).mean()
        )
        self.assertLess(global_mae, self.metric.threshold)
        self.assertTrue(self.metric.changed(frame_a, frame_b))
        if self.debug:
            print(
                f"global {global_mae:.2f} vs "
                f"block {self.metric.score(frame_a, frame_b):.2f}"
            )

    def test_color_frames(self):
        """The metric must accept 3-channel color frames."""
        frame_a = np.zeros((360, 640, 3), dtype=np.uint8)
        frame_b = np.zeros((360, 640, 3), dtype=np.uint8)
        frame_b[:40, :80, :] = 200
        self.assertTrue(self.metric.changed(frame_a, frame_b))
