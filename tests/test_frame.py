"""Created on 2026-08-08.

@author: wf
"""

from basemkit.basetest import Basetest

from rdd.frame import Frame, FrameChange, Region


class TestFrame(Basetest):
    """Test the frame abstraction and the frame change criterion."""

    def setUp(self, debug=False, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)
        self.frame_change = FrameChange()

    def test_frame_geometry_and_timecode(self):
        """A frame must know its size and its position in the reel."""
        frame = Frame.make(frame_num=3050, fps=25.0)
        self.assertEqual(1280, frame.width)
        self.assertEqual(720, frame.height)
        self.assertEqual(122.0, frame.time_sec)
        self.assertEqual("02:02", frame.timecode)
        no_fps = Frame.make(frame_num=7, fps=None, width=4, height=4, value=0)
        self.assertIsNone(no_fps.time_sec)
        self.assertEqual("frame 7", no_fps.timecode)

    def test_blank_frame(self):
        """A uniform frame is blank; content makes it non blank."""
        frame = Frame.make()
        self.assertTrue(frame.is_blank())
        self.assertFalse(frame.with_rect(10, 20, 10, 20, 255).is_blank())

    def test_identical_frames(self):
        """Identical frames must score zero and report no change."""
        frame = Frame.make()
        self.assertEqual(0.0, self.frame_change.score(frame, frame))
        self.assertFalse(self.frame_change.changed(frame, frame))

    def test_localized_change(self):
        """A dropdown-sized change must be detected although the global mean
        stays far below the threshold."""
        frame_a = Frame.make()
        frame_b = frame_a.with_rect(100, 180, 200, 400, 255)  # ~1.7% of the frame
        global_change = FrameChange(blocks_x=1, blocks_y=1)
        global_score = global_change.score(frame_a, frame_b)
        self.assertLess(global_score, self.frame_change.threshold)
        self.assertTrue(self.frame_change.changed(frame_a, frame_b))
        if self.debug:
            print(
                f"global {global_score:.2f} vs "
                f"block {self.frame_change.score(frame_a, frame_b):.2f}"
            )

    def test_region_bounds(self):
        """Issue #5: pixel and fractional regions must map to the same crop
        bounds on the native frame."""
        pixel_region = Region.of_str("0,0,1120,720")
        fractional_region = Region.of_str("0.0,0.0,0.875,1.0")
        self.assertFalse(pixel_region.is_fractional)
        self.assertTrue(fractional_region.is_fractional)
        self.assertEqual((0, 720, 0, 1120), pixel_region.bounds(1280, 720))
        self.assertEqual((0, 720, 0, 1120), fractional_region.bounds(1280, 720))
        self.assertEqual((0, 720, 0, 1280), Region().bounds(1280, 720))

    def test_region_needs_four_values(self):
        """A malformed region must raise instead of being guessed."""
        with self.assertRaises(ValueError):
            Region.of_str("0,0,1")

    def test_region_restricts_scoring(self):
        """Issue #5: a change outside the region must not score; the same
        change inside the full frame must."""
        frame_a = Frame.make()
        frame_b = frame_a.with_rect(0, 80, 1200, 1280, 255)  # top-right corner tile
        self.assertTrue(self.frame_change.changed(frame_a, frame_b))
        region_change = FrameChange(region=Region(0.0, 0.0, 0.875, 1.0))
        self.assertFalse(region_change.changed(frame_a, frame_b))
        self.assertEqual(0.0, region_change.score(frame_a, frame_b))

    def test_region_smaller_than_grid(self):
        """A region smaller than the block grid must raise instead of failing
        silently."""
        region_change = FrameChange(region=Region(0, 0, 8, 4))
        frame = Frame.make()
        with self.assertRaises(ValueError):
            region_change.score(frame, frame)

    def test_color_frames(self):
        """The criterion must accept 3-channel color frames."""
        frame_a = Frame.make(width=640, height=360, value=0, channels=3)
        frame_b = frame_a.with_rect(0, 40, 0, 80, 200)
        self.assertTrue(self.frame_change.changed(frame_a, frame_b))
