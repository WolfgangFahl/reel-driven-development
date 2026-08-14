"""Created on 2026-08-13.

test the reel site - reels directory, main demo, access rights and delivery

@author: wf
"""

import http.server
import json
import os
import threading
import urllib.error
import urllib.request
from typing import Optional, Tuple

from basemkit.basetest import Basetest

from rdd.hopset import HopSet
from rdd.rdd_site import RddSiteConfig, ReelSite, ReelSiteHandler, Review, Reviews
from rdd.recording import Recording
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

    def testReviewPageWearsTheSite(self):
        """Test that the served review page wears the site's palette and
        menu - one source, no second copy."""
        self.config.palette = "red"
        site = ReelSite(self.config, reviews=Reviews())
        page = site.review_page()
        self.assertIn("--primary: #F44336;", page)
        self.assertIn("<span>home</span>", page)
        self.assertIn("<span>about</span>", page)

    def testAboutAndMenu(self):
        """Test that the about page names version, license and repository."""
        about = self.site.about()
        self.assertIn("Apache-2.0", about)
        self.assertIn(self.site.version.version, about)
        self.assertIn("reel-driven-development", about)
        menu_names = [entry.name for entry in self.site.menu()]
        self.assertEqual(["home", "reels", "github", "help", "about"], menu_names)


