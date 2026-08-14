"""Created on 2026-08-12.

the site of an organization's reel driven development videos - home page, menu and about

see https://media.bitplan.com/index.php/Talk:Rdd.bitplan.com
ADRs: Review UI stack, Home page and menu

@author: wf
"""

import html
import http.server
import json
import mimetypes
import os
import re
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from basemkit.yamlable import lod_storable

from rdd.icons import svg
from rdd.palette import Palette, Palettes
from rdd.reelreview import page_path
from rdd.reels import Reel, Reels
from rdd.version import Version


@lod_storable
class RddSiteConfig:
    """Everything an organization configures to run its own reel site.

    One yaml is the whole configuration - the site names itself, its
    repository, its documentation, the palette it wears and its recordings
    directory, so a stranger's site names their project and not ours.

    The reels are not configured: the site names the recordings directory
    and the reels are what that directory holds, so publishing a reel is
    putting its folder there. main_demo names the demo the home page
    offers - a site has at least one reel in demo status.
    """

    DEFAULT_PATH = "~/.rdd/rdd_site.yaml"

    name: str = "reels"
    title: str = "Reels"
    intro: str = ""
    url: str = ""
    palette: str = "indigo"
    copy_right: str = ""
    cm_url: str = Version.cm_url
    doc_url: str = Version.doc_url
    port: int = 9925
    recordings_path: str = "~/.rdd/recordings"
    main_demo: str = ""
    max_reels_space_gb: int = 100
    reels_url_prefix: str = "/reels/"

    @classmethod
    def of_file(cls, path: str) -> "RddSiteConfig":
        """Load the site configuration from the given yaml file."""
        config = cls.load_from_yaml_file(path)
        return config

    @classmethod
    def of_path(cls, path: Optional[str] = None) -> "RddSiteConfig":
        """Load the site configuration from the given yaml file.

        Args:
            path: the configuration file; the default path when None.

        Returns:
            the configuration; the default configuration where no file exists.
        """
        config_path = os.path.expanduser(path or cls.DEFAULT_PATH)
        if os.path.isfile(config_path):
            config = cls.of_file(config_path)
        else:
            config = cls()
        return config

    @property
    def recordings_dir(self) -> str:
        """The recordings directory with the user's home resolved."""
        recordings_dir = os.path.expanduser(self.recordings_path)
        return recordings_dir


@lod_storable
class Person:
    """One person of a site - the seed minimum of the Owner bootstrap
    decision.

    The username is the key; full name, email and url are what a site
    needs to address its people.
    """

    username: str = ""
    name: str = ""
    email: str = ""
    url: str = ""


@lod_storable
class Persons:
    """The persons of a site."""

    DEFAULT_PATH = "~/.rdd/persons.yaml"

    persons: List[Person] = field(default_factory=list)

    @classmethod
    def of_path(cls, path: Optional[str] = None) -> "Persons":
        """Load the persons from the given yaml file.

        Args:
            path: the persons file; the default path when None.

        Returns:
            the persons; none where no file exists.
        """
        persons_path = os.path.expanduser(path or cls.DEFAULT_PATH)
        if os.path.isfile(persons_path):
            persons = cls.load_from_yaml_file(persons_path)
        else:
            persons = cls()
        return persons


@lod_storable
class Review:
    """One review right - a reviewer and the reels their link grants.

    Per the Reel Review decision the review rights are not modeled in
    SMW (yet) but kept as entities the rdd site must keep track of.
    Per the Owner bootstrap decision the owner's Review grants the
    wildcard '*' - every reel, including future ones.
    """

    WILDCARD = "*"

    token: str = ""
    person: str = ""
    meeting: str = ""
    reels: List[str] = field(default_factory=list)

    @property
    def is_wildcard(self) -> bool:
        """Whether this review grants every reel."""
        is_wildcard = self.WILDCARD in self.reels
        return is_wildcard


