"""Created on 2026-08-08.

hop detector over a reel

@author: wf
"""

import os
from typing import Generator, List, Optional, Tuple

from scenedetect import (
    AdaptiveDetector,
    ContentDetector,
    HashDetector,
    HistogramDetector,
    SceneDetector,
    detect,
)

from rdd.frame import Reel
from rdd.recording import HopContent, HopContents


class HopDetector:
    """Detect hops in the reel which e.g might be  scene change."""

    def __init__(self, reel: Reel):
        """Initialize the detector.

        Args:
            reel: the reel to analyze.
        """
        self.reel = reel

    @classmethod
    def get_detectors(cls) -> Generator[Tuple[str, SceneDetector], None, None]:
        """Get the scene detectors on offer.

        The detectors and their measured quality are documented at
        https://www.scenedetect.com/benchmarks/

        Yields:
            the name of the detector and the detector itself
        """
        yield "Adaptive", AdaptiveDetector()
        yield "Content", ContentDetector()
        yield "Hash", HashDetector()
        yield "Histogram", HistogramDetector()
        # the threshold is an 8-bit intensity level every channel must fall
        # below to count as a fade; the library documents it as chosen after
        # the minimum grey/black level of the material - 12 is its default
        # not useable for our material of mostly zoom recordings
        # yield "Threshold 12",ThresholdDetector(threshold=12)
        # yield "Threshold 32",ThresholdDetector(threshold=32)
        # yield "Threshold 64",ThresholdDetector(threshold=64)

    def scenes(
        self,
        detector: SceneDetector,
        start_sec: Optional[float] = None,
        end_sec: Optional[float] = None,
        progress: bool = False,
    ) -> List[int]:
        """Candidate hop positions from the given scene detector.

        Which detector is used is the caller's choice - the library offers
        several and they are benchmarked against each other, so the
        detector is a parameter and never fixed here. Each detector
        carries its own thresholds in its own constructor.

        See https://www.scenedetect.com/benchmarks/

        Args:
            detector: the scene detector to run over the reel.
            start_sec: start of the segment; None starts at the beginning.
            end_sec: end of the segment; None runs to one frame before the
                end, since the opencv backend fails on the last frame of
                some files with an undefined timestamp.
            progress: show the tqdm progress bar of the library - a run
                over a reel takes minutes and must not be silent.

        Returns:
            the frame numbers where the detector cuts, empty without a video.
        """
        candidates: List[int] = []
        if self.reel.path is not None:
            if end_sec is None:
                end_sec = self.reel.duration_sec - 1.0 / self.reel.fps
            scenes = detect(
                self.reel.path,
                detector,
                start_time=start_sec,
                end_time=end_sec,
                show_progress=progress,
            )
            candidates = [int(start.frame_num) for start, _ in scenes]
        return candidates

    def hops(
        self,
        detector: SceneDetector,
        out_dir: Optional[str] = None,
        start_sec: Optional[float] = None,
        end_sec: Optional[float] = None,
        progress: bool = False,
    ) -> HopContents:
        """Turn the cuts of the given detector into hop records.

        The evidence frame of a hop is the frame the detector cuts at -
        the first frame of the new content. node, url and summary of the
        walk stay empty: they come from the transcript and are never
        guessed from the picture.

        Args:
            detector: the scene detector to find the hops with.
            out_dir: directory the evidence frames and hops.yaml are
                written to; None writes nothing.
            start_sec: start of the segment; None starts at the beginning.
            end_sec: end of the segment; None runs to the end.
            progress: show the tqdm progress bar while detecting.

        Returns:
            the hops of this run.
        """
        hop_contents = HopContents(recording=self.reel.videoFile)
        if out_dir is not None:
            os.makedirs(out_dir, exist_ok=True)
        for frame_num in self.scenes(
            detector, start_sec=start_sec, end_sec=end_sec, progress=progress
        ):
            frame = self.reel.frame_at(frame_num)
            pos = len(hop_contents.hops) + 1
            screenshot = None
            if out_dir is not None and frame is not None:
                screenshot = f"hop{pos:02d}.jpg"
                frame.save(os.path.join(out_dir, screenshot))
            hop_contents.add(HopContent(time=frame.timecode, screenshot=screenshot))
        if out_dir is not None:
            hop_contents.save_to_yaml_file(os.path.join(out_dir, "hops.yaml"))
        return hop_contents
