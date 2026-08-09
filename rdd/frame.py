"""Created on 2026-08-08.

the frame module hides the technical datails of numpy

@author: wf
"""

import os
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np
from scenedetect import open_video

from rdd.recording import Recording


@dataclass
class Region:
    """A rectangular part of a frame.

    The region of interest restricts every judgement to the part of the
    screen that belongs to the walk, so that a permanently changing area
    outside it - live participant tiles, a clock, a scrolling log - can
    not defeat the detection - see issue #5.

    Coordinates are either fractions of the frame (width and height <= 1)
    or pixels; the two forms describe the same area on a given frame.
    """

    x: float = 0.0
    y: float = 0.0
    width: float = 1.0
    height: float = 1.0

    @classmethod
    def of_tuple(cls, values: Tuple[float, float, float, float]) -> "Region":
        """Create a region from an (x, y, width, height) tuple.

        Args:
            values: the four coordinates.

        Returns:
            the Region.
        """
        x, y, width, height = values
        region = cls(x=x, y=y, width=width, height=height)
        return region

    @classmethod
    def of_str(cls, text: str) -> "Region":
        """Create a region from a comma separated string.

        Args:
            text: "x,y,width,height" e.g. "0,0,0.875,1.0".

        Returns:
            the Region.

        Raises:
            ValueError: if the text does not hold four numbers.
        """
        parts = text.split(",")
        if len(parts) != 4:
            raise ValueError(f"region needs four values x,y,width,height - got {text}")
        values = tuple(float(part) for part in parts)
        region = cls.of_tuple(values)  # type: ignore[arg-type]
        return region

    @property
    def is_fractional(self) -> bool:
        """Decide whether the region is given as fractions of the frame.

        Returns:
            True if width and height are fractions.
        """
        fractional = self.width <= 1.0 and self.height <= 1.0
        return fractional

    def bounds(self, width: int, height: int) -> Tuple[int, int, int, int]:
        """Compute the pixel bounds of the region on a frame of the given size.

        Args:
            width: frame width in pixels.
            height: frame height in pixels.

        Returns:
            (y0, y1, x0, x1) crop bounds, clamped to the frame.
        """
        x, y, region_width, region_height = self.x, self.y, self.width, self.height
        if self.is_fractional:
            x, region_width = x * width, region_width * width
            y, region_height = y * height, region_height * height
        x0 = min(max(int(round(x)), 0), width)
        y0 = min(max(int(round(y)), 0), height)
        x1 = min(max(int(round(x + region_width)), x0), width)
        y1 = min(max(int(round(y + region_height)), y0), height)
        bounds = (y0, y1, x0, x1)
        return bounds