@lod_storable
class Reviews:
    """The review rights of a site."""

    DEFAULT_PATH = "~/.rdd/reviews.yaml"

    reviews: List[Review] = field(default_factory=list)

    @classmethod
    def of_path(cls, path: Optional[str] = None) -> "Reviews":
        """Load the reviews from the given yaml file.

        Args:
            path: the reviews file; the default path when None.

        Returns:
            the reviews; no reviews where no file exists.
        """
        reviews_path = os.path.expanduser(path or cls.DEFAULT_PATH)
        if os.path.isfile(reviews_path):
            reviews = cls.load_from_yaml_file(reviews_path)
        else:
            reviews = cls()
        return reviews

    def by_token(self) -> Dict[str, Review]:
        """The lookup from token to review.

        Returns:
            the lookup from token to review.
        """
        lookup = {review.token: review for review in self.reviews}
        return lookup


@dataclass
class MenuEntry:
    """One entry of the menu."""

    name: str
    target: str
    icon: str
    new_tab: bool = False

    def as_html(self) -> str:
        """Render the entry as an icon labelled link button.

        Returns:
            the anchor markup carrying the material icon and the name.
        """
        target = html.escape(self.target)
        new_tab = " target=_blank" if self.new_tab else ""
        markup = (
            f'      <a href="{target}"{new_tab}>{svg(self.icon)}'
            f"<span>{html.escape(self.name)}</span></a>"
        )
        return markup


