"""Created on 2026-07-30.

@author: wf
"""

import subprocess
from pathlib import Path
from typing import Optional

TEST_VIDEO_ID = "gVxk-zRb0wQ"
TEST_SEGMENT_START = 1200.0
TEST_SEGMENT_END = 1260.0


def get_test_video(video_id: str = TEST_VIDEO_ID) -> Optional[str]:
    """Provide the acceptance test video from the local cache.

    Downloads via yt-dlp on first use; callers skip their test when the
    video is unavailable (e.g. in public CI).

    Args:
        video_id: the YouTube video id.

    Returns:
        path of the cached video file or None if unavailable.
    """
    cache_dir = Path.home() / ".rdd" / "cache"
    video_path = cache_dir / f"{video_id}.mp4"
    if not video_path.exists():
        cache_dir.mkdir(parents=True, exist_ok=True)
        url = f"https://www.youtube.com/watch?v={video_id}"
        subprocess.run(
            ["yt-dlp", "-f", "mp4", "-o", str(video_path), url],
            check=False,
            capture_output=True,
        )
    result = str(video_path) if video_path.exists() else None
    return result
