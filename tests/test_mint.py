"""Created on 2026-08-13.

test owner bootstrap and token minting per the Owner bootstrap and
minting ADR

@author: wf
"""

import os
import stat
import tempfile

from basemkit.basetest import Basetest

from rdd.mint import Mint
from rdd.rdd_site import RddSiteConfig, ReelSite, Review, Reviews, serve
from rdd.reels import Reel


class TestMint(Basetest):
    """Test the owner bootstrap and the minting CLI side."""

    def setUp(self, debug=False, profile=True):
        """Set up a fresh site directory."""
        Basetest.setUp(self, debug=debug, profile=profile)
        self.rdd_dir = tempfile.mkdtemp(prefix="rdd-mint-")
        self.config = RddSiteConfig(url="https://reels.example.org")
        self.mint = Mint(self.config, rdd_path=self.rdd_dir)

    def testInitSite(self):
        """Test installation mode - the owner is seeded and the wildcard
        owner token minted exactly once."""
        owner_url = self.mint.init_site(
            "wf", "Wolfgang Fahl", "wf@bitplan.com", "https://www.bitplan.com"
        )
        self.assertTrue(os.path.isfile(self.mint.persons_path))
        self.assertTrue(os.path.isfile(self.mint.reviews_path))
        reviews = Reviews.of_path(self.mint.reviews_path)
        self.assertEqual(1, len(reviews.reviews))
        owner = reviews.reviews[0]
        self.assertEqual("wf", owner.person)
        self.assertTrue(owner.is_wildcard)
        self.assertEqual(32, len(owner.token))
        self.assertEqual(f"https://reels.example.org/reels/{owner.token}", owner_url)
        mode = stat.S_IMODE(os.stat(self.mint.owner_link_path).st_mode)
        self.assertEqual(0o600, mode)
        with open(self.mint.owner_link_path) as owner_link_file:
            self.assertIn(owner_url, owner_link_file.read())
        with self.assertRaises(ValueError):
            self.mint.init_site("wf", "Wolfgang Fahl", "", "")

    def testMintReview(self):
        """Test that minting needs the initialized site and appends a
        review."""
        with self.assertRaises(ValueError):
            self.mint.mint_review("maria")
        self.mint.init_site("wf", "Wolfgang Fahl", "wf@bitplan.com", "")
        url = self.mint.mint_review(
            "maria", meeting="CompGen/Usability 2026-07-12", reels=["NVK-2026-07-12"]
        )
        reviews = Reviews.of_path(self.mint.reviews_path)
        self.assertEqual(2, len(reviews.reviews))
        minted = reviews.reviews[1]
        self.assertEqual("maria", minted.person)
        self.assertEqual(["NVK-2026-07-12"], minted.reels)
        self.assertIn(minted.token, url)

    def testWildcardRight(self):
        """Test that the wildcard grants every reel - visibility and
        access alike."""
        config = RddSiteConfig(
            recordings_path="examples/recordings", main_demo="genwiki-walk"
        )
        site = ReelSite(config, reviews=Reviews())
        private_reel = Reel(path="/somewhere/NVK-2026-07-12")
        site.reels_found.reels.append(private_reel)
        owner = Review(token="owner-token", person="wf", reels=["*"])
        self.assertTrue(site.allowed(private_reel, owner))
        visible = site.reels_found.visible(owner.reels)
        self.assertIn(private_reel, visible)
        self.assertFalse(site.allowed(private_reel, None))

    def testServeRefusesUninitialized(self):
        """Test that a site without reviews.yaml refuses to serve and names the
        init command."""
        config = RddSiteConfig(
            recordings_path="examples/recordings", main_demo="genwiki-walk"
        )
        missing = os.path.join(self.rdd_dir, "reviews.yaml")
        with self.assertRaises(ValueError) as context:
            serve(config, reviews_path=missing)
        self.assertIn("reelsite --init", str(context.exception))
