"""Created on 2026-08-12.

the site of an organization's reels - home page, menu and about

see https://media.bitplan.com/index.php/Talk:Rdd.bitplan.com
ADRs: Review UI stack, Home page and menu

@author: wf
"""

import html
import http.server
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from basemkit.yamlable import lod_storable

from rdd.icons import svg
from rdd.palette import Palette, Palettes
from rdd.version import Version


@lod_storable
class PublicReel:
    """A reel this site offers to any visitor."""

    acronym: str = ""
    title: str = ""
    url: str = ""


@lod_storable
class SiteConfig:
    """Everything an organization configures to run its own reel site.

    One yaml is the whole configuration - the site names itself, its
    repository, its documentation and the palette it wears, so a stranger's
    site names their project and not ours.
    """

    name: str = "reels"
    title: str = "Reels"
    intro: str = ""
    palette: str = "default"
    copy_right: str = ""
    cm_url: str = Version.cm_url
    doc_url: str = Version.doc_url
    port: int = 9925
    reels: List[PublicReel] = field(default_factory=list)

    @classmethod
    def of_file(cls, path: str) -> "SiteConfig":
        """Load the site configuration from the given yaml file."""
        config = cls.load_from_yaml_file(path)
        return config


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

    def __init__(self, config: SiteConfig, version: Optional[Version] = None):
        """Initialize with the site configuration.

        Args:
            config: the configuration of this site.
            version: version info of the software; defaults to the package version.
        """
        self.config = config
        self.version = version or Version()
        self.palette: Palette = Palettes.of_resource().by_name(config.palette)

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
<h2>Reel Driven Development</h2>
<div class="card">
The reels are produced with
<a href="{html.escape(self.config.cm_url)}" target=_blank>reel-driven-development</a>,
free software under Apache-2.0, so any organization can run a site like this one.
</div>
"""
        page = self.page("home", content)
        return page

    def reels(self) -> str:
        """The list of reels this site makes public."""
        if self.config.reels:
            rows = "\n".join(
                f'<tr><td><a href="{html.escape(reel.url)}">'
                f"{html.escape(reel.acronym)}</a></td>"
                f"<td>{html.escape(reel.title)}</td></tr>"
                for reel in self.config.reels
            )
            content = (
                f'<h2>Reels</h2>\n<div class="card">\n<table>\n{rows}\n</table>\n</div>'
            )
        else:
            content = (
                '<h2>Reels</h2>\n<div class="card">\n'
                "This site makes no reel public yet.\n</div>"
            )
        page = self.page("reels", content)
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
            "/about": self.site.about,
        }
        page_of = pages.get(self.path)
        if page_of is None:
            self.send_error(404)
            return
        body = page_of().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args):
        """Log to stdout so the service log carries the requests."""
        print(f"{self.address_string()} {format % args}", flush=True)


def serve(config: SiteConfig, host: str = "127.0.0.1") -> None:
    """Serve the site of the given configuration.

    Args:
        config: the site configuration.
        host: the interface to listen on; localhost by default - the web
            server in front is what the internet talks to.
    """
    site = ReelSite(config)
    handler = type("BoundReelSiteHandler", (ReelSiteHandler,), {"site": site})
    with http.server.ThreadingHTTPServer((host, config.port), handler) as httpd:
        print(f"reelsite: {config.title} on http://{host}:{config.port}/", flush=True)
        httpd.serve_forever()
