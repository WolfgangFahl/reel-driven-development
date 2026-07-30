"""Created on 2026-07-30.

@author: wf
"""

import numpy as np
from basemkit.basetest import Basetest

from rdd.localized_detector import LocalizedContentDetector
from tests.video_cache import TEST_SEGMENT_END, TEST_SEGMENT_START, get_test_video

try:
    from scenedetect import SceneManager, open_video
    from scenedetect.detectors import ContentDetector
except ImportError:
    SceneManager = None  # type: ignore


class TestPySceneDetect(Basetest):
    """Test-before-adopt evaluation of PySceneDetect per issue #1."""

    def setUp(self, debug=False, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)

    def test_custom_detector_api(self):
        """The custom detector must receive raw frames and cut on a
        localized change - the API-fit criterion of issue #1."""
        detector = LocalizedContentDetector(min_scene_len=1)
        frame_a = np.full((360, 640, 3), 128, dtype=np.uint8)
        frame_b = frame_a.copy()
        frame_b[50:90, 100:200, :] = 255  # ~1.7% of the frame
        cuts = detector.process_frame(0, frame_a)
        self.assertEqual([], cuts)
        cuts = detector.process_frame(1, frame_a.copy())
        self.assertEqual([], cuts)
        cuts = detector.process_frame(2, frame_b)
        self.assertEqual([2], cuts)

    def run_detector(self, video_path: str, detector) -> int:
        """Run a detector over the acceptance segment via SceneManager.

        Args:
            video_path: path of the video file.
            detector: a PySceneDetect SceneDetector instance.

        Returns:
            the number of detected scenes.
        """
        video = open_video(video_path)
        video.seek(TEST_SEGMENT_START)
        manager = SceneManager()
        manager.add_detector(detector)
        manager.detect_scenes(video, duration=TEST_SEGMENT_END - TEST_SEGMENT_START)
        scene_count = len(manager.get_scene_list())
        return scene_count

    def test_miss_rate_evaluation(self):
        """Evaluation: compare the built-in global ContentDetector with
        the localized detector on the acceptance segment."""
        if self.inPublicCI():
            self.skipTest("test video not available in public CI")
        if SceneManager is None:
            self.skipTest("scenedetect not installed")
        video_path = get_test_video()
        if video_path is None:
            self.skipTest("test video could not be downloaded")
        global_scenes = self.run_detector(video_path, ContentDetector())
        localized_scenes = self.run_detector(video_path, LocalizedContentDetector())
        print(
            f"PySceneDetect evaluation 20:00-21:00: "
            f"ContentDetector(global)={global_scenes} scenes, "
            f"LocalizedContentDetector(block-MAE)={localized_scenes} scenes"
        )
        self.assertGreaterEqual(localized_scenes, global_scenes)
