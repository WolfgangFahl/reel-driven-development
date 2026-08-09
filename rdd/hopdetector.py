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

from rdd.config import HopConfig
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
        """Get the detectors on offer.

        A detector at one threshold says nothing about how it answers to
        that threshold, so each is offered around its library default.
        Which value is right can only be decided against a labeled corpus
        - until we have one these are measurements, not claims.

        ThresholdDetector is not on offer: it detects fades to a
        near-black level, which our material of mostly zoom recordings
        does not have.

        The detectors and their measured quality are documented at
        https://www.scenedetect.com/benchmarks/

        Yields:
            the name of the detector and the detector itself
        """
        yield "Adaptive 1.5", AdaptiveDetector(adaptive_threshold=1.5)
        yield "Adaptive", AdaptiveDetector()
        yield "Adaptive 6", AdaptiveDetector(adaptive_threshold=6.0)
        yield "Content 13.5", ContentDetector(threshold=13.5)
        yield "Content", ContentDetector()
        yield "Content 54", ContentDetector(threshold=54.0)
        yield "Hash 0.2", HashDetector(threshold=0.2)
        yield "Hash", HashDetector()
        yield "Hash 0.79", HashDetector(threshold=0.79)
        yield "Histogram 0.025", HistogramDetector(threshold=0.025)
        yield "Histogram", HistogramDetector()
        yield "Histogram 0.1", HistogramDetector(threshold=0.1)

    @classmethod
    def get_detector_names(cls) -> List[str]:
        """Get the names the detectors are on offer under.

        Returns:
            the names, in the order they are offered.
        """
        names = [name for name, _detector in cls.get_detectors()]
        return names

    def get_detector(self, config: HopConfig) -> SceneDetector:
        """Get the detector the given configuration names.

        Args:
            config: the configuration naming the detector.

        Returns:
            the detector on offer under that name.

        Raises:
            ValueError: if the named detector is not on offer.
        """
        detector = None
        for name, candidate in self.get_detectors():
            if name == config.detector:
                detector = candidate
        if detector is None:
            raise ValueError(
                f"detector {config.detector} is not on offer - "
                f"choose one of {self.get_detector_names()}"
            )
        return detector

    def scenes(
        self,
        config: HopConfig,
        progress: bool = False,
    ) -> List[int]:
        """Candidate hop positions from the given scene detector.

        Which detector is used is the caller's choice - the library offers
        several and they are benchmarked against each other, so the
        detector is a parameter and never fixed here. Each detector
        carries its own thresholds in its own constructor.

        See https://www.scenedetect.com/benchmarks/

        Args:
            config: the values selecting and parameterizing the detector;
                end_sec None runs to one frame before the end, since the
                opencv backend fails on the last frame of some files with
                an undefined timestamp.
            progress: show the tqdm progress bar of the library - a run
                over a reel takes minutes and must not be silent.

        Returns:
            the frame numbers where the detector cuts, empty without a video.
        """
        candidates: List[int] = []
        if self.reel.path is not None:
            end_sec = config.end_sec
            if end_sec is None:
                end_sec = self.reel.duration_sec - 1.0 / self.reel.fps
            scenes = detect(
                self.reel.path,
                self.get_detector(config),
                start_time=config.start_sec,
                end_time=end_sec,
                show_progress=progress,
            )
            candidates = [int(start.frame_num) for start, _ in scenes]
        return candidates

    def hops(
        self,
        config: HopConfig,
        out_dir: Optional[str] = None,
        progress: bool = False,
    ) -> HopContents:
        """Turn the cuts of the given detector into hop records.

        The evidence frame of a hop is the frame the detector cuts at -
        the first frame of the new content. node, url and summary of the
        walk stay empty: they come from the transcript and are never
        guessed from the picture.

        Args:
            config: the values selecting and parameterizing the detector.
            out_dir: directory the evidence frames, hops.yaml and the
                config.yaml that reproduces them are written to; None
                writes nothing.
            progress: show the tqdm progress bar while detecting.

        Returns:
            the hops of this run.
        """
        hop_contents = HopContents(recording=self.reel.videoFile)
        if out_dir is not None:
            os.makedirs(out_dir, exist_ok=True)
            config.save_to_yaml_file(os.path.join(out_dir, "config.yaml"))
        for frame_num in self.scenes(config, progress=progress):
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
