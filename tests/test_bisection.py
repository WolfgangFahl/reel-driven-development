"""Created on 2026-07-30.

@author: wf
"""

from typing import Optional

import numpy as np
from basemkit.basetest import Basetest

from rdd.bisection import BisectionSampler
from rdd.blockmae import BlockMAE


class SyntheticSegment:
    """A synthetic video segment with step-function content changes."""

    def __init__(self, change_times, start: float = 0.0, end: float = 60.0):
        """Initialize with the times at which the content changes.

        Args:
            change_times: sorted times (seconds) of content changes.
            start: segment start in seconds.
            end: segment end in seconds.
        """
        self.change_times = change_times
        self.start = start
        self.end = end
        self.frame_step = 1.0 / 25.0
        self.frames_read = 0

    def content_id(self, time_sec: float) -> int:
        """Return the content index active at the given time."""
        index = 0
        for change_time in self.change_times:
            if time_sec >= change_time:
                index += 1
        return index

    def frame_at(self, time_sec: float) -> Optional[np.ndarray]:
        """Render the frame for the content active at the given time."""
        self.frames_read += 1
        frame = np.full((90, 160), 100, dtype=np.uint8)
        index = self.content_id(time_sec)
        frame[10:30, 10 * index : 10 * index + 20] = 250
        return frame


class NoisyCornerSegment(SyntheticSegment):
    """A synthetic segment with a permanently changing corner tile.

    Models a conference share with a live participant tile: the corner
    changes in every frame while the walk content only changes at the
    given change times - the collapse case of issue #5.
    """

    def frame_at(self, time_sec: float) -> Optional[np.ndarray]:
        """Render the walk frame plus the deterministic noisy corner."""
        frame = SyntheticSegment.frame_at(self, time_sec)
        noise = (int(round(time_sec * 10000)) * 2654435761) % 200
        frame[0:30, 140:160] = noise
        return frame


class TestBisection(Basetest):
    """Test the multi-phase bisection sampler."""

    def setUp(self, debug=False, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)

    def test_changes_bracketed(self):
        """Every step change must be bracketed at frame granularity."""
        change_times = [10.0, 20.5, 41.0]
        segment = SyntheticSegment(change_times)
        sampler = BisectionSampler(segment)
        result = sampler.run()
        self.assertEqual(len(change_times), len(result.changes))
        for change_time, bracket in zip(change_times, result.changes):
            self.assertLessEqual(bracket.before, change_time)
            self.assertGreaterEqual(bracket.after + 1e-6, change_time)
            self.assertLessEqual(bracket.after - bracket.before, sampler.granularity)

    def test_cheaper_than_grid(self):
        """Bisection must need far fewer frames than a one-per-second uniform
        grid on a mostly static segment."""
        segment = SyntheticSegment([30.0])
        sampler = BisectionSampler(segment)
        result = sampler.run()
        grid_frames = int(segment.end - segment.start)
        self.assertLess(result.frames_sampled, grid_frames / 2)
        if self.debug:
            print(f"{result.frames_sampled} frames vs {grid_frames} grid")

    def test_absence_proof(self):
        """A target in a static region must yield an absence proof with the
        inspected window recorded."""
        segment = SyntheticSegment([50.0])
        sampler = BisectionSampler(segment)
        result = sampler.run(targets=[15.0])
        self.assertEqual(1, len(result.absences))
        proof = result.absences[0]
        self.assertEqual(15.0, proof.target)
        self.assertGreater(proof.frames_compared, 0)

    def test_target_with_change(self):
        """A target near a change must not yield an absence proof."""
        segment = SyntheticSegment([15.5])
        sampler = BisectionSampler(segment)
        result = sampler.run(targets=[15.0])
        self.assertEqual(0, len(result.absences))
        self.assertEqual(1, len(result.changes))

    def test_region_rescues_noisy_corner(self):
        """Issue #5: a permanently changing corner outside the region must
        yield the same single change as a clean reel, while without a region
        the bisection degenerates into a dense scan."""
        change_times = [5.0]
        region = (0.0, 0.0, 0.875, 1.0)  # excludes the x>=140 corner tile
        clean = SyntheticSegment(change_times, end=10.0)
        clean_result = BisectionSampler(clean).run()
        noisy = NoisyCornerSegment(change_times, end=10.0)
        metric = BlockMAE(region=region)
        region_result = BisectionSampler(noisy, metric).run()
        self.assertEqual(len(clean_result.changes), len(region_result.changes))
        self.assertEqual(1, len(region_result.changes))
        bracket = region_result.changes[0]
        self.assertLessEqual(bracket.before, change_times[0])
        self.assertGreaterEqual(bracket.after + 1e-6, change_times[0])
        degenerate = NoisyCornerSegment(change_times, end=10.0)
        degenerate_result = BisectionSampler(degenerate).run()
        self.assertGreater(len(degenerate_result.changes), 10)
        self.assertGreater(
            degenerate_result.frames_sampled,
            5 * region_result.frames_sampled,
        )
        if self.debug:
            print(
                f"region: {region_result.frames_sampled} frames, "
                f"degenerate: {degenerate_result.frames_sampled} frames"
            )
