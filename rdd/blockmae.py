"""Created on 2026-07-30.

@author: wf
"""

from typing import Optional, Tuple

import numpy as np

Region = Tuple[float, float, float, float]


class BlockMAE:
    """Localized change metric: mean absolute error per grid block.

    A global single-scalar frame metric hides small-area UI changes such
    as a dropdown (2-8% of the frame) or a highlighted option (<1%).
    Scoring a grid of blocks keeps such changes above threshold in their
    own block - see issue #1 of reel-driven-development.

    A region of interest restricts the metric to the part of the frame
    that belongs to the walk, so that a permanently changing area
    outside it - live participant tiles, a clock, a scrolling log - can
    not defeat the detection - see issue #5.
    """

    def __init__(
        self,
        blocks_x: int = 16,
        blocks_y: int = 9,
        threshold: float = 12.0,
        region: Optional[Region] = None,
    ):
        """Initialize the block grid, change threshold and region.

        Args:
            blocks_x: number of block columns.
            blocks_y: number of block rows.
            threshold: minimum block score (gray levels) counting as change.
            region: region of interest (x, y, width, height) the metric is
                restricted to; fractional values (width and height <= 1)
                scale with the scored frame, pixel values apply to it
                directly; defaults to the full frame.
        """
        self.blocks_x = blocks_x
        self.blocks_y = blocks_y
        self.threshold = threshold
        self.region = region

    @staticmethod
    def is_fractional(region: Region) -> bool:
        """Decide whether a region is given fractionally.

        Args:
            region: region of interest (x, y, width, height).

        Returns:
            True if width and height are fractions of the frame.
        """
        _x, _y, width, height = region
        fractional = width <= 1.0 and height <= 1.0
        return fractional

    def region_bounds(self, shape: Tuple[int, ...]) -> Tuple[int, int, int, int]:
        """Compute the pixel bounds of the region for a frame shape.

        Args:
            shape: (height, width) of the scored frame.

        Returns:
            (y0, y1, x0, x1) crop bounds, clamped to the frame.
        """
        frame_height, frame_width = shape[0], shape[1]
        x0, y0 = 0, 0
        x1, y1 = frame_width, frame_height
        if self.region is not None:
            x, y, width, height = self.region
            if self.is_fractional(self.region):
                x, width = x * frame_width, width * frame_width
                y, height = y * frame_height, height * frame_height
            x0 = min(max(int(round(x)), 0), frame_width)
            y0 = min(max(int(round(y)), 0), frame_height)
            x1 = min(max(int(round(x + width)), x0), frame_width)
            y1 = min(max(int(round(y + height)), y0), frame_height)
        bounds = (y0, y1, x0, x1)
        return bounds

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
        y0, y1, x0, x1 = self.region_bounds(diff.shape)
        diff = diff[y0:y1, x0:x1]
        height, width = diff.shape
        if height < self.blocks_y or width < self.blocks_x:
            raise ValueError(
                f"region {width}x{height} is smaller than the "
                f"{self.blocks_x}x{self.blocks_y} block grid"
            )
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
