"""The HTTP shell: routes in, JSON out, errors as sentences.

Every route is one of the page's backend verbs, dispatched to the workflow's
Python half that does the work. The server also hands out the built page, so
the microscope computer runs one program on one address. It knows no
workflow and no instrument: each workflow's half registers its own routes.

Standard library only, on purpose. The microscope computer has no network
to install packages from, and this server is a handful of routes: a
framework would save thirty lines and cost a dependency forever.

The routes are a table, ``ROUTES``, from ``(method, path)`` to the function
that answers it. A workflow's Python half puts its routes there through
:func:`add_route`, under ``/api/<its folder>/``. A handler takes
``(asked, query)`` -- the request's JSON body as a dictionary (empty for a
GET) and the raw query string -- and answers the dictionary the page
receives, or bytes (:class:`api.Bytes`); an exception it raises becomes the
sentence the page shows, with the status :meth:`Bridge._fail` gives it.

Author: Thom de Hoog, Center for Microscopy and Image Analysis (ZMB),
University of Zurich (thom.dehoog@zmb.uzh.ch, thomdehoog@gmail.com).
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import workflows
from .api import Bytes, Refusal

#: Where the page is that ``npm run build`` built from the folder of workflows:
#: its ``built-page/`` (``examples/built-page`` in a checkout of this
#: repository). None when there is no folder of workflows to run.
THE_PAGE: Path | None = workflows.WORKFLOWS / workflows.BUILT_PAGE if workflows.WORKFLOWS else None

#: The routes, by method and path: what answers ``GET /api/instruments`` is
#: ``ROUTES[("GET", "/api/instruments")]``.
ROUTES: dict[tuple[str, str], object] = {}

#: The routes that answer every path beginning with theirs, by method and
#: that beginning; their handler is handed the rest of the path too.
PREFIX_ROUTES: dict[tuple[str, str], object] = {}


def add_route(method: str, path: str, handler, prefix: bool = False) -> None:
    """Put a route in the table: ``handler(asked, query)`` answers ``method path``.

    With ``prefix``, the route answers every path that begins with ``path``,
    and ``handler(asked, query, rest)`` is handed what follows it. Adding a
    route again replaces the earlier one, which is what a workflow's Python
    half needs when the bridge is built twice in one process, as the tests do.
    """
    (PREFIX_ROUTES if prefix else ROUTES)[(method.upper(), path)] = handler


#: The names this computer answers to. A request that arrives under any other
#: name was sent to a web address that someone pointed at 127.0.0.1, which is
#: how a page from elsewhere would try to look like one served here.
THIS_COMPUTER = {"127.0.0.1", "localhost", "::1"}


def on_this_computer(address: str) -> bool:
    """Whether ``address`` (``host:port`` or a page's origin) names this computer."""
    if "//" not in address:
        address = f"//{address}"
    try:
        return urllib.parse.urlsplit(address).hostname in THIS_COMPUTER
    except ValueError:
        return False


def refusal_for(headers) -> str | None:
    """Why a request must not be answered, or None when it comes from this computer.

    The bridge listens on 127.0.0.1, so other computers cannot reach it. A web
    page open in a browser on the microscope computer can, though, and a
    browser sends such a page's request without asking first when it is
    dressed as plain text. Three things the browser always says tell such a
    request apart: the name it was sent to (``Host``), the page it came from
    (``Origin``), and, for a plain read such as a picture, whether it crossed
    from another site (``Sec-Fetch-Site``). The operator page, served by the
    bridge or by the development server on another port, is on this computer
    by all three. A script run here (the tests, curl) sends no ``Origin`` and
    is let through.
    """
    host = headers.get("Host") or ""
    if not on_this_computer(host):
        return f"the bridge only answers requests addressed to this computer, not to {host!r}"
    origin = headers.get("Origin")
    if origin is not None and not on_this_computer(origin):
        return f"the bridge only answers pages served on this computer, not one from {origin!r}"
    if origin is None and headers.get("Sec-Fetch-Site") == "cross-site":
        return "the bridge only answers pages served on this computer, not one from another site"
    return None


class Bridge(BaseHTTPRequestHandler):
    # Keep the connection: HTTP/1.0 opened a fresh TCP connection per
    # picture, which is 34 measured milliseconds a tile and seventy seconds
    # for a 2061-field overview. Every response carries its Content-Length,
    # which is what keep-alive requires.
    protocol_version = "HTTP/1.1"

    def allow_the_page(self) -> None:
        """Let the page that asked read the answer, when it is on this computer.

        The development server holds the page on another port, and a browser
        hides an answer from a page on another port unless it is named here.
        Only the page that asked is named, never everyone (``*``): a page
        from elsewhere has been refused before anything is answered.
        """
        origin = self.headers.get("Origin")
        if origin is not None and on_this_computer(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def refused(self) -> bool:
        """Answer 403 to a request that does not come from this computer, and say so."""
        why = refusal_for(self.headers)
        if why is None:
            return False
        # The body is read and dropped first: a connection closed with a body
        # still unread is reset on Windows, and the refusal never arrives.
        length = int(self.headers.get("Content-Length") or 0)
        if 0 < length <= 1_000_000:
            self.rfile.read(length)
        self.close_connection = True
        self._answer({"error": why}, status=403)
        return True

    def _answer(self, payload: dict, status: int = 200) -> None:
        body = json.dumps(payload, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.allow_the_page()
        self.end_headers()
        self.wfile.write(body)

    def _fail(self, why: Exception) -> None:
        """A failure as the sentence the page shows.

        A microscope that answered "I could not" is not a broken bridge, so it
        is told apart: a workflow raises it as a :class:`api.Refusal`, with a
        status of its own (409 by default), so whoever reads the log sees the
        instrument's own refusal rather than an internal error. The page shows
        the sentence either way, where the press was made.
        """
        said = str(why)
        if isinstance(why, Refusal):
            kind = why.status
        elif isinstance(why, KeyError):
            # Python says only the missing name, in quotes: "'record'".
            kind, said = 400, f"the request is missing {why.args[0]!r}" if why.args else said
        elif isinstance(why, (ValueError, TypeError)):
            kind = 400
        else:
            kind = 500
        self._answer({"error": said}, status=kind)

    #: What the built page is made of, and what to call each piece when sent.
    #: A browser will not start a background program from a file it was told is
    #: anything but JavaScript, and it says nothing when it refuses -- the
    #: picture simply never appears.
    PAGE = {
        ".html": "text/html", ".js": "text/javascript", ".mjs": "text/javascript",
        ".css": "text/css", ".json": "application/json", ".wasm": "application/wasm",
        ".svg": "image/svg+xml", ".png": "image/png", ".woff2": "font/woff2",
    }

    def _send_the_page(self, path: str) -> None:
        """Hand out the built operator page, so one process serves the whole thing.

        The microscope PC gets one program: the page it draws and the
        instrument it drives, on one address. That is also why the page finds
        the bridge at its own origin and needs telling only in development,
        where a dev server holds the page instead so that edits reload live.
        """
        if THE_PAGE is None:
            self._answer({"error": f"no page at {path}: there is no folder of workflows "
                                   f"({workflows.SETTING} is not set)"}, status=404)
            return
        name = path.lstrip("/") or "index.html"
        where = (THE_PAGE / name).resolve()
        wanted = self.PAGE.get(where.suffix)
        if THE_PAGE not in where.parents or wanted is None or not where.is_file():
            self._answer({"error": f"no page at {path}"}, status=404)
            return
        body = where.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", wanted)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, body: bytes, content_type: str) -> None:
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        # What a workflow answers in bytes is a picture of a run that is still
        # going (a scan's note, a field as it lands), so nothing here is worth
        # keeping: a cached note is a canvas that stops growing.
        self.send_header("Cache-Control", "no-store")
        self.allow_the_page()
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(length) or b"{}")

    def do_OPTIONS(self) -> None:  # noqa: N802 — http.server's naming
        if self.refused():
            return
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.allow_the_page()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _dispatch(self, method: str, asked: dict) -> None:
        """Answer one request from the route table, or say there is no such route.

        An exact route first; then the longest prefix route the path begins with.
        """
        path, _, query = self.path.partition("?")
        handler = ROUTES.get((method, path))
        if handler is not None:
            self._reply(handler(asked, query))
            return
        begins = [key for key in PREFIX_ROUTES if key[0] == method and path.startswith(key[1])]
        if begins:
            longest = max(begins, key=lambda key: len(key[1]))
            self._reply(PREFIX_ROUTES[longest](asked, query, path[len(longest[1]):]))
            return
        self._answer({"error": f"no route {path}"}, status=404)

    def _reply(self, answer) -> None:
        """A handler's answer: bytes as they are, anything else as JSON."""
        if isinstance(answer, Bytes):
            self._send_bytes(answer.body, answer.content_type)
        else:
            self._answer(answer)

    def do_GET(self) -> None:  # noqa: N802 — http.server's naming
        if self.refused():
            return
        path = self.path.partition("?")[0]
        try:
            if path.startswith("/api/"):
                self._dispatch("GET", {})
            else:
                self._send_the_page(path)
        except Exception as why:  # noqa: BLE001
            self._fail(why)

    def do_POST(self) -> None:  # noqa: N802 — http.server's naming
        if self.refused():
            return
        try:
            self._dispatch("POST", self._body())
        except Exception as why:  # noqa: BLE001
            self._fail(why)

    def log_message(self, *_args) -> None:
        """Quiet: the terminal is the operator's too."""


def a_bridge_on(port: int, args=None, *, halves=None) -> ThreadingHTTPServer:
    """A bridge ready to answer, with every workflow's Python half started.

    ``args`` are the parsed options, each half's own among them; ``halves``
    are the halves as :func:`workflows.load_halves` answers them, loaded here
    when not given. Each half's ``start(args)`` runs, and the first title one
    answers names the window (``listening.title``).
    """
    if halves is None:
        halves = workflows.load_halves(add_route)
    titles = [half.start(args) for _, half in halves if hasattr(half, "start")]
    listening = ThreadingHTTPServer(("127.0.0.1", port), Bridge)
    listening.halves = halves
    listening.title = next((title for title in titles if title), "ZMART")
    return listening


def serve(port: int = 8600, args=None, *, halves=None) -> ThreadingHTTPServer:
    """Start a bridge in a background thread and hand back its server; see :func:`a_bridge_on`."""
    listening = a_bridge_on(port, args, halves=halves)
    threading.Thread(target=listening.serve_forever, daemon=True).start()
    return listening


#: How long closing the window waits for a running scan to finish its field.
CLOSING_WAIT_S = 60.0


def shut_down(listening: ThreadingHTTPServer) -> None:
    """Close everything a bridge holds, when the window it served is closed.

    Each workflow's half closes what it holds (``close(wait_s)``), and the
    bridge stops listening. Each part is closed even when the one before it
    fails -- a microscope that no longer answers must not keep the bridge open
    -- and what failed is said in the terminal.
    """
    closings = [
        (lambda half=half: half.close(CLOSING_WAIT_S))
        for _, half in getattr(listening, "halves", []) if hasattr(half, "close")
    ]
    for closing in (*closings, listening.shutdown, listening.server_close):
        try:
            closing()
        except Exception as why:  # noqa: BLE001 -- the rest must still close
            print(f"while closing the interface: {why}", file=sys.stderr, flush=True)


def add_arguments(parser: argparse.ArgumentParser, halves=()) -> None:
    """Each workflow's half's own options, in a group named for it."""
    for name, half in halves:
        if hasattr(half, "add_arguments"):
            half.add_arguments(parser.add_argument_group(name))


def main(argv: list[str] | None = None) -> int:
    """Run the bridge on its own, for a browser: ``python -m zmart_interface.framework.bridge``."""
    parser = argparse.ArgumentParser(
        description="The bridge: the operator page's backend, serving the page and every workflow's routes",
    )
    parser.add_argument("--port", type=int, default=8600)
    halves = workflows.load_halves(add_route)
    add_arguments(parser, halves)
    args = parser.parse_args(argv)
    listening = a_bridge_on(args.port, args, halves=halves)
    print(f"bridge listening on 127.0.0.1:{args.port}")
    listening.serve_forever()
    return 0