class ReelSite:
    """The pages of a reel site.

    The layout is the one the BITPlan applications share - a menu with home,
    github, help and about, a footer with copyright and version, per the Home
    page and menu decision. It is rendered here rather than imported so that a
    reel site needs python and nothing else.
    """

    def __init__(
        self,
        config: RddSiteConfig,
        version: Optional[Version] = None,
        reels: Optional[Reels] = None,
        reviews: Optional[Reviews] = None,
    ):
        """Initialize with the site configuration.

        Args:
            config: the configuration of this site.
            version: version info of the software; defaults to the package version.
            reels: the reels of this site; scanned from the configuration when None.
            reviews: the review rights of this site; loaded from the default
                path when None.
        """
        self.config = config
        self.version = version or Version()
        self.palette: Palette = Palettes.of_resource().by_name(config.palette)
        self.reels_found = reels if reels is not None else self.scan()
        self.reviews = reviews if reviews is not None else Reviews.of_path()

    def scan(self) -> Reels:
        """Scan the recordings directory of this site into its directory of
        reels.

        Returns:
            the reels the recordings directory holds.
        """
        reels = Reels.of_dir(self.config.recordings_dir)
        return reels

    def check_main_demo(self) -> Reel:
        """Get the mandatory main demo of this site.

        Returns:
            the reel the configuration names as main_demo.

        Raises:
            ValueError: where main_demo is unset, unknown or not in demo
                status - a site has at least one demo.
        """
        directory = self.reels_found.by_acronym()
        main_demo = directory.get(self.config.main_demo)
        if main_demo is None:
            raise ValueError(
                f"main_demo '{self.config.main_demo}' is not a reel of "
                f"{self.config.recordings_dir}"
            )
        if not main_demo.is_demo:
            raise ValueError(
                f"main_demo '{self.config.main_demo}' has status "
                f"'{main_demo.status}' - demo is required"
            )
        return main_demo

    def reel_url(self, reel: Reel, review: Optional[Review] = None) -> str:
        """The url this site serves the given reel under.

        Per the Delivery decision the acronym is the only address a url
        needs; a review link carries its token before the acronym.

        Args:
            reel: the reel.
            review: the review whose token the url carries; None for the
                public url.

        Returns:
            the url of the reel.
        """
        prefix = self.config.reels_url_prefix
        if review:
            prefix = f"{prefix}{review.token}/"
        url = f"{prefix}{reel.acronym}/"
        return url

    def allowed(self, reel: Reel, review: Optional[Review] = None) -> bool:
        """Whether the holder of the given right may inspect the reel.

        Args:
            reel: the reel.
            review: the review right; None for anonymous.

        Returns:
            True for a public or demo reel, or a reel the review grants -
            every reel where the review grants the wildcard.
        """
        granted = review.reels if review else []
        allowed = (
            reel.is_public or Review.WILDCARD in granted or reel.acronym in granted
        )
        return allowed

    def reel_files(self, reel: Reel) -> List[str]:
        """The files of the given reel folder.

        Args:
            reel: the reel.

        Returns:
            the sorted file names, hidden files and the review page
            excluded - the review page is code of the package, never
            data of a reel.
        """
        names = [
            name
            for name in sorted(os.listdir(reel.path))
            if not name.startswith(".")
            and name != "reelreview.html"
            and os.path.isfile(os.path.join(reel.path, name))
        ]
        return names

    def reel_page(self, reel: Reel) -> str:
        """The page of one reel - what it is and the files it carries.

        The review and file links are relative so a review link keeps
        its token.

        Args:
            reel: the reel.

        Returns:
            the reel page.
        """
        recording = reel.recording
        summary = recording.summary if recording and recording.summary else ""
        rows = "\n".join(
            f'<tr><td><a href="{html.escape(urllib.parse.quote(name))}">'
            f"{html.escape(name)}</a></td>"
            f"<td>{os.path.getsize(os.path.join(reel.path, name))}</td></tr>"
            for name in self.reel_files(reel)
        )
        content = (
            f"<h2>{html.escape(reel.title)}</h2>\n"
            '<p><a href="review">review</a></p>\n'
            f'<div class="card">\n<b>summary</b><br>\n{html.escape(summary)}\n</div>\n'
            f'<div class="card">\n<table>\n'
            f"<tr><th>file</th><th>bytes</th></tr>\n{rows}\n</table>\n</div>"
        )
        page = self.page(reel.acronym, content)
        return page

    def review_page(self) -> str:
        """The review page of this site.

        Per the Review UI stack decision the packaged page is one
        self-contained file; serving it, the site derives the CSS
        variables from its named palette and puts its own menu into
        the marked header slot, so the review wears the same palette
        and menu as every other page of the site - one source, no
        second copy to keep in step.

        Returns:
            the review page in the site's palette with the site's menu.
        """
        page = page_path().read_text()
        for name, value in self.palette.__dict__.items():
            page = re.sub(rf"--{name}: #[0-9A-Fa-f]+;", f"--{name}: {value};", page)
        links = "\n".join(entry.as_html() for entry in self.menu())
        page = re.sub(
            r"<!-- menu -->.*?<!-- /menu -->",
            f"<!-- menu -->\n{links}\n  <!-- /menu -->",
            page,
            flags=re.DOTALL,
        )
        return page

    def menu(self) -> List[MenuEntry]:
        """The menu entries - settings and chat are dropped, a visitor has neither."""
        entries = [
            MenuEntry("home", "/", "home"),
            MenuEntry("reels", "/reels", "movie"),
            MenuEntry("github", self.config.cm_url, "bug_report", new_tab=True),
            MenuEntry("help", self.config.doc_url, "help", new_tab=True),
            MenuEntry("about", "/about", "info"),
        ]
        return entries

    def style(self) -> str:
        """The stylesheet, derived from the named palette."""
        css = f""":root {{
{self.palette.as_css()}
  --bg: #fafafa; --fg: #222; --card: #fff; --border: #ccc;
}}
@media (prefers-color-scheme: dark) {{
  :root {{ --bg: var(--dark); --fg: #ddd; --card: #2a2a2a; --border: #555; }}
}}
body {{ margin: 0; font-family: system-ui, sans-serif; background: var(--bg); color: var(--fg); }}
header {{ display: flex; gap: .6em; align-items: center; padding: .5em .8em; background: var(--primary); color: #fff; flex-wrap: wrap; }}
header h1 {{ font-size: 1.1em; margin: 0 .4em 0 0; }}
header a {{ display: inline-flex; align-items: center; gap: .35em; color: #fff; text-decoration: none; border: 1px solid rgba(255,255,255,.5); border-radius: 4px; padding: .2em .7em; font-size: .9em; }}
header a:hover {{ background: var(--accent); }}
.hamburger {{ display: inline-flex; align-items: center; background: none; border: none; color: #fff; cursor: pointer; padding: .1em; }}
.hamburger.collapsed {{ position: fixed; top: .4em; left: .4em; z-index: 10; background: var(--primary); border-radius: 4px; padding: .25em; }}
body.collapsed header, body.collapsed footer {{ display: none; }}
main {{ padding: 1em; max-width: 55em; }}
main h2 {{ font-size: 1.2em; }}
main a {{ color: var(--primary); }}
.card {{ background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: .8em; margin-bottom: .8em; }}
footer {{ padding: .5em .8em; border-top: 1px solid var(--border); font-size: .85em; color: var(--info); }}
table {{ border-collapse: collapse; }}
td, th {{ text-align: left; padding: .2em .8em .2em 0; }}
"""
        return css

    def page(self, title: str, content: str) -> str:
        """Render a page with menu and footer.

        Args:
            title: title of the page.
            content: the html of the page body.

        Returns:
            the complete html page.
        """
        links = "\n".join(entry.as_html() for entry in self.menu())
        site_title = html.escape(self.config.title)
        menu_icon = svg("menu")
        page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{site_title} - {html.escape(title)}</title>
