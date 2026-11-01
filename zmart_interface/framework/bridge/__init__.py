"""The bridge: where the operator page's backend verbs meet each workflow's Python half.

The operator page runs in a browser and cannot import Python, so it speaks
to this package over HTTP. The bridge serves the built page, and dispatches
every ``/api/`` route to the workflow's Python half that registered it,
under ``/api/<folder>/``. It knows no workflow and no instrument: a half
(``<folder>/bridge`` in the folder of workflows; see ``workflows``) brings its own routes, its
own command-line options, what it does at start and what it closes at the
end, and imports of the framework only ``api.py``, the agreement between
the two.

* ``api`` — what a half is handed and may answer: bytes, and a refusal with
  a status of its own.
* ``workflows`` — where the folder of workflows is (``ZMART_INTERFACE_WORKFLOWS``),
  and every workflow's Python half in it, found and wired in at start-up.
* ``server`` — the routes as a table, the built page, who may ask, and
  ``serve``/``main``.

Run on its own, for a browser instead of the window::

    python -m zmart_interface.framework.bridge --port 8600

It starts every workflow's Python half with it: target acquisition offers
its own mock microscope first
(``examples/target_acquisition/bridge/starting.py``).

Author: Thom de Hoog, Center for Microscopy and Image Analysis (ZMB),
University of Zurich (thom.dehoog@zmb.uzh.ch, thomdehoog@gmail.com).
"""

from .server import THE_PAGE, add_arguments, main, serve, shut_down

__all__ = ["THE_PAGE", "add_arguments", "main", "serve", "shut_down"]
