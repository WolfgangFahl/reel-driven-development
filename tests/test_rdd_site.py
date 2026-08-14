"""Created on 2026-08-13.

test the reel site - reels directory, main demo, access rights and delivery

@author: wf
"""

import io
import json
import os
import threading
import time
import urllib.error
import urllib.request
import zipfile
from typing import Optional, Tuple

import uvicorn
from basemkit.basetest import Basetest

from rdd.hopset import HopSet
from rdd.rdd_site import RddSiteConfig, ReelSite, Review, Reviews
from rdd.recording import Recording
from rdd.reels import Reel
from rdd.webapp import RateLimit, ReelApp, create_app


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

    def testReviewPageI18n(self):
        """Test that the review page speaks the visitor's language like
        every page of the site - full i18n per the i18n issue; the
        verdict vocabulary of reel-feedback.yaml stays canonical."""
        page = self.site.review_page("de")
        self.assertIn('<html lang="de">', page)
        self.assertIn('const LANG = "de";', page)
        self.assertIn("Reel-Urteil", page)
        self.assertIn("bestätigen", page)
        self.assertIn("<span>über</span>", page)
        # the yaml vocabulary is untouched - the buttons still set canonical verdicts
        self.assertIn("setVerdict('confirm')", page)
        page_en = self.site.review_page()
        self.assertIn('const LANG = "en";', page_en)
        self.assertIn('"reel_verdict": "reel verdict"', page_en)

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
        app = create_app(self.site)
        uv_config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
        self.server = uvicorn.Server(uv_config)
        threading.Thread(target=self.server.run, daemon=True).start()
        while not self.server.started:
            time.sleep(0.01)
        port = self.server.servers[0].sockets[0].getsockname()[1]
        self.base_url = f"http://127.0.0.1:{port}"

    def tearDown(self):
        """Stop the server."""
        self.server.should_exit = True
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
                headers = {
                    key.lower(): value for key, value in response.headers.items()
                }
                result = (response.status, response.read(), headers)
        except urllib.error.HTTPError as http_error:
            headers = {key.lower(): value for key, value in http_error.headers.items()}
            result = (http_error.code, http_error.read(), headers)
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
        self.assertIn("bytes 0-99/", headers["content-range"])
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
        self.assertEqual("hop-00h00m02s.jpg", reel_data["hops"][0]["screenshot"])

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
        status, body, _headers = self.get("/reels/genwiki-walk/hop-00h00m02s")
        self.assertEqual(200, status)
        self.assertIn(b"reelreview", body)
        status, body, _headers = self.get("/reels/2026/05/genwiki-walk/hop-00h00m02s")
        self.assertEqual(200, status)
        self.assertIn(b"reelreview", body)
        status, _body, _headers = self.get("/reels/genwiki-walk/hop-99h99m99s")
        self.assertEqual(404, status)
        status, body, _headers = self.get(f"/reels/{self.TOKEN}/genwiki-walk/hop-00h00m02s")
        self.assertEqual(200, status)
        status, _body, _headers = self.get(f"/reels/{self.TOKEN}/secret-reel/hop-00h00m02s")
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
            self.assertIn("text/html", headers["content-type"], path)
            self.assertIn(b"<span>home</span>", body, path)
            self.assertIn(b"Example of a valid address", body, path)
            self.assertIn(b"/reels/genwiki-walk/", body, path)

    def testDocs(self):
        """Test the OpenAPI docs - /docs and /openapi.json answer and the
        swagger assets come from the site, never from a CDN."""
        status, body, _headers = self.get("/docs")
        self.assertEqual(200, status)
        self.assertIn(b"/static/swagger/swagger-ui-bundle.js", body)
        self.assertNotIn(b"cdn", body.lower())
        status, body, _headers = self.get("/openapi.json")
        self.assertEqual(200, status)
        api = json.loads(body)
        self.assertIn("/reels/{address}/api/files", api["paths"])
        self.assertIn("/reels/{address}/api/{action}", api["paths"])
        status, _body, headers = self.get("/static/swagger/swagger-ui-bundle.js")
        self.assertEqual(200, status)

    def testI18n(self):
        """Test i18n - the browser setting decides the default, ?lang=
        overrides and is remembered, the selector shows a flag."""
        request = urllib.request.Request(f"{self.base_url}/")
        request.add_header("Accept-Language", "de-DE,de;q=0.9,en;q=0.8")
        with urllib.request.urlopen(request) as response:
            body = response.read()
        self.assertIn('<html lang="de"'.encode(), body)
        self.assertIn("Stöbern".encode(), body)
        self.assertIn('class="flag"'.encode(), body)
        request = urllib.request.Request(f"{self.base_url}/?lang=en")
        request.add_header("Accept-Language", "de")
        with urllib.request.urlopen(request) as response:
            body = response.read()
            cookie = response.headers.get("Set-Cookie") or ""
        self.assertIn('<html lang="en"'.encode(), body)
        self.assertIn(b"Browsing", body)
        self.assertIn("lang=en", cookie)

    def testEscapeIsNoEscape(self):
        """Test that a path may not leave its reel folder."""
        status, _body, _headers = self.get("/reels/genwiki-walk/../persons.yaml")
        self.assertEqual(404, status)

    def testReviewPageLanguage(self):
        """Test that the served review page answers in the requested language
        like every other page."""
        status, body, _headers = self.get("/reels/genwiki-walk/review?lang=de")
        self.assertEqual(200, status)
        self.assertIn("Reel-Urteil".encode(), body)
        self.assertIn('<html lang="de">'.encode(), body)

    def testVerdictPage(self):
        """Test that the verdict is its own page per the Reel verdict
        decision - served under its own address, right checked, offering
        the review folder and the zip download."""
        status, body, _headers = self.get("/reels/genwiki-walk/verdict")
        self.assertEqual(200, status)
        self.assertIn(b"reel verdict", body)
        self.assertIn(b'href="./"', body)
        self.assertIn(b'href="api/zip"', body)
        status, _body, _headers = self.get("/reels/secret-reel/verdict")
        self.assertEqual(404, status)
        status, _body, _headers = self.get(f"/reels/{self.TOKEN}/secret-reel/verdict")
        self.assertEqual(200, status)

    def testZip(self):
        """Test that the verdict page's download answers the reel folder as one
        zip, right checked."""
        status, body, headers = self.get("/reels/genwiki-walk/api/zip")
        self.assertEqual(200, status)
        self.assertEqual("application/zip", headers.get("content-type"))
        with zipfile.ZipFile(io.BytesIO(body)) as zip_file:
            names = zip_file.namelist()
        self.assertTrue(any(name.endswith("reel.yaml") for name in names))
        self.assertTrue(all(name.startswith("genwiki-walk/") for name in names))
        status, _body, _headers = self.get("/reels/secret-reel/api/zip")
        self.assertEqual(404, status)


