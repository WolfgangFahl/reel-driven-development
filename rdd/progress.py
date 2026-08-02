"""Created on 2026-08-02.

@author: wf
"""

import json
import sys
import time
from typing import IO, List, Optional

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None  # type: ignore


def mmss(time_sec: float) -> str:
    """Format seconds as MM:SS.

    Args:
        time_sec: time in seconds.

    Returns:
        zero-padded MM:SS string.
    """
    minutes = int(time_sec) // 60
    seconds = int(time_sec) % 60
    formatted = f"{minutes:02d}:{seconds:02d}"
    return formatted


class ProgressEmitter:
    """Single progress source of a hop detection run per issues #6/#7.

    Emits structured events to attached renderers so that the human
    progress bar and the machine-readable JSONL stream can never
    disagree about the state of a run. The bisection is adaptive, so no
    completion fraction is ever invented: events carry only what is
    actually known at each moment.
    """

    def __init__(self):
        """Initialize the emitter with an empty renderer list."""
        self.renderers: List = []
        self.start_monotonic = time.monotonic()

    def attach(self, renderer) -> None:
        """Attach a renderer receiving every event via handle(event).

        Args:
            renderer: object with a handle(event: dict) method.
        """
        self.renderers.append(renderer)

    def emit(self, event: str, pos: Optional[float] = None, **fields) -> None:
        """Emit an event to all attached renderers.

        Args:
            event: the event type, e.g. run_start, phase, sample,
                bracket, target, hop, run_end.
            pos: position in the reel in seconds, where one applies.
            **fields: event type specific fields.
        """
        record = {
            "event": event,
            "t": round(time.monotonic() - self.start_monotonic, 3),
        }
        if pos is not None:
            record["pos"] = round(pos, 3)
        record.update(fields)
        for renderer in self.renderers:
            renderer.handle(record)


class JsonlRenderer:
    """Machine-readable progress renderer per issue #7.

    Writes one JSON object per line, flushed per event, so that an agent
    driving the run can abort a degenerate run early and account for
    proven-absence claims at the moment they are made.
    """

    def __init__(self, stream: IO, progress_every: float = 1.0):
        """Initialize the renderer.

        Args:
            stream: text stream the JSONL is written to.
            progress_every: minimum seconds between sample events so
                long runs do not flood the log; other events always
                pass.
        """
        self.stream = stream
        self.progress_every = progress_every
        self.last_sample_t = -progress_every

    def handle(self, event: dict) -> None:
        """Write an event as one JSON line.

        Args:
            event: the event record.
        """
        if event["event"] == "sample":
            if event["t"] - self.last_sample_t < self.progress_every:
                return
            self.last_sample_t = event["t"]
        json.dump(event, self.stream)
        self.stream.write("\n")
        self.stream.flush()


class TqdmRenderer:
    """Human progress renderer per issue #6.

    Phase 1 (anchors, targets) has a known count and is shown as a
    determinate bar. Phase 2 (bisection) is adaptive - its total is not
    known when the run starts, so a percentage would be a fabrication:
    it is shown as an indeterminate display carrying the quantities
    that are actually known. Bars render only on a TTY, so redirected
    output stays clean.
    """

    def __init__(self, stream: Optional[IO] = None):
        """Initialize the renderer.

        Args:
            stream: stream the bars render to; defaults to stderr.

        Raises:
            ImportError: if tqdm is not available.
        """
        if tqdm is None:
            raise ImportError("tqdm is required for the progress bar")
        self.stream = stream if stream is not None else sys.stderr
        self.bar = None

    def close_bar(self) -> None:
        """Close the current bar if one is open."""
        if self.bar is not None:
            self.bar.close()
            self.bar = None

    def handle(self, event: dict) -> None:
        """Render an event.

        Args:
            event: the event record.
        """
        kind = event["event"]
        if kind == "phase":
            self.close_bar()
            phase = event["phase"]
            if phase in ("anchors", "targets"):
                self.bar = tqdm(
                    total=event.get("total"),
                    desc=phase,
                    file=self.stream,
                    disable=None,
                    leave=False,
                )
            elif phase == "bisection":
                self.bar = tqdm(
                    desc=phase,
                    file=self.stream,
                    disable=None,
                    leave=False,
                    bar_format="{desc}: {n} samples {postfix} [{elapsed}]",
                )
        elif kind == "sample" and self.bar is not None:
            if self.bar.total is None:
                postfix = (
                    f"frames {event['frames']}, "
                    f"brackets {event.get('brackets', 0)}, "
                    f"open {event['open']}, "
                    f"at {mmss(event.get('pos', 0.0))}"
                )
                self.bar.set_postfix_str(postfix, refresh=False)
            self.bar.update(1)
        elif kind == "run_end":
            self.close_bar()
            totals = (
                f"frames sampled {event['frames_sampled']}, "
                f"brackets {event['brackets']}, "
                f"groups {event['groups']}, "
                f"hops {event['hops']}, "
                f"absences {event['absences']}, "
                f"wall {event['t']}s"
            )
            self.stream.write(totals + "\n")
            self.stream.flush()