<style>
{self.style()}</style>
</head>
<body>
<button class="hamburger collapsed" id="unhide" onclick="toggleMenu()" title="show menu" hidden>{menu_icon}</button>
<header>
  <button class="hamburger" onclick="toggleMenu()" title="hide menu">{menu_icon}</button>
  <h1>{site_title}</h1>
{links}
</header>
<main>
{content}
</main>
<footer>{html.escape(self.config.copy_right)} - {self.version.name} {self.version.version}</footer>
<script>
function toggleMenu() {{
  const collapsed = document.body.classList.toggle('collapsed');
  document.getElementById('unhide').hidden = !collapsed;
}}
</script>
</body>
</html>
"""
        return page

    def demo_card(self) -> str:
        """The demo section of the home page - the main_demo of this site.

        Returns:
            the demo card markup; empty where the main_demo does not
            resolve, so a misconfigured site still serves its home page.
        """
        card = ""
        directory = self.reels_found.by_acronym()
        main_demo = directory.get(self.config.main_demo)
        if main_demo and main_demo.is_demo:
            url = self.reel_url(main_demo)
            card = (
                '<h2>Demo</h2>\n<div class="card">\n'
                f'See a reel for yourself: <a href="{html.escape(url)}">'
                f"{html.escape(main_demo.title)}</a> "
                f"({main_demo.hop_count} hops) - inspect it in true "
                "inspection mode; your verdicts stay on your device.\n</div>"
            )
        return card

    def home(self) -> str:
        """The home page - what this site is and the two ways in."""
        intro = self.config.intro or (
            "This site keeps the reels of recorded sessions - "
            "a video, the document derived from it and the evidence frames."
        )
        content = f"""<div class="card">
{html.escape(intro)}
</div>
<h2>Reviewing</h2>
<div class="card">
A review is addressed by its own url. If you were invited to review, follow the
link you received by mail - it opens the reels of your review. There is no
account and no password, and the link keeps working when reels are added.
</div>
<h2>Browsing</h2>
<div class="card">
The reels this site makes public are listed under <a href="/reels">reels</a>.
</div>
{self.demo_card()}
<h2>Reel Driven Development</h2>
<div class="card">
The reels are produced with
<a href="{html.escape(self.config.cm_url)}" target=_blank>reel-driven-development</a>,
free software under Apache-2.0, so any organization can run a site like this one.
</div>
"""
        page = self.page("home", content)
        return page

    def reels(self, review: Optional[Review] = None) -> str:
        """The reels directory as the holder of the given right sees it.

        Anyone sees the public and demo reels; a Review right adds its
        private reels under the same directory.

        Args:
            review: the review right; None for the anonymous directory.

        Returns:
            the reels directory page.
        """
        granted = review.reels if review else None
        visible_reels = self.reels_found.visible(granted)
        heading = "Reels"
        if review:
            heading = f"Reels - review by {review.person}"
        if visible_reels:
            rows = "\n".join(
                f'<tr><td><a href="{html.escape(self.reel_url(reel, review))}">'
                f"{html.escape(reel.acronym)}</a></td>"
                f"<td>{html.escape(reel.title)}</td>"
                f"<td>{reel.hop_count}</td>"
                f"<td>{html.escape(reel.status)}</td></tr>"
                for reel in visible_reels
            )
            content = (
                f'<h2>{html.escape(heading)}</h2>\n<div class="card">\n<table>\n'
                f"<tr><th>reel</th><th>title</th><th>hops</th><th>status</th></tr>\n"
                f"{rows}\n</table>\n</div>"
            )
        else:
            content = (
                f'<h2>{html.escape(heading)}</h2>\n<div class="card">\n'
                "This site makes no reel public yet.\n</div>"
            )
        page = self.page("reels", content)
        return page

    def installation(self, reviews_file: str) -> str:
        """The installation mode page - the state a visitor sees while the
        site is not initialized.

        Per the Owner bootstrap decision a site without reviews.yaml
        refuses to serve reels and names the init command instead; the
        state is shown, never hidden behind a dead backend.

        Args:
            reviews_file: the reviews file whose absence is the state.

        Returns:
            the installation mode page.
        """
        content = f"""<h2>Installation mode</h2>