class Reel(Recording):
    """A Recording that can be played - the source of frames.

    A reel knows how fast it runs and, where it has one, the stream it
    reads its pictures from. The stream is what is optional here, not the
    reel: a frame always belongs to a reel, while a reel built for a test
    has no video behind it and answers no pictures.

    The video library stays inside this class - callers ask for a frame at
    a position and get a Frame, never a stream, a timecode object or a codec.
    """

    def __init__(self, path: Optional[str] = None, fps: Optional[float] = None):
        """Open a reel, or create one that has no video.

        Args:
            path: path of the video file; None creates a reel without a
                stream, as used by tests and by synthetic frames.
            fps: frames per second; read from the video when a path is
                given, otherwise as given here and None where unknown.

        Raises:
            FileNotFoundError: if a path is given that holds no video file.
        """
        super().__init__()
        if path is not None and not os.path.isfile(path):
            raise FileNotFoundError(f"reel {path} not found in {os.getcwd()}")
        self.path = path
        self.videoFile = os.path.basename(path) if path else None
        self.stream = None
        self.fps = fps
        self.duration_sec = 0.0
        self.frame_count = 0
        self._keyframes: Optional[List[int]] = None
        if path is not None:
            self.stream = open_video(path)
            self.fps = float(self.stream.frame_rate)
            self.duration_sec = float(self.stream.duration.seconds)
            self.frame_count = int(round(self.duration_sec * self.fps))
            self.durationMin = self.duration_sec / 60.0

    def frame_num_of(self, time_sec: float) -> int:
        """Convert a position in seconds to a frame number.

        Args:
            time_sec: the position in seconds.

        Returns:
            the frame number.

        Raises:
            ValueError: if the recording does not know its rate.
        """
        if not self.fps:
            raise ValueError("the recording does not know its frame rate")
        frame_num = int(round(time_sec * self.fps))
        return frame_num

    def time_of(self, frame_num: int) -> Optional[float]:
        """Convert a frame number to a position in seconds.

        Args:
            frame_num: the frame number.

        Returns:
            the position in seconds, or None if the rate is unknown.
        """
        time_sec = None
        if self.fps:
            time_sec = frame_num / self.fps
        return time_sec

    @property
    def keyframes(self) -> List[int]:
        """The frame numbers of the key frames of this recording.

        Key frames are the positions that can be seeked to without
        decoding forward, so they are the cheap probes. The index is
        read once with ffprobe; without a stream or without ffprobe the
        list stays empty and the caller falls back to plain bisection.
        """
        if self._keyframes is None:
            self._keyframes = self._read_keyframes()
        return self._keyframes

    def _read_keyframes(self) -> List[int]:
        """Read the key frame positions with ffprobe.

        Returns:
            the key frame numbers, empty if there is no video or ffprobe
            is not available.
        """
        keyframes: List[int] = []
        if self.path is not None:
            cmd = [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-skip_frame",
                "nokey",
                "-show_entries",
                "frame=pts_time",
                "-of",
                "csv=p=0",
                self.path,
            ]
            try:
                output = subprocess.run(cmd, capture_output=True, text=True, check=True)
                for line in output.stdout.splitlines():
                    text = line.strip().rstrip(",")
                    if text:
                        keyframes.append(self.frame_num_of(float(text)))
            except (OSError, subprocess.CalledProcessError, ValueError):
                keyframes = []
        return keyframes

    def frame_at(self, frame_num: int) -> Optional["Frame"]:
        """Read the frame at the given position.

        Args:
            frame_num: the frame number to read.

        Returns:
            the Frame, or None without a stream or past the end of the recording.
        """
        frame = None
        if self.stream is not None:
            self.stream.seek(frame_num)
            img = self.stream.read()
            if img is not False and img is not None:
                frame = Frame(img=img, frame_num=frame_num, reel=self)
        return frame


