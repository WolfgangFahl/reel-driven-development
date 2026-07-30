"""Created on 2026-07-30.

@author: wf
"""

import numpy as np


class BlockMAE:
    """Localized change metric: mean absolute error per grid block.

    A global single-scalar frame metric hides small-area UI changes such
    as a dropdown (2-8% of the frame) or a highlighted option (<1%).
    Scoring a grid of blocks keeps such changes above threshold in their
    own block - see issue #1 of reel-driven-development.
    """

    def __init__(self, blocks_x: int = 16, blocks_y: int = 9, threshold: float = 12.0):
        """Initialize the block grid and change threshold.

        Args:
            blocks_x: number of block columns.
            blocks_y: number of block rows.
            threshold: minimum block score (gray levels) counting as change.
        """
        self.blocks_x = blocks_x
        self.blocks_y = blocks_y
        self.threshold = threshold

    def to_gray(self, frame: np.ndarray) -> np.ndarray:
        """Convert a frame to a float32 grayscale array.

        Args:
            frame: HxW or HxWxC image array.

        Returns:
            HxW float32 grayscale array.
        """
        gray = frame
        if frame.ndim == 3:
            gray = frame.mean(axis=2)
        gray = gray.astype(np.float32)
        return gray

    def block_scores(self, frame_a: np.ndarray, frame_b: np.ndarray) -> np.ndarray:
        """Compute the per-block mean absolute error between two frames.

        Args:
            frame_a: first frame.
            frame_b: second frame of the same shape.

        Returns:
            blocks_y x blocks_x array of block scores.
        """
        gray_a = self.to_gray(frame_a)
        gray_b = self.to_gray(frame_b)
        diff = np.abs(gray_a - gray_b)
        height, width = diff.shape
        height_c = (height // self.blocks_y) * self.blocks_y
        width_c = (width // self.blocks_x) * self.blocks_x
        diff = diff[:height_c, :width_c]
        blocks = diff.reshape(
            self.blocks_y,
            height_c // self.blocks_y,
            self.blocks_x,
            width_c // self.blocks_x,
        )
        scores = blocks.mean(axis=(1, 3))
        return scores

    def score(self, frame_a: np.ndarray, frame_b: np.ndarray) -> float:
        """Compute the localized change score: the maximum block score.

        Args:
            frame_a: first frame.
            frame_b: second frame of the same shape.

        Returns:
            the maximum per-block mean absolute error.
        """
        scores = self.block_scores(frame_a, frame_b)
        max_score = float(scores.max())
        return max_score

    def changed(self, frame_a: np.ndarray, frame_b: np.ndarray) -> bool:
        """Decide whether a localized change happened between two frames.

        Args:
            frame_a: first frame.
            frame_b: second frame of the same shape.

        Returns:
            True if any block score reaches the threshold.
        """
        is_changed = self.score(frame_a, frame_b) >= self.threshold
        return is_changed
