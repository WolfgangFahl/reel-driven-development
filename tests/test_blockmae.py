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

    def test_region_bounds(self):
        """Issue #5: pixel and fractional regions must map to the same crop
        bounds on the native frame."""
        pixel_metric = BlockMAE(region=(0, 0, 1120, 720))
        fractional_metric = BlockMAE(region=(0.0, 0.0, 0.875, 1.0))
        shape = (720, 1280)
        self.assertFalse(BlockMAE.is_fractional(pixel_metric.region))
        self.assertTrue(BlockMAE.is_fractional(fractional_metric.region))
        self.assertEqual((0, 720, 0, 1120), pixel_metric.region_bounds(shape))
        self.assertEqual((0, 720, 0, 1120), fractional_metric.region_bounds(shape))
        self.assertEqual((0, 720, 0, 1280), BlockMAE().region_bounds(shape))

    def test_region_restricts_scoring(self):
        """Issue #5: a change outside the region must not score; the same
        change inside the full frame must."""
        frame_a = self.make_frame()
        frame_b = self.make_frame()
        frame_b[0:80, 1200:1280] = 255  # top-right corner tile
        self.assertTrue(self.metric.changed(frame_a, frame_b))
        region_metric = BlockMAE(region=(0.0, 0.0, 0.875, 1.0))
        self.assertFalse(region_metric.changed(frame_a, frame_b))
        self.assertEqual(0.0, region_metric.score(frame_a, frame_b))

    def test_region_smaller_than_grid(self):
        """A region smaller than the block grid must raise instead of failing
        silently."""
        metric = BlockMAE(region=(0, 0, 8, 4))
        frame = self.make_frame()
        with self.assertRaises(ValueError):
            metric.score(frame, frame)

    def test_color_frames(self):
        """The metric must accept 3-channel color frames."""
        frame_a = np.zeros((360, 640, 3), dtype=np.uint8)
        frame_b = np.zeros((360, 640, 3), dtype=np.uint8)
        frame_b[:40, :80, :] = 200
        self.assertTrue(self.metric.changed(frame_a, frame_b))
