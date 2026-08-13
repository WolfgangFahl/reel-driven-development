"""Created on 2026-08-13.

the directory of reels of an installation - found by scanning a recordings
directory

see the Directory of reels and Reel Review ADRs on
https://media.bitplan.com/index.php/Talk:Rdd.bitplan.com

@author: wf
"""

import os
import time
from dataclasses import field
from typing import Dict, List, Optional

from basemkit.yamlable import lod_storable

from rdd.hopset import HopSet

PUBLIC_STATUSES = {"public", "demo"}


@lod_storable
class Reel:
    """One reel of an installation - the published form of a Recording.

    Per the Unit of reel publication decision the reel is the folder
    with its reel.yaml; the folder name is the identifier a url can
    carry, the hop set is the record the reviews and the document pass
    read back.
    """

    path: str = ""
    hop_set: Optional[HopSet] = None

    @property
    def folder(self) -> str:
        """The name of the reel folder."""
        folder = os.path.basename(self.path)
        return folder

    @property
    def recording(self):
        """The Recording of this reel, None where the reel names none."""
        recording = self.hop_set.recording if self.hop_set else None
        return recording

    @property
    def acronym(self) -> str:
        """The acronym of the reel, the folder name where the reel names
        none."""
        acronym = self.folder
        recording = self.recording
        if recording and recording.acronym:
            acronym = recording.acronym
        return acronym

    @property
    def title(self) -> str:
        """The name of the recording, the acronym where the reel names none."""
        title = self.acronym
        recording = self.recording
        if recording and recording.name:
            title = recording.name
        return title

    @property
    def hop_count(self) -> int:
        """The number of hops of this reel."""
        hop_count = self.hop_set.hopCount if self.hop_set else 0
        return hop_count

    @property
    def status(self) -> str:
        """The status of this reel - the state of its Recording.

        The status continues from the processing states into publication:
        public and demo per the Reel Review decision.
        """
        status = ""
        recording = self.recording
        if recording and recording.state:
            status = recording.state
        return status

    @property
    def is_public(self) -> bool:
        """Whether anyone may inspect this reel."""
        is_public = self.status in PUBLIC_STATUSES
        return is_public

    @property
    def is_demo(self) -> bool:
        """Whether this reel is offered in true inspection mode."""
        is_demo = self.status == "demo"
        return is_demo


@lod_storable
class Reels:
    """The directory of reels below a recordings directory.

    The directory is built at startup by walking for reel.yaml files and
    reading each of them, so what the site offers is what the disk has.
    The walk and the read are timed - a scan that grows with the number
    of reels has to be measurable before a cache is worth its complexity.
    """

    recordings_path: str = ""
    reels: List[Reel] = field(default_factory=list)
    found: int = 0
    walk_time: float = 0.0
    read_time: float = 0.0
    errors: Dict[str, str] = field(default_factory=dict)

    @property
    def count(self) -> int:
        """The number of reels held in memory."""
        count = len(self.reels)
        return count

    @property
    def total_time(self) -> float:
        """The time the whole scan took."""
        total_time = self.walk_time + self.read_time
        return total_time

    @classmethod
    def paths_of(cls, recordings_dir: str) -> List[str]:
        """Get the sorted paths of the reel folders below the given directory.

        A reel folder is a directory carrying a reel.yaml; the walk does
        not descend into a reel folder, so files beside the reel - frames,
        video, document - cost nothing but their directory entry.

        Args:
            recordings_dir: the directory to walk.

        Returns:
            the sorted paths of the reel folders.
        """
        paths = []
        for dir_path, dir_names, file_names in os.walk(recordings_dir):
            if HopSet.FILE_NAME in file_names:
                paths.append(dir_path)
                dir_names.clear()
        paths = sorted(paths)
        return paths

    @classmethod
    def of_dir(cls, recordings_dir: str) -> "Reels":
        """Scan the given directory into the directory of reels.

        Args:
            recordings_dir: the directory holding the reel folders.

        Returns:
            the reels found, with the timings of the scan.
        """
        reels = cls(recordings_path=recordings_dir)
        walk_start = time.time()
        paths = cls.paths_of(recordings_dir)
        reels.walk_time = time.time() - walk_start
        reels.found = len(paths)
        read_start = time.time()
        for path in paths:
            try:
                hop_set = HopSet.of_dir(path)
                reels.reels.append(Reel(path=path, hop_set=hop_set))
            except Exception as ex:
                reels.errors[path] = str(ex)
        reels.read_time = time.time() - read_start
        return reels

    def by_acronym(self) -> Dict[str, Reel]:
        """The directory of reels - the lookup from acronym to reel.

        Returns:
            the lookup from acronym to reel.
        """
        lookup = {reel.acronym: reel for reel in self.reels}
        return lookup

    def visible(self, granted: Optional[List[str]] = None) -> List[Reel]:
        """The reels the holder of the given right may see.

        Anyone sees the public and demo reels; a Review right adds its
        private reels - per the Reel Review decision the access right
        changes the visibility of reels in the reels directory.

        Args:
            granted: the acronyms a Review grants; None for anonymous.

        Returns:
            the visible reels, in the order of the scan.
        """
        granted_set = set(granted) if granted else set()
        visible_reels = [
            reel for reel in self.reels if reel.is_public or reel.acronym in granted_set
        ]
        return visible_reels

    def as_summary(self) -> str:
        """A one line summary of the scan for the service log.

        Returns:
            the counts and timings of this scan.
        """
        summary = (
            f"{self.count} of {self.found} reels from {self.recordings_path} "
            f"in {self.total_time:.3f}s "
            f"(walk {self.walk_time:.3f}s read {self.read_time:.3f}s)"
        )
        if self.errors:
            summary += f" - {len(self.errors)} unreadable"
        return summary
