"""The ZMART interface: the operator page in a window of its own.

This is how the page is meant to be met -- a native window, not a browser tab
with its chrome, its zoom and its address bar. It starts the bridge (the part
that talks to the microscope through the ZMART Controller), opens the window,
and points one at the other::

    zmart-interface                 # the built page, as the microscope runs it
    zmart-interface --dev           # the development server's page, edits reload live

By default the bridge serves the page and the instrument on one address, which
is exactly how it runs on the microscope PC. The interface brings no workflow
of its own: it runs the workflows in the folder ``ZMART_INTERFACE_WORKFLOWS``
names (in a checkout of this repository, its ``examples/``), and serves the
page built from them, which sits in that folder as ``built-page/``. The page is
built once, on a computer with Node.js, and committed beside the workflows, so
nothing has to be built on the microscope.

``--dev`` is for working on the page itself: the Vite development server
(``npm run dev``, in a checkout of this repository) holds the page so edits
appear as they are saved, and the page is told where the bridge is.

Why the page is served rather than opened from the disk
-------------------------------------------------------

One of the drawing engines is neuroglancer, which does part of its work in
background programs, and a browser refuses to start one for a page opened off
the disk, because such a page has no address of its own. So the page is
served over HTTP, by the bridge, which is already here.

The window is drawn by pywebview, which on Windows uses the WebView2 runtime,
which is Chromium. On a Mac it is drawn by Chromium too, through Qt: macOS's
own WebKit, which pywebview would take there, drops the overview's picture
after a deep zoom and draws the tiles flat until the view refreshes. With Qt
missing the window does not open on WebKit; it says what to install instead.

Author: Thom de Hoog, Center for Microscopy and Image Analysis (ZMB),
University of Zurich (thom.dehoog@zmb.uzh.ch, thomdehoog@gmail.com).
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request

#: Where ``npm run dev`` serves the page while it is being worked on.
DEV_URL = "http://127.0.0.1:5174/"


def _dev_server_is_up(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except (urllib.error.URLError, OSError):
        return False


def main(argv: list[str] | None = None) -> int:
    from zmart_interface.framework.bridge import server, workflows

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dev", nargs="?", const=DEV_URL, default=None, metavar="URL",
        help=f"open the development server's page instead of the built one (default {DEV_URL})",
    )
    try:
        halves = workflows.load_halves(server.add_route)
    except workflows.NoWorkflows as why:
        print(why)
        return 1
    server.add_arguments(parser, halves)
    args = parser.parse_args(argv)
    # What ``npm run build`` leaves in the folder of workflows: the page and
    # neuroglancer's two background programs beside it. The bridge hands them
    # out, so where they are is the bridge's to say.
    built = server.THE_PAGE / "index.html"

    if args.dev and not _dev_server_is_up(args.dev):
        print(f"nothing answering at {args.dev} — start it with `npm run dev`, or leave out --dev")
        return 1
    if not args.dev and not built.exists():
        print(f"no built page at {built} — build it from these workflows with "
              f"`npm run build` in a checkout of ZMART-interface, with {workflows.SETTING} "
              "set to their folder")
        return 1

    try:
        import webview
    except ModuleNotFoundError:
        print("this needs the 'pywebview' package; or run "
              "`python -m zmart_interface.framework.bridge` and open its address in a browser")
        return 1
    # On a Mac, Qt's Chromium and never WebKit, which draws the overview's
    # tiles flat after a deep zoom.
    qt = sys.platform == "darwin"
    if qt:
        try:
            import qtpy.QtWebEngineWidgets  # noqa: F401
        except Exception:
            print("on a Mac the window needs Qt's Chromium: "
                  "pip install \"pywebview[pyside6]\"")
            return 1

    listening = server.serve(0, args, halves=halves)
    bridge_at = f"http://127.0.0.1:{listening.server_address[1]}"
    if args.dev:
        # The development server holds the page so edits reload live, which
        # puts it on another address from the bridge -- so the page is told.
        target = f"{args.dev}{'&' if '?' in args.dev else '?'}bridge={bridge_at}"
        note = f"development page · {args.dev} · bridge at {bridge_at}"
    else:
        target, note = bridge_at, f"built page · served with the bridge at {bridge_at}"

    print(f"opening the {note}")
    webview.create_window(listening.title, target, width=1500, height=950)
    try:
        webview.start(gui="qt" if qt else None)
    finally:
        # The window is closed: the session with the microscope software is
        # closed with it, rather than left open until the process is killed.
        server.shut_down(listening)
    return 0


if __name__ == "__main__":
    sys.exit(main())
