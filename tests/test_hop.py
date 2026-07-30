"""Created on 2026-07-30.

@author: wf
"""

from basemkit.basetest import Basetest

from rdd.hop import Hop


class TestHop(Basetest):
    """Test the Hop dataclass."""

    def setUp(self, debug=False, profile=True):
        Basetest.setUp(self, debug=debug, profile=profile)

    def test_hop(self):
        """Test creating a hop with and without optional evidence fields."""
        hop = Hop(pos=1, time="20:00", node="test node")
        self.assertEqual(1, hop.pos)
        self.assertEqual("20:00", hop.time)
        self.assertIsNone(hop.screenshot)
