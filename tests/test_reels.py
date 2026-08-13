"""Created on 2026-08-13.

test the reels of an installation

@author: wf
"""

from basemkit.basetest import Basetest

from rdd.rdd_site import RddSiteConfig
from rdd.reels import Reel, Reels


class TestReels(Basetest):
    """Test scanning a recordings directory for reels."""

    def setUp(self, debug=True, profile=True):
        """setUp."""
        Basetest.setUp(self, debug=debug, profile=profile)

    def tearDown(self):
        """Remove the temporary recordings directory."""
        Basetest.tearDown(self)

    def testReelsLoading(self):
        """Test loading reels on the current production server or in CI
        compatible way from the examples directory."""
        force_ci = False  # set True to test the public CI path locally
        if Basetest.inPublicCI() or force_ci:
            recordings_dir = "examples/recordings"
        else:
            config = RddSiteConfig.of_path()
            recordings_dir = config.recordings_dir
        reels = Reels.of_dir(recordings_dir)
        if self.debug:
            print(reels.as_summary())
        self.assertEqual({}, reels.errors)
        directory = reels.by_acronym()
        if Basetest.inPublicCI() or force_ci:
            # the example genwiki-walk 1 min video is properly loaded and
            # offered as a demo reel
            self.assertGreaterEqual(reels.count, 1)
            genwiki_walk = directory["genwiki-walk"]
            self.assertEqual(12, genwiki_walk.hop_count)
            self.assertTrue(genwiki_walk.is_demo)
        else:
            # the master holds at least 13 reels with at least two demos
            self.assertGreaterEqual(reels.count, 13)
            demos = [reel for reel in reels.reels if reel.is_demo]
            self.assertGreaterEqual(len(demos), 2)

    def testVisibility(self):
        """Test that the access right changes the visibility of reels in the
        reels directory."""
        reels = Reels.of_dir("examples/recordings")
        demo_reel = reels.by_acronym()["genwiki-walk"]
        private_reel = Reel(path="/somewhere/NVK-2026-07-12")
        reels.reels.append(private_reel)
        self.assertEqual("", private_reel.status)
        self.assertFalse(private_reel.is_public)
        anonymous = reels.visible()
        self.assertIn(demo_reel, anonymous)
        self.assertNotIn(private_reel, anonymous)
        granted = reels.visible(granted=["NVK-2026-07-12"])
        self.assertIn(demo_reel, granted)
        self.assertIn(private_reel, granted)