class TestReelDelivery(Basetest):
    """Test reel delivery per the Delivery decision.

    A reel and its files are reachable under /reels/<acronym>/,
    optionally carrying the review token; the site answers the bytes,
    range requests included.
    """

    TOKEN = "maria-test-token"

    def setUp(self, debug=False, profile=True):
        """Serve a site over the example recordings directory."""
        Basetest.setUp(self, debug=debug, profile=profile)
        config = RddSiteConfig(
            recordings_path="examples/recordings",
            main_demo="genwiki-walk",
        )
        # a private reel: the example folder under a second, granted acronym
        secret = Reel(
            path="examples/recordings/genwiki-walk",
            hop_set=HopSet(recording=Recording(acronym="secret-reel")),
        )
        review = Review(token=self.TOKEN, person="Maria Fahl", reels=["secret-reel"])
        self.site = ReelSite(config, reviews=Reviews(reviews=[review]))
        self.site.reels_found.reels.append(secret)
        handler = type("TestHandler", (ReelSiteHandler,), {"site": self.site})
        self.httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.base_url = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        """Stop the server."""
        self.httpd.shutdown()
        self.httpd.server_close()
        Basetest.tearDown(self)

    def get(
        self, path: str, range_header: Optional[str] = None
    ) -> Tuple[int, bytes, dict]:
        """Get the given path from the test server.

        Args:
            path: the path to request.
            range_header: the Range header value, if any.

        Returns:
            status code, body and headers of the response.
        """
        request = urllib.request.Request(f"{self.base_url}{path}")
        if range_header:
            request.add_header("Range", range_header)
        try:
            with urllib.request.urlopen(request) as response:
                result = (response.status, response.read(), dict(response.headers))
        except urllib.error.HTTPError as http_error:
            result = (http_error.code, http_error.read(), dict(http_error.headers))
        return result

    def testReelPageAndFile(self):
        """Test that the demo reel's page and files are delivered."""
        status, body, _headers = self.get("/reels/genwiki-walk/")
        self.assertEqual(200, status)
        self.assertIn(b"reel.yaml", body)
        status, body, _headers = self.get("/reels/genwiki-walk/reel.yaml")
        self.assertEqual(200, status)
        self.assertIn(b"acronym: genwiki-walk", body)

    def testRange(self):
        """Test that range requests are answered so seeking works."""
        status, body, headers = self.get(
            "/reels/genwiki-walk/genwiki-walk.mp4", range_header="bytes=0-99"
        )
        self.assertEqual(206, status)
        self.assertEqual(100, len(body))
        self.assertIn("bytes 0-99/", headers["Content-Range"])
        status, body, _headers = self.get(
            "/reels/genwiki-walk/genwiki-walk.mp4", range_header="bytes=-100"
        )
        self.assertEqual(206, status)
        self.assertEqual(100, len(body))

    def testRight(self):
        """Test that the right decides access - nobody without the right
        reaches a private reel's files."""
        status, _body, _headers = self.get("/reels/secret-reel/")
        self.assertEqual(404, status)
        status, _body, _headers = self.get("/reels/secret-reel/reel.yaml")
        self.assertEqual(404, status)
        status, body, _headers = self.get(f"/reels/{self.TOKEN}/secret-reel/")
        self.assertEqual(200, status)
        status, body, _headers = self.get(f"/reels/{self.TOKEN}")
        self.assertEqual(200, status)
        self.assertIn(b"secret-reel", body)
        self.assertIn(b"Maria Fahl", body)

    def post(self, path: str, body: bytes) -> int:
        """Post the given body to the test server.

        Args:
            path: the path to post to.
            body: the request body.

        Returns:
            the status code of the response.
        """
        request = urllib.request.Request(f"{self.base_url}{path}", data=body)
        try:
            with urllib.request.urlopen(request) as response:
                status = response.status
        except urllib.error.HTTPError as http_error:
            status = http_error.code
        return status

    def testReviewPage(self):
        """Test that the review of a reel is one link away and right
        checked - the packaged page, never a copy."""
        status, body, _headers = self.get("/reels/genwiki-walk/")
        self.assertEqual(200, status)
        self.assertIn(b'<a href="review">review</a>', body)
        self.assertIn(b"<b>summary</b>", body)
        status, body, _headers = self.get("/reels/genwiki-walk/review")
        self.assertEqual(200, status)
        self.assertIn(b"reelreview", body)
        status, _body, _headers = self.get("/reels/secret-reel/review")
        self.assertEqual(404, status)
        status, body, _headers = self.get(f"/reels/{self.TOKEN}/secret-reel/review")
        self.assertEqual(200, status)
        self.assertIn(b"reelreview", body)

    def testReviewApi(self):
        """Test that the site answers the read api of the review page."""
        status, body, _headers = self.get("/reels/genwiki-walk/api/files")
        self.assertEqual(200, status)
        files = json.loads(body)
        self.assertIn("reel.yaml", files)
        status, body, _headers = self.get("/reels/genwiki-walk/api/info")
        self.assertEqual(200, status)
        info = json.loads(body)
        self.assertEqual("genwiki-walk", info["acronym"])
        # api/reel answers the hop set parsed by the model, so a summary
        # that PyYAML wrapped over several lines arrives whole
        status, body, _headers = self.get("/reels/genwiki-walk/api/reel")
        self.assertEqual(200, status)
        reel_data = json.loads(body)
        self.assertEqual("genwiki-walk", reel_data["recording"]["acronym"])
        self.assertTrue(reel_data["recording"]["summary"].endswith("Kategorie SVG."))
        self.assertEqual(12, len(reel_data["hops"]))
        self.assertEqual("hop01.jpg", reel_data["hops"][0]["screenshot"])

    def testStaleCopyIsShadowed(self):
        """Test that a reelreview.html in a reel folder is neither listed
        nor served - the packaged page answers instead."""
        stale_path = "examples/recordings/genwiki-walk/reelreview.html"
        with open(stale_path, "w") as stale_file:
            stale_file.write("stale copy")
        try:
            status, body, _headers = self.get("/reels/genwiki-walk/api/files")
            self.assertEqual(200, status)
            self.assertNotIn("reelreview.html", json.loads(body))
            status, body, _headers = self.get("/reels/genwiki-walk/reelreview.html")
            self.assertEqual(200, status)
            self.assertNotIn(b"stale copy", body)
            self.assertIn(b"reelreview", body)
        finally:
            os.remove(stale_path)

    def testSaveStoresNothing(self):
        """Test true inspection mode - a save answers success and the
        reel.yaml stays untouched."""
        reel_yaml_path = "examples/recordings/genwiki-walk/reel.yaml"
        with open(reel_yaml_path, "rb") as reel_yaml_file:
            before = reel_yaml_file.read()
        status = self.post("/reels/genwiki-walk/api/save", b"changed: yaml")
        self.assertEqual(200, status)
        status = self.post(f"/reels/{self.TOKEN}/secret-reel/api/feedback", b"note")
        self.assertEqual(200, status)
        status = self.post("/reels/secret-reel/api/save", b"denied")
        self.assertEqual(404, status)
        with open(reel_yaml_path, "rb") as reel_yaml_file:
            after = reel_yaml_file.read()
        self.assertEqual(before, after)

    def testHopUrl(self):
        """Test the Hop url decision - shortcut and lengthy PID iri
        answer the review, a slug naming no hop is 404."""
        status, body, _headers = self.get("/reels/genwiki-walk/hop01")
        self.assertEqual(200, status)
        self.assertIn(b"reelreview", body)
        status, body, _headers = self.get("/reels/2026/05/genwiki-walk/hop01")
        self.assertEqual(200, status)
        self.assertIn(b"reelreview", body)
        status, _body, _headers = self.get("/reels/genwiki-walk/hop-99h99m99s")
        self.assertEqual(404, status)
        status, body, _headers = self.get(f"/reels/{self.TOKEN}/genwiki-walk/hop01")
        self.assertEqual(200, status)
        status, _body, _headers = self.get(f"/reels/{self.TOKEN}/secret-reel/hop01")
        self.assertEqual(404, status)
        status, body, _headers = self.get("/reels/2026/05/genwiki-walk/reel.yaml")
        self.assertEqual(200, status)
        self.assertIn(b"acronym: genwiki-walk", body)
        status, _body, _headers = self.get("/reels/2026/06/genwiki-walk/")
        self.assertEqual(404, status)

    def testReelPageRedirectsToTrailingSlash(self):
        """Test that a reel page without trailing slash redirects, so the
        relative review and file links resolve below the reel."""
        request = urllib.request.Request(f"{self.base_url}/reels/genwiki-walk")
        with urllib.request.urlopen(request) as response:
            self.assertEqual("/reels/genwiki-walk/", response.url[len(self.base_url) :])
        request = urllib.request.Request(
            f"{self.base_url}/reels/{self.TOKEN}/genwiki-walk"
        )
        with urllib.request.urlopen(request) as response:
            self.assertEqual(
                f"/reels/{self.TOKEN}/genwiki-walk/",
                response.url[len(self.base_url) :],
            )

    def testReelsTrailingSlash(self):
        """Test that /reels/ answers the directory like /reels."""
        status, body, _headers = self.get("/reels/")
        self.assertEqual(200, status)
        self.assertIn(b"genwiki-walk", body)

    def testFramed404(self):
        """Test the framed 404 - it shows like any other page, with an
        example of a valid address, on pages and reels alike."""
        for path in ("/nosuchpage", "/reels/nosuchreel/", "/reels/nosuchreel/x.y"):
            status, body, headers = self.get(path)
            self.assertEqual(404, status, path)
            self.assertIn("text/html", headers["Content-Type"], path)
            self.assertIn(b"<span>home</span>", body, path)
            self.assertIn(b"Example of a valid address", body, path)
            self.assertIn(b"/reels/genwiki-walk/", body, path)

    def testEscapeIsNoEscape(self):
        """Test that a path may not leave its reel folder."""
        status, _body, _headers = self.get("/reels/genwiki-walk/../persons.yaml")
        self.assertEqual(404, status)
