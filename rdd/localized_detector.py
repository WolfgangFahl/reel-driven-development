"""Created on 2026-07-30.

@author: wf
"""

from typing import List, Optional

import numpy as np

from rdd.blockmae import BlockMAE

try:
    from scenedetect.scene_detector import SceneDetector
except ImportError:
    SceneDetector = object  # type: ignore


class LocalizedContentDetector(SceneDetector):  # type: ignore[misc]
    """PySceneDetect detector flagging localized block-MAE changes.

    The built-in PySceneDetect detectors reduce each frame to a single
    global scalar and miss subtle UI hops such as a dropdown or a
    highlighted option. This detector scores a block grid instead, so a
    change confined to a small screen area still cuts - the upstream
    candidate of issue #1.
    """

    def __init__(self, metric: Optional[BlockMAE] = None, min_scene_len: int = 15):
        """Initialize the detector.

        Args:
            metric: localized change metric; defaults to BlockMAE().
            min_scene_len: minimum frames between two cuts.
        """
        super().__init__()
        self.metric = metric if metric is not None else BlockMAE()
        self.min_scene_len = min_scene_len
        self.last_frame: Optional[np.ndarray] = None
        self.last_cut: Optional[int] = None

    def process_frame(
        self, frame_num: int, frame_img: Optional[np.ndarray]
    ) -> List[int]:
        """Process one frame and report cuts.

        Args:
            frame_num: the frame number.
            frame_img: the frame image or None in stats-only mode.

        Returns:
            list with the cut frame number, usually empty.
        """
        cuts: List[int] = []
        if frame_img is not None:
            if self.last_frame is not None:
                if self.metric.changed(self.last_frame, frame_img):
                    is_far_enough = (
                        self.last_cut is None
                        or frame_num - self.last_cut >= self.min_scene_len
                    )
                    if is_far_enough:
                        cuts = [frame_num]
                        self.last_cut = frame_num
            self.last_frame = frame_img
        return cuts

    def post_process(self, frame_num: int) -> List[int]:
        """Report cuts pending after the last frame.

        Args:
            frame_num: the last frame number.

        Returns:
            an empty list - this detector holds no pending cuts.
        """
        cuts: List[int] = []
        return cuts
