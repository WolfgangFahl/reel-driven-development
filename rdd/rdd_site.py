"""Created on 2026-08-12.

the site of an organization's reel driven development videos - home page, menu and about

see https://media.bitplan.com/index.php/Talk:Rdd.bitplan.com
ADRs: Review UI stack, Home page and menu

@author: wf
"""

import html
import os
import re
import sys
import tempfile
import urllib.parse
import zipfile
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from basemkit.yamlable import lod_storable

from rdd.i18n import FLAGS, LANGUAGES, texts
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
            reel = self.reels_found.by_pid().get("/".join(parts[:3]))
            file_parts = [part for part in parts[3:] if part]
        elif parts:
            reel = self.reels_found.by_acronym().get(parts[0])
            file_parts = [part for part in parts[1:] if part]
        return reel, file_parts

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

    def reel_page(self, reel: Reel, lang: str = "en") -> str:
        """The page of one reel - what it is and the files it carries.

        The review and file links are relative so a review link keeps
        its token.

        Args:
            reel: the reel.
            lang: the language of the page.

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
        t = texts(lang)
        content = (
            f"<h2>{html.escape(reel.title)}</h2>\n"
            f'<p><a href="review">{t["review"]}</a></p>\n'
            f'<div class="card">\n<b>{t["summary"]}</b><br>\n'
            f"{html.escape(summary)}\n</div>\n"
            f'<div class="card">\n<table>\n'
            f'<tr><th>{t["file"]}</th><th>{t["bytes"]}</th></tr>\n'
            f"{rows}\n</table>\n</div>"
        )
        page = self.page(reel.acronym, content, lang)
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

    def reel_zip(self, reel: Reel) -> str:
        """Zip the folder of the given reel into a temporary file.

        Per the Reel verdict decision the verdict page offers the reel
        folder as one download; videos do not compress, so the entries
        are stored.

        Args:
            reel: the reel.

        Returns:
            the path of the temporary zip file - the caller removes it
            after delivery.
        """
        handle, zip_path = tempfile.mkstemp(suffix=".zip", prefix=f"{reel.acronym}-")
        os.close(handle)
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_STORED) as zip_file:
            for root, _dirs, files in os.walk(reel.path):
                for file_name in sorted(files):
                    file_path = os.path.join(root, file_name)
                    arcname = os.path.join(
                        reel.acronym, os.path.relpath(file_path, reel.path)
                    )
                    zip_file.write(file_path, arcname)
        return zip_path

    def menu(self, lang: str = "en") -> List[MenuEntry]:
        """The menu entries - settings and chat are dropped, a visitor has
        neither.

        Args:
            lang: the language of the entry names.
        """
        t = texts(lang)
        entries = [
            MenuEntry(t["home"], "/", "home"),
            MenuEntry(t["reels"], "/reels", "movie"),
            MenuEntry(t["github"], self.config.cm_url, "bug_report", new_tab=True),
            MenuEntry(t["help"], self.config.doc_url, "help", new_tab=True),
            MenuEntry(t["about"], "/about", "info"),
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
header {{ display: flex; gap: .8em; align-items: center; padding: .6em .8em; background: var(--primary); color: #fff; flex-wrap: wrap; }}
header h1 {{ font-size: 1.1em; margin: 0 .4em 0 0; }}
header a {{ display: inline-flex; align-items: center; gap: .5em; color: #fff; text-decoration: none; background: var(--primary); border-radius: 4px; padding: .5em 1em; font-size: .85em; font-weight: 500; text-transform: uppercase; letter-spacing: .05em; box-shadow: 0 1px 5px rgba(0,0,0,.2), 0 2px 2px rgba(0,0,0,.14), 0 3px 1px -2px rgba(0,0,0,.12); }}
header a:hover {{ background: var(--accent); }}
header a.flag {{ box-shadow: none; text-transform: none; background: none; font-size: 1.1em; padding: .2em; margin-left: auto; }}
.hamburger {{ display: inline-flex; align-items: center; background: var(--primary); border: none; color: #fff; cursor: pointer; border-radius: 4px; padding: .45em .6em; box-shadow: 0 1px 5px rgba(0,0,0,.2), 0 2px 2px rgba(0,0,0,.14), 0 3px 1px -2px rgba(0,0,0,.12); }}
.hamburger.collapsed {{ position: fixed; top: .4em; left: .4em; z-index: 10; }}
.hamburger[hidden] {{ display: none; }}
body.collapsed header, body.collapsed footer {{ display: none; }}
main {{ padding: 1em; max-width: 55em; }}
main h2 {{ font-size: 1.2em; }}
main a {{ color: var(--primary); }}
.card {{ background: var(--card); border: 1px solid var(--border); border-radius: 6px; padding: .8em; margin-bottom: .8em; }}
footer {{ padding: .6em .8em; background: var(--primary); color: #fff; font-size: .85em; }}
footer a {{ color: #fff; }}
table {{ border-collapse: collapse; }}
td, th {{ text-align: left; padding: .2em .8em .2em 0; }}
"""
        return css

    def flag_selector(self, lang: str) -> str:
        """The language selector with flag - the other languages as links.

        Args:
            lang: the language of the current page.

        Returns:
            the selector markup.
        """
        flags = " ".join(
            f'<a class="flag" href="?lang={other}" title="{other}">{FLAGS[other]}</a>'
            for other in LANGUAGES
            if other != lang
        )
        return flags

    def page(self, title: str, content: str, lang: str = "en") -> str:
        """Render a page with menu and footer.

        Args:
            title: title of the page.
            content: the html of the page body.
            lang: the language of the page.

        Returns:
            the complete html page.
        """
        links = "\n".join(entry.as_html() for entry in self.menu(lang))
        site_title = html.escape(self.config.title)
        menu_icon = svg("menu")
        page = f"""<!DOCTYPE html>
<html lang="{lang}">
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
  {self.flag_selector(lang)}
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

    def demo_card(self, lang: str = "en") -> str:
        """The demo section of the home page - the main_demo of this site.

        Args:
            lang: the language of the card.

        Returns:
            the demo card markup; empty where the main_demo does not
            resolve, so a misconfigured site still serves its home page.
        """
        t = texts(lang)
        card = ""
        directory = self.reels_found.by_acronym()
        main_demo = directory.get(self.config.main_demo)
        if main_demo and main_demo.is_demo:
            url = self.reel_url(main_demo)
            card = (
                f'<h2>{t["demo"]}</h2>\n<div class="card">\n'
                f'{t["demo_text"]}: <a href="{html.escape(url)}">'
                f"{html.escape(main_demo.title)}</a> "
                f'({main_demo.hop_count} {t["hops"]}) - {t["demo_hint"]}\n</div>'
            )
        return card

    def home(self, lang: str = "en") -> str:
        """The home page - what this site is and the two ways in.

        Args:
            lang: the language of the page.
        """
        t = texts(lang)
        intro = html.escape(self.config.intro) if self.config.intro else t["intro"]
        content = f"""<div class="card">
{intro}
</div>
<h2>{t["reviewing"]}</h2>
<div class="card">
{t["reviewing_text"]}
</div>
<h2>{t["browsing"]}</h2>
<div class="card">
{t["browsing_text"]}
</div>
{self.demo_card(lang)}
<h2>Reel Driven Development</h2>
<div class="card">
{t["rdd_text"]}
<a href="{html.escape(self.config.cm_url)}" target=_blank>reel-driven-development</a>,
{t["rdd_text2"]}
</div>
"""
        page = self.page(t["home"], content, lang)
        return page

    def reels(self, review: Optional[Review] = None, lang: str = "en") -> str:
        """The reels directory as the holder of the given right sees it.

        Anyone sees the public and demo reels; a Review right adds its
        private reels under the same directory.

        Args:
            review: the review right; None for the anonymous directory.
            lang: the language of the page.

        Returns:
            the reels directory page.
        """
        t = texts(lang)
        granted = review.reels if review else None
        visible_reels = self.reels_found.visible(granted)
        heading = "Reels"
        if review:
            heading = t["review_by"].format(person=review.person)
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
                f'<tr><th>{t["reel"]}</th><th>{t["title"]}</th>'
                f'<th>{t["hops"]}</th><th>{t["status"]}</th></tr>\n'
                f"{rows}\n</table>\n</div>"
            )
        else:
            content = (
                f'<h2>{html.escape(heading)}</h2>\n<div class="card">\n'
                f'{t["no_reels"]}\n</div>'
            )
        page = self.page(t["reels"], content, lang)
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
<pre>{html.escape(init_command())}</pre>
The command asks for username, full name, email and url, seeds the owner
and mints the wildcard owner token. The token is shown once on the
terminal and written beside the site configuration with mode 600; it is
never mailed, never logged and never minted via this webservice.
</div>
"""
        page = self.page("installation mode", content)
        return page

    def not_found(self, path: str, lang: str = "en") -> str:
        """The framed 404 page - it shows like any other page, with an
        example of a valid address.

        Args:
            path: the path that has no page.
            lang: the language of the page.

        Returns:
            the framed 404 page.
        """
        t = texts(lang)
        example = "/reels"
        directory = self.reels_found.by_acronym()
        main_demo = directory.get(self.config.main_demo)
        if main_demo and main_demo.is_demo:
            example = self.reel_url(main_demo)
        content = (
            f'<h2>404 - {t["not_found"]}</h2>\n'
            f'<div class="card">\n{t["no_page"]} '
            f"<code>{html.escape(path)}</code>.\n</div>\n"
            f'<div class="card">\n{t["example"]}: '
            f'<a href="{html.escape(example)}">{html.escape(example)}</a>; '
            f'{t["reels_listed"]}'
            "\n</div>"
        )
        page = self.page(t["not_found"], content, lang)
        return page

    def about(self, lang: str = "en") -> str:
        """The about page - version, license and repository.

        Args:
            lang: the language of the page.
        """
        t = texts(lang)
        version = self.version
        content = f"""<h2>{t["about_heading"]}</h2>
<div class="card">
<table>
<tr><th>{t["site"]}</th><td>{html.escape(self.config.title)}</td></tr>
<tr><th>{t["software"]}</th><td>{html.escape(version.name)}</td></tr>
<tr><th>{t["version"]}</th><td>{html.escape(version.version)}</td></tr>
<tr><th>{t["updated"]}</th><td>{html.escape(version.updated)}</td></tr>
<tr><th>{t["license"]}</th><td>Apache-2.0</td></tr>
<tr><th>{t["source"]}</th><td><a href="{html.escape(self.config.cm_url)}" target=_blank>{html.escape(self.config.cm_url)}</a></td></tr>
<tr><th>{t["documentation"]}</th><td><a href="{html.escape(self.config.doc_url)}" target=_blank>{html.escape(self.config.doc_url)}</a></td></tr>
</table>
</div>
"""
        page = self.page(t["about"], content, lang)
        return page


