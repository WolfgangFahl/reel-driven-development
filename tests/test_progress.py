"""Created on 2026-08-02.

@author: wf
"""

import io
import json
import tempfile
from contextlib import redirect_stderr
from pathlib import Path

import numpy as np
from basemkit.basetest import Basetest

from rdd.bisection import BisectionSampler
from rdd.hopdetection import main
from rdd.progress import JsonlRenderer, ProgressEmitter
from tests.test_bisection import SyntheticSegment

try:
    import cv2
except ImportError:
    cv2 = None  # type: ignore


class TestProgress(Basetest):
    """Test the progress emitter and its JSONL renderer per issue #7."""

    def setUp(self, debug=False, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)

    def jsonl_events(self, text: str) -> list:
        """Parse JSONL text into the event list, asserting validity.

        Args:
            text: the JSONL text, one JSON object per line.

        Returns:
            list of event dicts.
        """
        events = []
        for line in text.splitlines():
            event = json.loads(line)
            self.assertIn("event", event)
            self.assertIn("t", event)
            events.append(event)
        return events

    def make_test_video(self, path: str) -> bool:
        """Write a synthetic 4 second test video with one content change.

        Args:
            path: output path of the video file.

        Returns:
            True if the video could be written.
        """
        written = False
        if cv2 is not None:
            writer = cv2.VideoWriter(
                path, cv2.VideoWriter_fourcc(*"MJPG"), 25.0, (160, 90)
            )
            if writer.isOpened():
                for index in range(100):
                    frame = np.full((90, 160, 3), 100, dtype=np.uint8)
                    if index >= 25:  # content change at t=1.0
                        frame[20:60, 40:120] = 250
                    writer.write(frame)
                writer.release()
                written = True
        return written

    def test_jsonl_sequence_synthetic(self):
        """The sampler must emit a valid ordered event stream: phases in
        order, brackets for changes, found and absent targets."""
        emitter = ProgressEmitter()
        stream = io.StringIO()
        emitter.attach(JsonlRenderer(stream, progress_every=0.0))
        segment = SyntheticSegment([10.0], end=30.0)
        sampler = BisectionSampler(segment, progress=emitter)
        result = sampler.run(targets=[10.0, 25.0])
        events = self.jsonl_events(stream.getvalue())
        kinds = [event["event"] for event in events]
        phases = [event["phase"] for event in events if event["event"] == "phase"]
        self.assertEqual(["anchors", "targets", "bisection"], phases)
        self.assertIn("sample", kinds)
        self.assertIn("bracket", kinds)
        resolutions = {
            event["pos"]: event["resolution"]
            for event in events
            if event["event"] == "target"
        }
        self.assertEqual({10.0: "found", 25.0: "absent"}, resolutions)
        absent = [
            event
            for event in events
            if event["event"] == "target" and event["resolution"] == "absent"
        ]
        self.assertEqual(1, len(absent))
        self.assertIn("window", absent[0])
        self.assertIn("granularity", absent[0])
        self.assertEqual(1, len(result.changes))

    def test_progress_every_bounds_sample_rate(self):
        """A large --progress-every must suppress sample events while letting
        every other event type pass."""
        emitter = ProgressEmitter()
        stream = io.StringIO()
        emitter.attach(JsonlRenderer(stream, progress_every=3600.0))
        segment = SyntheticSegment([10.0], end=30.0)
        sampler = BisectionSampler(segment, progress=emitter)
        sampler.run()
        events = self.jsonl_events(stream.getvalue())
        samples = [event for event in events if event["event"] == "sample"]
        brackets = [event for event in events if event["event"] == "bracket"]
        self.assertLessEqual(len(samples), 1)
        self.assertEqual(1, len(brackets))

    def test_end_to_end_progress_details(self):
        """Hopdetect --progress-details must write a JSONL file whose run_end
        totals match hops.json."""
        if cv2 is None:
            self.skipTest("opencv not available")
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = str(Path(tmp_dir) / "reel.avi")
            if not self.make_test_video(video_path):
                self.skipTest("MJPG video writer not available")
            out_dir = str(Path(tmp_dir) / "hops")
            details_path = str(Path(tmp_dir) / "progress.jsonl")
            exit_code = main(
                [
                    video_path,
                    "--target",
                    "1.0",
                    "--target",
                    "3.5",
                    "--target-window",
                    "0.5",
                    "--out",
                    out_dir,
                    "--progress-details",
                    details_path,
                    "--progress-every",
                    "0",
                ]
            )
            self.assertEqual(0, exit_code)
            events = self.jsonl_events(Path(details_path).read_text())
            kinds = [event["event"] for event in events]
            for kind in (
                "run_start",
                "phase",
                "sample",
                "bracket",
                "target",
                "hop",
                "run_end",
            ):
                self.assertIn(kind, kinds)
            self.assertEqual("run_start", kinds[0])
            self.assertEqual("run_end", kinds[-1])
            run_start = events[0]
            self.assertIn("parameters", run_start)
            run_end = events[-1]
            with (Path(out_dir) / "hops.json").open() as json_file:
                report = json.load(json_file)
            self.assertEqual(report["frames_sampled"], run_end["frames_sampled"])
            self.assertEqual(len(report["hops"]), run_end["hops"])
            self.assertEqual(len(report["absences"]), run_end["absences"])
            self.assertEqual("ok", run_end["status"])

    def test_progress_bar_redirected(self):
        """Issue #6: hopdetect --progress with redirected output must not emit
        control characters or a percentage, and the final totals line must
        match hops.json."""
        if cv2 is None:
            self.skipTest("opencv not available")
        with tempfile.TemporaryDirectory() as tmp_dir:
            video_path = str(Path(tmp_dir) / "reel.avi")
            if not self.make_test_video(video_path):
                self.skipTest("MJPG video writer not available")
            out_dir = str(Path(tmp_dir) / "hops")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                exit_code = main([video_path, "--progress", "--out", out_dir])
            self.assertEqual(0, exit_code)
            text = stderr.getvalue()
            self.assertNotIn("\r", text)
            self.assertNotIn("\x1b", text)
            self.assertNotIn("%", text)
            with (Path(out_dir) / "hops.json").open() as json_file:
                report = json.load(json_file)
            totals_lines = [
                line for line in text.splitlines() if "frames sampled" in line
            ]
            self.assertEqual(1, len(totals_lines))
            totals = totals_lines[0]
            self.assertIn(f"frames sampled {report['frames_sampled']}", totals)
            self.assertIn(f"hops {len(report['hops'])}", totals)
            self.assertIn(f"absences {len(report['absences'])}", totals)
