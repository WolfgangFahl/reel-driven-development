"""Created on 2026-08-14.

test the reelreview local server

@author: wf
"""

import http.server
import json
import threading
import urllib.request
from pathlib import Path
from typing import Tuple

from basemkit.basetest import Basetest

from rdd.reelreview import ReelReviewHandler


class TestReelReview(Basetest):
    """Test the reelreview server of one recording folder."""

    def setUp(self, debug=False, profile=True):
        """Serve the example recording folder."""
        Basetest.setUp(self, debug=debug, profile=profile)
        folder = Path("examples/recordings/genwiki-walk")
        handler = lambda *a, **kw: ReelReviewHandler(*a, directory=str(folder), **kw)
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        """Stop the server."""
        self.httpd.shutdown()
        self.httpd.server_close()
        Basetest.tearDown(self)

    def get(self, path: str) -> Tuple[int, bytes]:
        """Get the given path from the test server.

        Args:
            path: the path to request.

        Returns:
            status code and body of the response.
        """
        with urllib.request.urlopen(f"{self.base_url}{path}") as response:
            result = (response.status, response.read())
        return result

    def test_api_reel(self):
        """Test that api/reel answers the hop set parsed by the model - a
        summary that PyYAML wrapped over several lines arrives whole."""
        status, body = self.get("/api/reel")
        self.assertEqual(200, status)
        reel_data = json.loads(body)
        self.assertEqual("genwiki-walk", reel_data["recording"]["acronym"])
        self.assertTrue(reel_data["recording"]["summary"].endswith("Kategorie SVG."))
        self.assertEqual(12, len(reel_data["hops"]))

    def test_page_uses_api_reel(self):
        """Test that the served page reads the reel from api/reel and carries
        no YAML parser of its own."""
        status, body = self.get("/")
        self.assertEqual(200, status)
        self.assertIn(b"api/reel", body)
        self.assertNotIn(b"parseReel", body)
