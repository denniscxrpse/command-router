__all__ = (
    "CommandRouter",
    "init_flags",
)

from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from uuid import uuid4

import json5
import tomllib
from icecream import ic

from cmd_router.utils.cli import *
from cmd_router.utils.context import *
from cmd_router.utils.grammar_loader import *
from cmd_router.utils.logger import *

_Dict = dict[str, Any]


class CommandRouter:
    _grammars: _Dict
    _info: _Dict

    def __init__(self) -> None:
        self._grammars = {}
        self._info = {}

        # Get every single file in fixtures/*
        if flags.lazy:
            # pass control to lazy_init
            self._lazy_init()
            return
        files = [path for path in paths.FIXTURES.iterdir() if path.is_file()]
        result = self._init_grammar(files)
        if isinstance(result, int):
            log.critical(f"Could not initialize grammars ({result}).")
        ic(self._info, self._grammars)

    def _lazy_init(self) -> None:
        http_dir = paths.FIXTURES / "http"
        state = {"success": False}
        router = self

        class _Handler(BaseHTTPRequestHandler):
            def _reply(self, status: int, body: bytes = b"") -> None:
                self.send_response(status)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                if body:
                    self.wfile.write(body)

            def _invalid(self, message: str) -> None:
                log.stderr(1)
                log.warning(message)
                self._reply(400, b"1\n")

            # noinspection pep8-naming
            def do_POST(self) -> None:
                try:
                    content_length = int(self.headers.get("Content-Length", "-1"))
                except ValueError:
                    self._invalid("Invalid HTTP content length.")
                    return

                if content_length < 0:
                    self._invalid("HTTP request has no content.")
                    return

                payload = self.rfile.read(content_length)
                try:
                    text = payload.decode("utf-8")
                except UnicodeDecodeError:
                    self._invalid("HTTP grammar is not valid UTF-8.")
                    return

                suffix: str | None = None
                for candidate, parser in ((".json5", json5.loads), (".toml", tomllib.loads)):
                    try:
                        parsed = parser(text)
                    except (ValueError, tomllib.TOMLDecodeError):
                        continue
                    if isinstance(parsed, dict):
                        suffix = candidate
                        break

                if suffix is None:
                    self._invalid("HTTP body is not valid JSON5 or TOML.")
                    return

                target = http_dir / f"grammar-{uuid4().hex}{suffix}"
                try:
                    http_dir.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(payload)
                    result = load_grammars(target)
                except OSError:
                    self._invalid("Could not save the HTTP grammar.")
                    return

                if isinstance(result, int):
                    target.unlink(missing_ok=True)
                    self._invalid("HTTP grammar has an invalid schema.")
                    return

                router._normalize(result)
                log.stderr(0)
                log.debug(f"Saved HTTP grammar: {target.name}")
                state["success"] = True
                self._reply(204)

            # pyrefly: ignore [bad-override]
            def log_message(self, *_args: Any) -> None:
                # The lazy protocol reserves stderr for the port and errors.
                return

        server = HTTPServer(("127.0.0.1", 0), _Handler)
        log.stderr(server.server_port)
        try:
            while not state["success"]:
                server.handle_request()
        finally:
            server.server_close()

    def _init_grammar(self, f: list[Path] | Path) -> tuple[_Dict, _Dict] | int:
        files = f if isinstance(f, list) else [f]
        self._grammars = {}
        self._info = {}

        for file in files:
            result = load_grammars(file)
            if isinstance(result, int):
                if result == error.UnsupportedGrammarFormatError:
                    continue
                return result
            self._normalize(result)

        return self._grammars, self._info

    def _normalize(self, t: tuple[_Dict, _Dict]) -> None:
        grammars, info = t
        self._grammars.update(grammars)
        self._info.update(info)