class Frame:
    """One picture of a recording together with its position in the recording.

    The pixel representation is an implementation detail: callers ask a
    frame what it shows and where it sits in the recording, never how it is
    stored. The type of a picture is known to its suppliers - the video
    reader handing frames in, make building them - never to its users,
    who only ever pass the picture on as img.
    """

    def __init__(
        self,
        img: np.ndarray,
        frame_num: int = 0,
        reel: Optional[Reel] = None,
    ):
        """Initialize the frame.

        Args:
            img: the picture as a HxW or HxWxC array.
            frame_num: the position of the frame in the recording.
            reel: the reel this picture belongs to; a frame without one is
                given a reel that has neither a stream nor a rate, so that
                a frame always knows its reel.
        """
        self._img = img
        self.frame_num = frame_num
        self.reel = reel if reel is not None else Reel()
        self._gray_cache: Optional[np.ndarray] = None

    @property
    def fps(self) -> Optional[float]:
        """Frames per second of the recording this frame belongs to."""
        fps = self.reel.fps
        return fps

    @property
    def img(self) -> np.ndarray:
        """The picture this frame shows.

        The handle a user passes on without asking what it is made of;
        only frame.py and the suppliers of a picture know its type.
        """
        img = self._img
        return img

    @property
    def width(self) -> int:
        """Width of the frame in pixels."""
        width = int(self._img.shape[1])
        return width

    @property
    def height(self) -> int:
        """Height of the frame in pixels."""
        height = int(self._img.shape[0])
        return height

    @property
    def time_sec(self) -> Optional[float]:
        """Position of the frame in the recording in seconds, if the recording
        knows its rate."""
        time_sec = self.reel.time_of(self.frame_num)
        return time_sec

    @property
    def timecode(self) -> str:
        """Position of the frame as mm:ss, or the frame number if no fps."""
        time_sec = self.time_sec
        if time_sec is None:
            timecode = f"frame {self.frame_num}"
        else:
            minutes, seconds = divmod(int(time_sec), 60)
            timecode = f"{minutes:02d}:{seconds:02d}"
        return timecode

    @property
    def _gray(self) -> np.ndarray:
        """The frame as a float32 grayscale array, computed once.

        Private on purpose: grayscale is how this module happens to
        compare pictures, not something a user of a frame should see.
        """
        if self._gray_cache is None:
            gray = self._img
            if gray.ndim == 3:
                gray = gray.mean(axis=2)
            self._gray_cache = gray.astype(np.float32)
        return self._gray_cache

    def crop(self, region: Optional[Region]) -> "Frame":
        """Restrict the frame to a region of interest.

        Args:
            region: the region; None returns the frame itself.

        Returns:
            a Frame showing only the region.
        """
        cropped = self
        if region is not None:
            y0, y1, x0, x1 = region.bounds(self.width, self.height)
            cropped = Frame(
                img=self._img[y0:y1, x0:x1],
                frame_num=self.frame_num,
                reel=self.reel,
            )
        return cropped

    def is_blank(self, tolerance: float = 1.0) -> bool:
        """Decide whether the frame shows a single uniform color.

        A blank frame is what a browser shows before a page has rendered;
        capturing it as evidence is a false hop - see issue #1.

        Args:
            tolerance: maximum spread in gray levels still counting as blank.

        Returns:
            True if the frame is uniform within the tolerance.
        """
        spread = float(self._gray.max() - self._gray.min())
        blank = spread <= tolerance
        return blank

    @classmethod
    def make(
        cls,
        frame_num: int = 0,
        fps: Optional[float] = 25.0,
        width: int = 1280,
        height: int = 720,
        value: int = 128,
        channels: Optional[int] = None,
    ) -> "Frame":
        """Create a frame of a single uniform color.

        Args:
            frame_num: the position of the frame in the recording.
            fps: frames per second of the recording; None leaves the recording unknown.
            width: frame width in pixels.
            height: frame height in pixels.
            value: the gray level or channel value to fill the frame with.
            channels: number of color channels; None creates a gray frame.

        Returns:
            the Frame.
        """
        shape = (height, width) if channels is None else (height, width, channels)
        img = np.full(shape, value, dtype=np.uint8)
        frame = cls(img=img, frame_num=frame_num, reel=Reel(fps=fps))
        return frame

    def with_rect(self, y0: int, y1: int, x0: int, x1: int, value: int) -> "Frame":
        """Copy the frame with a rectangle painted in a single value.

        Args:
            y0: first row of the rectangle.
            y1: row behind the last row of the rectangle.
            x0: first column of the rectangle.
            x1: column behind the last column of the rectangle.
            value: the gray level or channel value to paint with.

        Returns:
            a Frame showing the painted rectangle.
        """
        img = self._img.copy()
        img[y0:y1, x0:x1] = value
        painted = Frame(img=img, frame_num=self.frame_num, reel=self.reel)
        return painted

    def save(self, path: str) -> bool:
        """Write the frame to an image file.

        Args:
            path: the file path; the suffix selects the format.

        Returns:
            True if the file was written.
        """
        written = cv2.imwrite(path, self._img)
        return written
