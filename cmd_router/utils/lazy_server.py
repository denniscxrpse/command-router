#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ("LazyServer",)

from http.server import BaseHTTPRequestHandler

from cmd_router.utils.logger import log

_CONTENT_LENGTH = "Content-Length"


class _LazyHandler(BaseHTTPRequestHandler):
    text: str
    payload: bytes

    def _reply(self, status: int, body: bytes = b"") -> None:
        self.send_response(status)
        self.send_header(_CONTENT_LENGTH, str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)

    def _invalid(self, message: str) -> None:
        log.warning("lazy request rejected: %s", message)
        log.stderr(1)
        self._reply(400, b"1\n")

    def post(self, whoami: str) -> None:
        log.info("lazy server for %s received POST request for %s", whoami, self.path)
        # Read and validate the request body length.
        try:
            content_length = int(self.headers.get(_CONTENT_LENGTH, "-1"))
        except ValueError:
            self._invalid("Invalid HTTP content length.")
            return

        if content_length < 0:
            self._invalid("HTTP request has no content.")
            return

        # Decode the grammar as UTF-8 text.
        self.payload = self.rfile.read(content_length)
        log.info("lazy request body read (%d byte(s))", len(self.payload))
        try:
            self.text = self.payload.decode("utf-8")
        except UnicodeDecodeError:
            self._invalid("HTTP is not valid UTF-8.")
            return


class LazyServer(_LazyHandler):
    def post(self, whoami: str) -> None:
        super().post(whoami)

    # noinspection shadowing-builtins
    def log_message(self, format, *args) -> None:
        log.raw(format, *args)
