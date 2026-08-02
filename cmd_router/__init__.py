#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

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

from cmd_router.grammar.loader import *
from cmd_router.utils.cli import *
from cmd_router.utils.context import *
from cmd_router.utils.logger import *

_Dict = dict[str, Any]


class CommandRouter:
    _grammars: _Dict = {}
    _info: _Dict = {}

    def __init__(self) -> None:
        # Get every single file in fixtures/*
        if flags.lazy:
            # pass control to lazy_init
            self._lazy_init()
            return
        files = [path for path in paths.FIXTURES.iterdir() if path.is_file()]
        result = self._init_grammar(files)
        if isinstance(result, int):
            log.critical(f"Could not initialize grammars ({result}).")
        ic(self._grammars, self._info)
        log.info("ready")

    def _lazy_init(self) -> None:
        """Load the first valid grammar received through the local HTTP endpoint."""

        # Keep HTTP grammars in a persistent cache between application runs.
        http_dir = paths.FIXTURES / "http"
        # Stop serving requests after one grammar loads successfully.
        state = {"success": False}
        # Let the request handler update this router instance.
        router = self

        # Define the small HTTP protocol used to receive a grammar.
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
                # Read and validate the request body length.
                try:
                    content_length = int(self.headers.get("Content-Length", "-1"))
                except ValueError:
                    self._invalid("Invalid HTTP content length.")
                    return

                if content_length < 0:
                    self._invalid("HTTP request has no content.")
                    return

                # Decode the grammar as UTF-8 text.
                payload = self.rfile.read(content_length)
                try:
                    text = payload.decode("utf-8")
                except UnicodeDecodeError:
                    self._invalid("HTTP grammar is not valid UTF-8.")
                    return

                # Detect whether the body is a JSON5 or TOML object.
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

                # Reuse an identical grammar already saved by an earlier run.
                existing: Path | None = None
                try:
                    for candidate in http_dir.glob(f"grammar-*{suffix}"):
                        try:
                            if candidate.is_file() and candidate.read_bytes() == payload:
                                existing = candidate
                                break
                        except OSError:
                            continue
                except OSError:
                    # Handle the request as new when the cache cannot be scanned.
                    pass

                if existing is not None:
                    # Load the cached grammar into this router instance.
                    result = load_grammars(existing)
                    if isinstance(result, int):
                        self._invalid("HTTP grammar has an invalid schema.")
                        return

                    router._normalize(result)
                    log.stderr(0)
                    log.debug(f"Reused HTTP grammar: {existing.name}")
                    state["success"] = True
                    self._reply(204)
                    return

                # Save unseen grammars under a unique filename.
                target = http_dir / f"grammar-{uuid4().hex}{suffix}"
                try:
                    http_dir.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(payload)
                    result = load_grammars(target)
                except OSError:
                    self._invalid("Could not save the HTTP grammar.")
                    return

                # Remove files that fail schema validation.
                if isinstance(result, int):
                    target.unlink(missing_ok=True)
                    self._invalid("HTTP grammar has an invalid schema.")
                    return

                # Store the grammar and signal that initialization is complete.
                router._normalize(result)
                log.stderr(0)
                log.debug(f"Saved HTTP grammar: {target.name}")
                state["success"] = True
                self._reply(204)

            # pyrefly: ignore [bad-override]
            def log_message(self, *_args: Any) -> None:
                # The lazy protocol reserves stderr for the port and errors.
                return

        # Bind an ephemeral localhost port and announce it to the client.
        server = HTTPServer(("127.0.0.1", 0), _Handler)
        log.stderr(server.server_port)
        try:
            # Process requests until a valid grammar is accepted.
            while not state["success"]:
                server.handle_request()
        finally:
            # Always release the listening socket.
            server.server_close()

    def _init_grammar(self, f: list[Path] | Path) -> tuple[_Dict, _Dict] | int:
        files = f if isinstance(f, list) else [f]

        # Keep bare filenames fast while also accepting full file or directory paths.
        ignored_names: set[str] = set()
        ignored_paths: set[Path] = set()
        for value in flags.ignore:
            candidate = Path(value).expanduser()
            if not candidate.is_absolute() and len(candidate.parts) == 1 and not candidate.is_dir():
                ignored_names.add(candidate.name)
                continue
            try:
                ignored_paths.add(candidate.resolve())
            except (OSError, RuntimeError):
                ignored_paths.add(candidate.absolute())

        # Load grammars unless their name or path was explicitly ignored.
        for file in files:
            if file.name in ignored_names:
                log.debug(f"Ignoring: {file.name}!")
                continue
            if ignored_paths:
                try:
                    file_path = file.resolve()
                except (OSError, RuntimeError):
                    file_path = file.absolute()
                if any(file_path == ignored or ignored in file_path.parents for ignored in ignored_paths):
                    continue
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
