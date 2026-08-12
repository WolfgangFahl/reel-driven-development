"""
Reel Driven Development - reelreview server
https://github.com/WolfgangFahl/reel-driven-development

Serves a recording folder for the reelreview.html human-in-the-loop verdict
pass and accepts the curated reel.yaml back:

    GET  /            -> reelreview.html
    GET  /<file>      -> static file from the recording folder
    GET  /api/files   -> JSON list of the folder's file names
    GET  /api/info    -> JSON folder name and acronym of the reviewed reel
    POST /api/save     -> body replaces reel.yaml (RCS checkpoint first)
    POST /api/feedback -> body replaces reel-feedback.yaml (RCS checkpoint first)
    POST /api/upload   -> forward reel-feedback.yaml body to the feedback_url
                          configured in reel.yaml's config block

Python stdlib only - no dependencies to install.

Usage:
    reelreview [folder] [--port PORT]
"""

import http.server
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

DEFAULT_PORT = 8123
DEFAULT_HOST = "127.0.0.1"


class ReelReviewHandler(http.server.SimpleHTTPRequestHandler):
    """Serve one recording folder for the review pass.

    The whole folder is readable and reel.yaml and reel-feedback.yaml are
    writable through the api, with no authentication of any kind - this is a
    single user tool for the person curating a reel on their own machine. It
    is bound to localhost for that reason; a --host that opens it to a network
    hands that write access to everyone who can reach the port.
    """

    def do_GET(self):
        """Answer a file or api request.

        / and /index.html serve the review page, /api/info the folder
        name and acronym of the reviewed reel, /api/files the file names
        of the folder; anything else is a static file of the folder.
        """
        if self.path in ("/", "/index.html"):
            self.path = "/reelreview.html"
        if self.path == "/api/info":
            folder = Path(self.directory)
            info = {"folder": folder.name}
            reel = folder / "reel.yaml"
            if reel.exists():
                match = re.search(
                    r"^\s+acronym:\s*(\S+)", reel.read_text(), re.MULTILINE
                )
                if match:
                    info["acronym"] = match.group(1).strip("\"'")
            body = json.dumps(info).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/files":
            names = sorted(
                p.name for p in Path(self.directory).iterdir() if p.is_file()
            )
            body = json.dumps(names).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def do_POST(self):
        """Take the curated yaml back.

        /api/save replaces reel.yaml and /api/feedback reel-
        feedback.yaml, both after an RCS checkpoint of the file being
        replaced; /api/upload forwards the body to the feedback_url of
        reel.yaml. Anything else is a 404.
        """
        targets = {"/api/save": "reel.yaml", "/api/feedback": "reel-feedback.yaml"}
        length = int(self.headers.get("Content-Length", 0))
        content = self.rfile.read(length)
        if self.path in targets:
            target = Path(self.directory) / targets[self.path]
            self.checkpoint(target)
            target.write_bytes(content)
            self.send_response(200)
            self.send_header("Content-Length", "0")
            self.end_headers()
        elif self.path == "/api/upload":
            self.upload(content)
        else:
            self.send_error(404)

    def upload(self, content: bytes):
        """Forward the feedback to the feedback_url configured in reel.yaml."""
        import re
        import urllib.request

        reel = (Path(self.directory) / "reel.yaml").read_text()
        match = re.search(r"^\s+feedback_url:\s*(\S+)", reel, re.MULTILINE)
        if not match:
            self.send_error(409, "no feedback_url in reel.yaml config")
            return
        request = urllib.request.Request(
            match.group(1), data=content, headers={"Content-Type": "text/yaml"}
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                self.send_response(response.status)
                self.send_header("Content-Length", "0")
                self.end_headers()
        except Exception as ex:
            self.send_error(502, str(ex))

    def checkpoint(self, target: Path):
        """Version the current reel.yaml with RCS before overwriting."""
        if target.exists() and shutil.which("ci"):
            subprocess.run(
                [
                    "ci",
                    "-l",
                    f"-t-{target.name}",
                    "-m",
                    "reelreview checkpoint",
                    str(target),
                ],
                cwd=self.directory,
                capture_output=True,
            )


def page_path() -> Path:
    """Path of the review page shipped with the package."""
    path = Path(__file__).parent / "resources" / "reelreview.html"
    return path


def serve(folder: Path, port: int = DEFAULT_PORT, host: str = DEFAULT_HOST) -> None:
    """Serve the given recording folder for the review pass.

    Args:
        folder: the recording folder holding reel.yaml.
        port: port to serve on.
        host: interface to listen on; localhost by default - the api writes
            reel.yaml without authentication, so binding a reachable interface
            is an explicit choice of the person starting the server.

    Raises:
        ValueError: if the folder holds no reel.yaml or the page is missing.
    """
    if not (folder / "reel.yaml").exists():
        raise ValueError(f"no reel.yaml in {folder}")
    if not (folder / "reelreview.html").exists():
        page = page_path()
        if not page.exists():
            raise ValueError(f"no reelreview.html in {folder} and none packaged")
        shutil.copy(page, folder / "reelreview.html")
    handler = lambda *a, **kw: ReelReviewHandler(*a, directory=str(folder), **kw)
    with http.server.ThreadingHTTPServer((host, port), handler) as httpd:
        print(f"reelreview: serving {folder} on http://{host}:{port}/")
        httpd.serve_forever()