<div class="card">
This reel site is not initialized: <code>{html.escape(reviews_file)}</code>
does not exist, so no review right exists yet - not even the owner's.
No reel is served in this state.
</div>
<div class="card">
The owner initializes the site on its host - access administration needs
ssh and nothing else:
<pre>reelsite --init</pre>
The command asks for username, full name, email and url, seeds the owner
and mints the wildcard owner token. The token is shown once on the
terminal and written beside the site configuration with mode 600; it is
never mailed, never logged and never minted via this webservice.
</div>
"""
        page = self.page("installation mode", content)
        return page

    def about(self) -> str:
        """The about page - version, license and repository."""
        version = self.version
        content = f"""<h2>About</h2>
<div class="card">
<table>
<tr><th>site</th><td>{html.escape(self.config.title)}</td></tr>
<tr><th>software</th><td>{html.escape(version.name)}</td></tr>
<tr><th>version</th><td>{html.escape(version.version)}</td></tr>
<tr><th>updated</th><td>{html.escape(version.updated)}</td></tr>
<tr><th>license</th><td>Apache-2.0</td></tr>
<tr><th>source</th><td><a href="{html.escape(self.config.cm_url)}" target=_blank>{html.escape(self.config.cm_url)}</a></td></tr>
<tr><th>documentation</th><td><a href="{html.escape(self.config.doc_url)}" target=_blank>{html.escape(self.config.doc_url)}</a></td></tr>
</table>
</div>
"""
        page = self.page("about", content)
        return page


class ReelSiteHandler(http.server.BaseHTTPRequestHandler):
    """Serve the pages of a reel site.

    Reel files are not served here - per the Delivery decision the web server
    in front does that.
    """

    site: Optional[ReelSite] = None

    def do_GET(self):
        """Answer a page request."""
        pages = {
            "/": self.site.home,
            "/index.html": self.site.home,
            "/reels": self.site.reels,
            "/reels/": self.site.reels,
            "/about": self.site.about,
        }
        page_of = pages.get(self.path)
        if page_of is not None:
            self.respond(page_of().encode())
            return
        if self.path.startswith("/reels/"):
            self.handle_reel(self.path[len("/reels/") :])
            return
        self.send_error(404)

    def handle_reel(self, rest: str):
        """Answer a request below /reels/ per the Delivery decision.

        The url is /reels/<acronym>/<file>, optionally carrying the
        review token first - /reels/<token>/<acronym>/<file> - and per
        the Hop url decision optionally the lengthy address
        /reels/<year>/<month>/<acronym>/; a hop slug below the reel
        answers the review positioned at that hop. A bare
        token shows the reels directory of its Review. Below the reel,
        review answers the packaged review page - reelreview.html
        alike, so a stale copy in a reel folder is shadowed - and
        api/files, api/info and api/reel answer the page's read api. Unknown
        tokens, unknown acronyms and denied reels answer alike,
        tarpitted, so neither tokens nor private acronyms can be
        probed.

        Args:
            rest: the path after /reels/.
        """
        parts = [urllib.parse.unquote(part) for part in rest.split("/")]
        review = self.site.reviews.by_token().get(parts[0])
        if review is not None:
            parts = parts[1:]
            if not parts or parts == [""]:
                self.respond(self.site.reels(review).encode())
                return
        reel, file_parts = self.resolve_reel(parts)
        if reel is None or not self.site.allowed(reel, review):
            time.sleep(0.5)
            self.send_error(404)
            return
        if not file_parts:
            if not self.path.endswith("/"):
                # the reel page needs its trailing slash so its relative
                # review and file links resolve below the reel
                self.send_response(301)
                self.send_header("Location", self.path + "/")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            self.respond(self.site.reel_page(reel).encode())
            return
        if file_parts in (["review"], ["reelreview.html"]):
            self.respond(self.site.review_page().encode())
            return
        if len(file_parts) == 1 and file_parts[0] in reel.hop_slugs():
            self.respond(self.site.review_page().encode())
            return
        if file_parts == ["api", "files"]:
            self.respond_json(self.site.reel_files(reel))
            return
        if file_parts == ["api", "info"]:
            self.respond_json({"folder": reel.folder, "acronym": reel.acronym})
            return
        if file_parts == ["api", "reel"]:
            # the hop set parsed by the model - the page never parses YAML
            self.respond_json(reel.hop_set.to_dict() if reel.hop_set else {})
            return
        file_path = os.path.realpath(os.path.join(reel.path, *file_parts))
        reel_dir = os.path.realpath(reel.path)
        if not file_path.startswith(reel_dir + os.sep) or not os.path.isfile(file_path):
            self.send_error(404)
            return
        self.send_file(file_path)

    def resolve_reel(self, parts: List[str]):
        """Resolve the addressed reel - shortcut or lengthy form.

        Per the Hop url decision the acronym is the shortcut address
        and year/month/acronym the lengthy form disambiguating
        non-unique acronyms.

        Args:
            parts: the path parts after /reels/ with the token stripped.

        Returns:
            the reel or None, and the remaining path parts.
        """
        reel = None
        file_parts: List[str] = []
        if (
            len(parts) >= 3
            and re.match(r"\d{4}$", parts[0])
            and re.match(r"\d{2}$", parts[1])
        ):
            reel = self.site.reels_found.by_pid().get("/".join(parts[:3]))
            file_parts = [part for part in parts[3:] if part]
        elif parts:
            reel = self.site.reels_found.by_acronym().get(parts[0])
            file_parts = [part for part in parts[1:] if part]
        return reel, file_parts

    def send_file(self, file_path: str):
        """Send the given file, answering range requests so seeking works.

        Args:
            file_path: the file to send.
        """
        file_size = os.path.getsize(file_path)
        content_type = mimetypes.guess_type(file_path)[0] or "application/octet-stream"
        start = 0
        end = file_size - 1
        status = 200
        range_match = re.match(r"bytes=(\d*)-(\d*)$", self.headers.get("Range") or "")
        if range_match and (range_match.group(1) or range_match.group(2)):
            if range_match.group(1):
                start = int(range_match.group(1))
                if range_match.group(2):
                    end = min(int(range_match.group(2)), file_size - 1)
            else:
                start = max(file_size - int(range_match.group(2)), 0)
            if start >= file_size or start > end:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{file_size}")
                self.end_headers()
                return
            status = 206
        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Accept-Ranges", "bytes")
        if status == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()
        with open(file_path, "rb") as reel_file:
            reel_file.seek(start)
            remaining = length
            while remaining > 0:
                chunk = reel_file.read(min(65536, remaining))
                if not chunk:
                    break
                self.wfile.write(chunk)
                remaining -= len(chunk)

    def do_POST(self):
        """Answer the write api of the review page - true inspection mode.

        Per the Reel Review decision a save on this site answers
        success and stores nothing on the server; server side storage
        for token holders is the matter of the quick check issue. The
        request must name an allowed reel, so the write api reveals no
        more than the read api does.
        """
        match = re.match(
            r"/reels/(.+)/api/(save|feedback|upload)$",
            urllib.parse.unquote(self.path),
        )
        parts = match.group(1).split("/") if match else []
        review = self.site.reviews.by_token().get(parts[0]) if parts else None
        if review is not None:
            parts = parts[1:]
        directory = self.site.reels_found.by_acronym()
        reel = directory.get(parts[0]) if len(parts) == 1 else None
        if reel is None or not self.site.allowed(reel, review):
            time.sleep(0.5)
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", 0))
        self.rfile.read(length)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def respond_json(self, data) -> None:
        """Send the given data as a json response.

        Args:
            data: the payload to serialize.
        """
        body = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def respond(self, body: bytes):
        """Send the given page body as a successful response.

        Args:
            body: the encoded html page.
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        # pages are dynamic - a browser must revalidate, never show a stale copy
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args):
        """Log to stdout so the service log carries the requests."""
        print(f"{self.address_string()} {format % args}", flush=True)


