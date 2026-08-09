"""Created on 2026-08-08.

@author: wf
"""

from basemkit.basetest import Basetest

from rdd.frame import Frame, Region


class TestFrame(Basetest):
    """Test the frame abstraction."""

    def setUp(self, debug=False, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)

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

    def test_crop_to_region(self):
        """Issue #5: cropping to a region must answer a frame of the region
        size."""
        frame = Frame.make()
        cropped = frame.crop(Region(0.0, 0.0, 0.875, 1.0))
        self.assertEqual(1120, cropped.width)
        self.assertEqual(frame.height, cropped.height)
        self.assertEqual(frame, frame.crop(None))
