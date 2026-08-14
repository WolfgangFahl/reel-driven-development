"""Created on 2026-08-14.

test the rdd dispatcher

@author: wf
"""

import subprocess
import sys

from basemkit.basetest import Basetest

from rdd.rdd_cmd import SUBCOMMANDS, main


class TestRddCmd(Basetest):
    """Test the rdd dispatcher."""

    def testSubcommands(self):
        """Test that the dispatcher names the four tools of the pipeline."""
        self.assertEqual({"detect", "doc", "review", "site"}, set(SUBCOMMANDS.keys()))
        exit_code = main([])
        self.assertEqual(0, exit_code)

    def testSiteStaysHeadless(self):
        """Test that dispatching to site loads no display dependency - a
        headless serving host has no libGL, so cv2 must stay unloaded."""
        code = (
            "import sys\n"
            "from rdd.rdd_cmd import main\n"
            "main(['site', '-V'])\n"
            "assert 'cv2' not in sys.modules, 'cv2 was loaded'\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True
        )
        self.assertEqual(0, result.returncode, result.stderr)