class InstallationHandler(http.server.BaseHTTPRequestHandler):
    """Serve the installation mode state.

    Per the Owner bootstrap decision a site without reviews.yaml refuses
    to serve reels and names the init command instead - the site is up
    and shows what needs to be done; it never serves a reel and never
    mints.
    """

    page: bytes = b""

    def do_GET(self):
        """Answer any request with the installation state."""
        self.respond()

    def do_POST(self):
        """Answer any write attempt with the installation state."""
        self.respond()

    def respond(self):
        """Send the installation page as service unavailable."""
        self.send_response(503)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Content-Length", str(len(self.page)))
        self.end_headers()
        self.wfile.write(self.page)

    def log_message(self, format: str, *args):
        """Log to stdout so the service log carries the requests."""
        print(f"{self.address_string()} {format % args}", flush=True)


def serve(
    config: RddSiteConfig,
    host: str = "127.0.0.1",
    reviews_path: Optional[str] = None,
) -> None:
    """Serve the site of the given configuration.

    Per the Owner bootstrap decision a site without reviews.yaml is in
    installation mode: it stays up, refuses to serve reels and names the
    init command on every request, so the state is never hidden behind a
    dead backend.

    Args:
        config: the site configuration.
        host: the interface to listen on; localhost by default - the web
            server in front is what the internet talks to.
        reviews_path: the reviews file; the default path when None.
    """
    reviews_file = os.path.expanduser(reviews_path or Reviews.DEFAULT_PATH)
    if not os.path.isfile(reviews_file):
        install_site = ReelSite(config, reels=Reels(), reviews=Reviews())
        page = install_site.installation(reviews_file).encode()
        handler = type(
            "BoundInstallationHandler", (InstallationHandler,), {"page": page}
        )
        print(
            f"rdd_site: installation mode - no {reviews_file}; " "run reelsite --init",
            flush=True,
        )
        with http.server.ThreadingHTTPServer((host, config.port), handler) as httpd:
            print(
                f"rdd_site: {config.title} on http://{host}:{config.port}/ "
                "(installation mode)",
                flush=True,
            )
            httpd.serve_forever()
        return
    site = ReelSite(config, reviews=Reviews.of_path(reviews_file))
    main_demo = site.check_main_demo()
    print(f"rdd_site: {site.reels_found.as_summary()}", flush=True)
    print(f"rdd_site: main_demo {main_demo.acronym}", flush=True)
    handler = type("BoundReelSiteHandler", (ReelSiteHandler,), {"site": site})
    with http.server.ThreadingHTTPServer((host, config.port), handler) as httpd:
        print(f"rdd_site: {config.title} on http://{host}:{config.port}/", flush=True)
        httpd.serve_forever()
