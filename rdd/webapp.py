"""Created on 2026-08-14.

the fastapi application of a reel site - the pages and the api as decided,
plus /docs and /openapi.json per the OpenAPI docs issue

Per the Delivery decision the site itself answers below /reels/; the web
server in front only proxies. Per the framed 404 issue every miss answers
the framed page. The docs are self-contained like every other page: the
swagger assets are served by the site, never by a CDN.

@author: wf
"""

import os
import time
import urllib.parse
from typing import List, Optional, Tuple

from fastapi import FastAPI, Request
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from swagger_ui_bundle import swagger_ui_path

from rdd.rdd_site import Reel, ReelSite, Review

TARPIT_SECONDS = 0.5


def page_response(page: str, status: int = 200) -> HTMLResponse:
    """The given page as an html response.

    Args:
        page: the html page.
        status: the http status; 200 by default.

    Returns:
        the response; no-cache so a browser never shows a stale page.
    """
    response = HTMLResponse(page, status_code=status)
    response.headers["Cache-Control"] = "no-cache"
    return response


class ReelApp:
    """The fastapi application of a reel site.

    One instance wires the routes of one ReelSite; the app is what
    uvicorn serves and what /docs documents.
    """

    def __init__(self, site: ReelSite):
        """Initialize with the site to serve.

        Args:
            site: the reel site.
        """
        self.site = site
        self.app = FastAPI(
            title=site.config.title,
            version=site.version.version,
            description=(
                "The api of a reel site per the Delivery and Reel Review "
                "decisions: a reel and its files are served by acronym and "
                "right. Unknown tokens, unknown acronyms and denied reels "
                "answer alike - a tarpitted framed 404 - so neither tokens "
                "nor private acronyms can be probed."
            ),
            docs_url=None,
            redoc_url=None,
        )
        self.app.mount(
            "/static/swagger",
            StaticFiles(directory=swagger_ui_path),
            name="swagger",
        )
        self.add_routes()

    def not_found(self, path: str, tarpit: bool = False) -> HTMLResponse:
        """The framed 404 response.

        Args:
            path: the path that has no page.
            tarpit: delay the answer so tokens and private acronyms
                cannot be probed.

        Returns:
            the framed 404 page as a response.
        """
        if tarpit:
            time.sleep(TARPIT_SECONDS)
        response = page_response(self.site.not_found(path), status=404)
        return response

    def address_parts(
        self, address: str
    ) -> Tuple[Optional[Review], Optional[Reel], List[str]]:
        """Resolve an address below /reels/ into right, reel and rest.

        Args:
            address: the path after /reels/, optionally token first.

        Returns:
            the review right or None, the reel or None, and the
            remaining path parts.
        """
        parts = [urllib.parse.unquote(part) for part in address.split("/")]
        review = self.site.reviews.by_token().get(parts[0])
        if review is not None:
            parts = parts[1:]
        reel, file_parts = self.site.resolve_reel(parts)
        return review, reel, file_parts

    def checked_reel(
        self, address: str
    ) -> Tuple[Optional[Reel], Optional[Review], List[str]]:
        """The reel of the given address where the right allows it.

        Args:
            address: the path after /reels/, optionally token first.

        Returns:
            reel, review and remaining parts; reel is None where the
            address resolves to nothing the right allows.
        """
        review, reel, file_parts = self.address_parts(address)
        if reel is not None and not self.site.allowed(reel, review):
            reel = None
        return reel, review, file_parts

    def add_routes(self) -> None:
        """Wire the routes of the site."""
        app = self.app
        site = self.site

        @app.get("/", response_class=HTMLResponse, summary="the home page")
        @app.get("/index.html", response_class=HTMLResponse, include_in_schema=False)
        def home() -> HTMLResponse:
            """The home page - what this site is and the ways in."""
            return page_response(site.home())

        @app.get("/reels", response_class=HTMLResponse, summary="the reels directory")
        def reels() -> HTMLResponse:
            """The public reels directory."""
            return page_response(site.reels())

        @app.get("/about", response_class=HTMLResponse, summary="the about page")
        def about() -> HTMLResponse:
            """The about page - version, license and repository."""
            return page_response(site.about())

        @app.get("/docs", include_in_schema=False)
        def docs() -> HTMLResponse:
            """The api documentation - swagger assets served by the site."""
            return get_swagger_ui_html(
                openapi_url="/openapi.json",
                title=f"{site.config.title} - api",
                swagger_js_url="/static/swagger/swagger-ui-bundle.js",
                swagger_css_url="/static/swagger/swagger-ui.css",
                swagger_favicon_url="/static/swagger/favicon-32x32.png",
            )

        @app.get(
            "/reels/{address:path}/api/files",
            summary="the files of a reel",
        )
        def api_files(address: str, request: Request):
            """The sorted file names of the reel - the review page's read api."""
            reel, _review, file_parts = self.checked_reel(address)
            if reel is None or file_parts:
                return self.not_found(request.url.path, tarpit=True)
            return JSONResponse(site.reel_files(reel))

        @app.get(
            "/reels/{address:path}/api/info",
            summary="folder and acronym of a reel",
        )
        def api_info(address: str, request: Request):
            """Folder and acronym of the reel."""
            reel, _review, file_parts = self.checked_reel(address)
            if reel is None or file_parts:
                return self.not_found(request.url.path, tarpit=True)
            return JSONResponse({"folder": reel.folder, "acronym": reel.acronym})

        @app.get(
            "/reels/{address:path}/api/reel",
            summary="the hop set of a reel",
        )
        def api_reel(address: str, request: Request):
            """The hop set parsed by the model - the page never parses YAML."""
            reel, _review, file_parts = self.checked_reel(address)
            if reel is None or file_parts:
                return self.not_found(request.url.path, tarpit=True)
            return JSONResponse(reel.hop_set.to_dict() if reel.hop_set else {})

        @app.post(
            "/reels/{address:path}/api/{action}",
            summary="the write api - true inspection mode",
        )
        async def api_write(address: str, action: str, request: Request):
            """Per the Reel Review decision a save on this site answers success
            and stores nothing; the request must name an allowed reel, so the
            write api reveals no more than the read api."""
            reel, _review, file_parts = self.checked_reel(address)
            if (
                reel is None
                or file_parts
                or action not in ("save", "feedback", "upload")
            ):
                return self.not_found(request.url.path, tarpit=True)
            await request.body()
            return JSONResponse({})

        @app.get(
            "/reels/{rest:path}",
            response_class=HTMLResponse,
            summary="a reel, its review or one of its files",
        )
        def reel_route(rest: str, request: Request):
            """Delivery per the Delivery and Hop url decisions.

            The url is /reels/[token/][yyyy/mm/]acronym/[file|review|hop-slug].
            A bare token answers the reels directory of its review.
            """
            path = request.url.path
            parts = [urllib.parse.unquote(part) for part in rest.split("/")]
            review = site.reviews.by_token().get(parts[0])
            if review is not None:
                parts = parts[1:]
                if not parts or parts == [""]:
                    return page_response(site.reels(review))
            elif not rest or rest == "":
                return page_response(site.reels())
            reel, file_parts = site.resolve_reel(parts)
            if reel is None or not site.allowed(reel, review):
                return self.not_found(path, tarpit=True)
            if not file_parts:
                if not path.endswith("/"):
                    # the reel page needs its trailing slash so its relative
                    # review and file links resolve below the reel
                    return RedirectResponse(path + "/", status_code=301)
                return page_response(site.reel_page(reel))
            if file_parts in (["review"], ["reelreview.html"]):
                return page_response(site.review_page())
            if len(file_parts) == 1 and file_parts[0] in reel.hop_slugs():
                return page_response(site.review_page())
            file_path = os.path.realpath(os.path.join(reel.path, *file_parts))
            reel_dir = os.path.realpath(reel.path)
            if not file_path.startswith(reel_dir + os.sep) or not os.path.isfile(
                file_path
            ):
                return self.not_found(path)
            return FileResponse(file_path)

        @app.exception_handler(404)
        async def framed_404(request: Request, _exception) -> HTMLResponse:
            """Any miss answers the framed 404 page."""
            return page_response(site.not_found(request.url.path), status=404)


class InstallationApp:
    """The installation mode application.

    Per the Owner bootstrap decision a site without reviews.yaml refuses
    to serve reels and names the init command on every request - the
    state is shown, never hidden behind a dead backend.
    """

    def __init__(self, page: str):
        """Initialize with the installation page.

        Args:
            page: the installation mode page.
        """
        self.page = page
        self.app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        self.add_routes()

    def add_routes(self) -> None:
        """Every request answers the installation state."""
        app = self.app
        page = self.page

        @app.api_route("/{rest:path}", methods=["GET", "POST"], include_in_schema=False)
        def installation(rest: str) -> HTMLResponse:
            """The installation mode state as service unavailable."""
            return page_response(page, status=503)


def create_app(site: ReelSite) -> FastAPI:
    """Create the fastapi application of the given site.

    Args:
        site: the reel site.

    Returns:
        the application.
    """
    app = ReelApp(site).app
    return app


def create_installation_app(page: str) -> FastAPI:
    """Create the installation mode application.

    Args:
        page: the installation mode page.

    Returns:
        the application.
    """
    app = InstallationApp(page).app
    return app
