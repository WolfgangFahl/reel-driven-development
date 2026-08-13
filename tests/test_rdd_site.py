"""Created on 2026-08-13.

test the reel site - reels directory, main demo and access rights

@author: wf
"""

from basemkit.basetest import Basetest

from rdd.rdd_site import RddSiteConfig, ReelSite, Review, Reviews
from rdd.reels import Reel


class TestRddSite(Basetest):
    """Test the reel site over the example recordings directory."""

    def setUp(self, debug=False, profile=True):
        """Set up a site over the example recordings directory."""
        Basetest.setUp(self, debug=debug, profile=profile)
        self.config = RddSiteConfig(
            name="rdd-test",
            title="Test Reels",
            copy_right="2026 BITPlan GmbH",
            recordings_path="examples/recordings",
            main_demo="genwiki-walk",
        )
        self.site = ReelSite(self.config, reviews=Reviews())

    def testMainDemo(self):
        """Test that the site offers the example reel as its demo."""
        main_demo = self.site.check_main_demo()
        self.assertEqual("genwiki-walk", main_demo.acronym)
        self.assertTrue(main_demo.is_demo)
        home = self.site.home()
        self.assertIn("Demo", home)
        self.assertIn("/reels/genwiki-walk/", home)

    def testMainDemoRequired(self):
        """Test that a site without its main demo refuses to serve."""
        config = RddSiteConfig(recordings_path="examples/recordings")
        site = ReelSite(config, reviews=Reviews())
        with self.assertRaises(ValueError):
            site.check_main_demo()

    def testReelsDirectory(self):
        """Test that the reels directory lists exactly the public and demo
        reels and that a review right adds its private reels."""
        private_reel = Reel(path="/somewhere/NVK-2026-07-12")
        self.site.reels_found.reels.append(private_reel)
        anonymous_page = self.site.reels()
        self.assertIn("genwiki-walk", anonymous_page)
        self.assertNotIn("NVK-2026-07-12", anonymous_page)
        review = Review(
            token="test-token",
            person="Maria Fahl",
            meeting="CompGen/Usability 2026-07-12",
            reels=["NVK-2026-07-12"],
        )
        review_page = self.site.reels(review)
        self.assertIn("genwiki-walk", review_page)
        self.assertIn("NVK-2026-07-12", review_page)
        self.assertIn("Maria Fahl", review_page)

    def testAboutAndMenu(self):
        """Test that the about page names version, license and repository."""
        about = self.site.about()
        self.assertIn("Apache-2.0", about)
        self.assertIn(self.site.version.version, about)
        self.assertIn("reel-driven-development", about)
        menu_names = [entry.name for entry in self.site.menu()]
        self.assertEqual(["home", "reels", "github", "help", "about"], menu_names)
