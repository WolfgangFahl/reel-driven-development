"""Created on 2026-08-08.

hop detector over a reel

@author: wf
"""

import os
from datetime import datetime
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
from rdd.frame import Reel, hop_frame_names
from rdd.hopset import HopSet
from rdd.recording import HopContent, HopContents, Recording
from rdd.version import Version


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

    def clear(self, out_dir: str, force: bool) -> Optional[HopSet]:
        """Make sure a hop set is not silently mixed with an older one.

        Writing a hop set over an older one leaves the frames the new run
        does not cut at behind, and the directory then shows a hop set
        that never existed. An existing hop set is therefore kept unless
        it is replaced whole, and replacing it removes the frames the old
        hop set named.

        What a person wrote into the reel file - the name, the acronym,
        the participants - is not a hop set and survives the replacement:
        a detection replaces what it produced, never what it was given.

        Args:
            out_dir: the directory the hop set is written to.
            force: replace an existing hop set instead of keeping it.

        Returns:
            the reel file that was there, None where there was none.

        Raises:
            ValueError: if a hop set is there and force is not given.
        """
        old = HopSet.of_dir(out_dir)
        if old is not None and old.hops:
            if not force:
                raise ValueError(
                    f"{HopSet.path_of(out_dir)} already holds a hop set - "
                    f"use --force to replace it"
                )
            for hop in old.hops:
                if hop.screenshot:
                    frame_path = os.path.join(out_dir, hop.screenshot)
                    if os.path.isfile(frame_path):
                        os.remove(frame_path)
            old.hops = []
        return old

    def recording_of(self, given: Optional[Recording] = None) -> Recording:
        """The Recording record of the reel this run analyzed.

        Args:
            given: the Recording of a reel file written beforehand; its
                values win, because they are what a person knew and the
                reel cannot answer.

        Returns:
            the Recording, with the fields the reel itself can answer
            filled in where the given one leaves them open.
        """
        recording = given if given else Recording()
        if not recording.videoFile:
            recording.videoFile = self.reel.videoFile
        if recording.durationMin is None:
            recording.durationMin = round(self.reel.duration_sec / 60.0, 1)
        return recording

    def hops(
        self,
        config: HopConfig,
        out_dir: Optional[str] = None,
        progress: bool = False,
        force: bool = False,
    ) -> HopContents:
        """Turn the cuts of the given detector into hop records.

        The evidence frame of a hop is the frame the detector cuts at -
        the first frame of the new content. It is named by its offset in
        the reel and never by its position in the run - see issue #21 and
        hop_frame_names. node, url and summary of the walk stay empty:
        they come from the transcript and are never guessed from the
        picture.

        Args:
            config: the values selecting and parameterizing the detector.
            out_dir: directory the evidence frames and the reel.yaml that
                carries them with the values reproducing them are written
                to; a hopless reel.yaml already there is the input of the
                run and its recording values are kept. None writes
                nothing.
            progress: show the tqdm progress bar while detecting.
            force: overwrite a hop set that is already there.

        Returns:
            the hops of this run.

        Raises:
            ValueError: if the output directory already holds a hop set
                and force is not given.
        """
        # no back reference on the hop: the reel file it lives in is the reel
        hop_contents = HopContents()
        given = None
        if out_dir is not None:
            given = self.clear(out_dir, force)
            os.makedirs(out_dir, exist_ok=True)
        frame_nums = self.scenes(config, progress=progress)
        times_sec = [self.reel.time_of(frame_num) for frame_num in frame_nums]
        names = hop_frame_names(times_sec)
        for frame_num, name in zip(frame_nums, names):
            frame = self.reel.frame_at(frame_num)
            screenshot = None
            if out_dir is not None and frame is not None:
                screenshot = name
                frame.save(os.path.join(out_dir, screenshot))
            hop_contents.add(HopContent(time=frame.timecode, screenshot=screenshot))
        if out_dir is not None:
            hop_set = HopSet(
                recording=self.recording_of(given.recording if given else None),
                config=config,
                hops=hop_contents.hops,
            )
            hop_set.save(
                HopSet.path_of(out_dir),
                version=Version.version,
                date=datetime.now().strftime("%Y-%m-%d"),
            )
        return hop_contents