class TestRateLimit(Basetest):
    """Test the rate limit on missed lookups per the Reel Review
    decision - unknown tokens are rate-limited."""

    def testMiss(self):
        """Test the sliding window per client."""
        limit = RateLimit(max_misses=2, window_seconds=60.0)
        self.assertFalse(limit.miss("a", now=0.0))
        self.assertFalse(limit.miss("a", now=1.0))
        self.assertTrue(limit.miss("a", now=2.0))
        # another client has its own window
        self.assertFalse(limit.miss("b", now=2.0))
        # the window has passed
        self.assertFalse(limit.miss("a", now=100.0))

    def testUnknownTokenRateLimited(self):
        """Test that a client probing unknown tokens answers 429 over the
        limit, Retry-After naming the window."""
        config = RddSiteConfig(
            recordings_path="examples/recordings",
            main_demo="genwiki-walk",
        )
        site = ReelSite(config, reviews=Reviews())
        reel_app = ReelApp(site)
        reel_app.tarpit_seconds = 0.0
        reel_app.rate_limit = RateLimit(max_misses=2, window_seconds=60.0)
        uv_config = uvicorn.Config(
            reel_app.app, host="127.0.0.1", port=0, log_level="warning"
        )
        server = uvicorn.Server(uv_config)
        threading.Thread(target=server.run, daemon=True).start()
        while not server.started:
            time.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]
        try:
            statuses = []
            retry_after = None
            for _probe in range(3):
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/reels/no-such-token/"
                )
                try:
                    with urllib.request.urlopen(request) as response:
                        statuses.append(response.status)
                except urllib.error.HTTPError as http_error:
                    statuses.append(http_error.code)
                    retry_after = http_error.headers.get("Retry-After")
            self.assertEqual([404, 404, 429], statuses)
            self.assertEqual("60", retry_after)
        finally:
            server.should_exit = True
