"""Created on 2026-08-13.

test the reels of an installation

@author: wf
"""

import os

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
        compatible way from the examples directory.

        The installation configuration decides: where ~/.rdd/rdd_site.yaml
        exists the reels of that installation are loaded - on the Jenkins
        node this is the actual noah configuration; where no configuration
        exists, e.g. on a GitHub Actions runner, the example recordings
        directory of the repository is loaded.
        """
        force_ci = False  # set True to test the public CI path locally
        config_path = os.path.expanduser(RddSiteConfig.DEFAULT_PATH)
        has_config = os.path.isfile(config_path) and not force_ci
        if has_config:
            config = RddSiteConfig.of_path()
            recordings_dir = config.recordings_dir
        else:
            recordings_dir = "examples/recordings"
        reels = Reels.of_dir(recordings_dir)
        if self.debug:
            print(reels.as_summary())
        self.assertEqual({}, reels.errors)
        directory = reels.by_acronym()
        if has_config:
            # the master holds at least 13 reels with at least two demos
            self.assertGreaterEqual(reels.count, 13)
            demos = [reel for reel in reels.reels if reel.is_demo]
            self.assertGreaterEqual(len(demos), 2)
        else:
            # the example genwiki-walk 1 min video is properly loaded and
            # offered as a demo reel
            self.assertGreaterEqual(reels.count, 1)
            genwiki_walk = directory["genwiki-walk"]
            self.assertEqual(12, genwiki_walk.hop_count)
            self.assertTrue(genwiki_walk.is_demo)

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

    def testHopSlugs(self):
        """Test that the hop slug is the frame base name minus its
        extension per #21 - never a path, even for frames in a
        subfolder."""
        from rdd.hopset import HopSet
        from rdd.recording import HopContent

        reel = Reel(
            path="/somewhere/reel",
            hop_set=HopSet(
                hops=[
                    HopContent(pos=1, screenshot="hop-00h02m12s.jpg"),
                    HopContent(pos=2, screenshot="screenshots/walk-home.jpg"),
                ]
            ),
        )
        self.assertEqual(["hop-00h02m12s", "walk-home"], reel.hop_slugs())
