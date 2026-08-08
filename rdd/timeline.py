"""Created on 2026-08-08.

showing a detection run as a timeline

@author: wf
"""

from typing import List, Optional

from rdd.hopdetect import Bracket
from rdd.recording import HopContents


class Timeline:
    """A detection run drawn as a strip of the segment.

    One line stands for the whole segment, so where the changes sit and
    how much of the reel is quiet is visible at a glance - which a list of
    intervals does not show.
    """

    QUIET = "─"
    CHANGE = "█"
    OPEN = " "

    def __init__(self, start_sec: float, end_sec: float, width: int = 78):
        """Initialize the timeline for a segment.

        Args:
            start_sec: start of the segment in seconds.
            end_sec: end of the segment in seconds.
            width: width of the strip in characters.
        """
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.width = width
        self.sec_per_char = (
            (end_sec - start_sec) / width if end_sec > start_sec else 0.0
        )

    def column_of(self, time_sec: float) -> int:
        """Find the column a position falls into.

        Args:
            time_sec: the position in seconds.

        Returns:
            the column index, clamped to the strip.
        """
        column = 0
        if self.sec_per_char > 0:
            column = int((time_sec - self.start_sec) / self.sec_per_char)
        column = min(max(column, 0), self.width - 1)
        return column

    @staticmethod
    def timecode_of(time_sec: float) -> str:
        """Format a position as mm:ss.

        Args:
            time_sec: the position in seconds.

        Returns:
            the timecode.
        """
        minutes, seconds = divmod(int(time_sec), 60)
        timecode = f"{minutes:02d}:{seconds:02d}"
        return timecode

    def strip_of(self, brackets: List[Bracket], resolved_sec: float) -> str:
        """Draw the strip of changes and quiet passages.

        Args:
            brackets: the brackets found so far.
            resolved_sec: how much of the segment is decided.

        Returns:
            the strip as a string.
        """
        resolved_columns = int(
            self.width * resolved_sec / (self.end_sec - self.start_sec)
        )
        columns = [
            self.QUIET if index < resolved_columns else self.OPEN
            for index in range(self.width)
        ]
        for bracket in brackets:
            for column in range(
                self.column_of(bracket.start_sec), self.column_of(bracket.end_sec) + 1
            ):
                columns[column] = self.CHANGE
        strip = "".join(columns)
        return strip

    def hop_line(self, hops: Optional[HopContents]) -> str:
        """Draw the hop positions under the strip.

        Args:
            hops: the hops of the run; None draws nothing.

        Returns:
            the hop marker line.
        """
        columns = [" "] * self.width
        if hops is not None:
            for hop in hops.hops:
                label = str(hop.pos)
                column = self.column_of(self.seconds_of(hop.time))
                for offset, char in enumerate(label):
                    if column + offset < self.width:
                        columns[column + offset] = char
        hop_line = "".join(columns)
        return hop_line

    @staticmethod
    def seconds_of(timecode: str) -> float:
        """Convert a mm:ss timecode back to seconds.

        Args:
            timecode: the timecode.

        Returns:
            the position in seconds.
        """
        time_sec = 0.0
        for part in timecode.split(":"):
            time_sec = time_sec * 60.0 + float(part)
        return time_sec

    def render(
        self,
        brackets: List[Bracket],
        resolved_sec: float,
        hops: Optional[HopContents] = None,
    ) -> str:
        """Render the timeline with its axis.

        Args:
            brackets: the brackets found so far.
            resolved_sec: how much of the segment is decided.
            hops: the hops of the run; None draws no hop markers.

        Returns:
            the timeline as a multi line string.
        """
        left = self.timecode_of(self.start_sec)
        right = self.timecode_of(self.end_sec)
        axis = f"{left}{right:>{self.width - len(left)}}"
        lines = [
            axis,
            self.strip_of(brackets, resolved_sec),
            self.hop_line(hops),
        ]
        rendered = "\n".join(lines)
        return rendered