def init_command() -> str:
    """The init command as this installation runs it.

    A user cannot be expected to know a command name, and the venv of a
    service is not on anybody's PATH - so the command is named with the
    absolute path of the running installation where the rdd dispatcher
    lies beside the interpreter, and by its bare name otherwise.

    Returns:
        the command that initializes this site.
    """
    rdd_command = os.path.join(os.path.dirname(sys.executable), "rdd")
    if not os.path.isfile(rdd_command):
        rdd_command = "rdd"
    command = f"{rdd_command} site --init"
    return command


def serve(
    config: RddSiteConfig,
    host: str = "127.0.0.1",
    reviews_path: Optional[str] = None,
) -> None:
    """Serve the site of the given configuration with uvicorn.

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
    import uvicorn

    from rdd.webapp import create_app, create_installation_app

    reviews_file = os.path.expanduser(reviews_path or Reviews.DEFAULT_PATH)
    if not os.path.isfile(reviews_file):
        install_site = ReelSite(config, reels=Reels(), reviews=Reviews())
        page = install_site.installation(reviews_file)
        print(
            f"rdd_site: installation mode - no {reviews_file}; run {init_command()}",
            flush=True,
        )
        print(
            f"rdd_site: {config.title} on http://{host}:{config.port}/ "
            "(installation mode)",
            flush=True,
        )
        uvicorn.run(create_installation_app(page), host=host, port=config.port)
        return
    site = ReelSite(config, reviews=Reviews.of_path(reviews_file))
    main_demo = site.check_main_demo()
    print(f"rdd_site: {site.reels_found.as_summary()}", flush=True)
    print(f"rdd_site: main_demo {main_demo.acronym}", flush=True)
    print(f"rdd_site: {config.title} on http://{host}:{config.port}/", flush=True)
    uvicorn.run(create_app(site), host=host, port=config.port)
