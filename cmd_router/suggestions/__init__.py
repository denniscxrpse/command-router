#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

__all__ = ["LazySuggestionsServer", "lazy_suggest_srv_ctx"]

import json
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlsplit

from cmd_router.suggestions.algo import fuzzy_str_match
from cmd_router.utils import LazyServer, Status, flags, log, stat, uctx

from .context import lazy_suggest_srv_ctx

if TYPE_CHECKING:
    from cmd_router.lib.commands.context import ParseError


class LazySuggestionsServer(LazyServer):
    """Lazy TCP suggestions server decoupled from the command-router responses.

    Consumers enable it with ``flags.suggestions_server`` and configure the
    endpoint through ``FixturesSetup.suggestions_server_address`` /
    ``suggestions_server_port`` (backed by ``lazy_suggest_srv_ctx``). When
    enabled, the server initializes just before the router reports 'ready' and
    the ``lazy`` flag is ignored for its lifecycle.

    Protocol (intentionally tiny; only the endpoint and response shape are fixed):

    - ``POST`` carries the partial command to complete. No body or specific
      format is required: an empty body is valid, and a non-``/`` request
      path (e.g. ``POST /gamemod``) is used as a fallback when the body is
      empty. A successful ``POST`` computes the currently available
      suggestions immediately (full ranked pool up to ``SUGGESTIONS_MAX``,
      not truncated to ``suggestions_set_current_size``), stores them in
      ``lazy_suggest_srv_ctx``, and replies ``204`` with no body.
    - ``GET`` returns the suggestions stored by the last successful ``POST``
      as a JSON list (``[]`` when nothing was posted yet), with
      ``Content-Type: application/json`` and status ``200``.

    Flag interactions (see ``EnvFlags.suggestions_server`` and
    ``EnvFlags.no_suggestions_server``):

    - ``no_suggestions_server=True`` completely disables the server; the
      router does not bind it at all, regardless of ``suggestions_server``.
    - Otherwise, when ``suggestions_server=False``, the handler stays
      available so disabled use is visible instead of a dropped connection:
      it logs at error level, ignores ``POST`` bodies (``204``), and answers
      ``GET`` with an empty JSON list (``200``). Every disabled request still
      returns ``stat.SuggestionServerDisabled()`` to the embedded caller.
    - The server never consults ``flags.no_suggestions``: it is an
      independent channel, so router ``error["suggestions"]`` behavior is
      unaffected, including when ``no_suggestions`` or
      ``max_sized_suggestions`` is enabled.

    All HTTP bytes are emitted through ``LazyServer`` helpers (``_reply`` /
    ``_invalid`` plus a small JSON reply built the same way). All error paths
    additionally return a centralized ``Status`` contract (``stat.*``) instead
    of raising, so embedded callers can branch on ``result.name``.
    """

    @staticmethod
    def _disabled() -> bool:
        """Return whether suggestion requests must take the disabled path.

        Completely disabled (``no_suggestions_server``) wins over everything;
        otherwise the server is disabled whenever ``suggestions_server`` is
        off. Kept as a helper so ``do_POST``/``do_GET`` cannot drift apart.
        """
        return bool(flags.no_suggestions_server or not flags.suggestions_server)

    @staticmethod
    def _err(what: str) -> Status:
        """Log a disabled-server request and return its status contract.

        The HTTP reply itself is sent by the caller (``204`` for ignored
        ``POST`` bodies, ``200`` + ``[]`` for ``GET``) so this helper stays a
        pure ``Status`` factory with a single flooding log line.
        """
        log.error("%s request received for suggestions server, but suggestions server is disabled", what)
        return stat.SuggestionServerDisabled()

    def _send_json_list(self, suggestions: list[str]) -> Status | None:
        """Reply ``200`` with *suggestions* encoded as a JSON list.

        Returns ``None`` on success or an ``Abort`` status when the payload
        cannot be serialized (the caller must then return that status). Uses
        the same ``send_response``/``send_header``/``end_headers`` pattern as
        ``LazyServer._reply``, plus an explicit JSON content type.
        """
        try:
            body = json.dumps(list(suggestions)).encode("utf-8")
        except (TypeError, ValueError) as exception:
            log.error("could not encode suggestions as JSON: %s", exception)
            self._reply(500)
            return stat.Abort()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            self.wfile.write(body)
        return None

    def _unsupported(self) -> Status:
        """Reply ``501`` with a JSON error for unsupported HTTP methods.

        ``BaseHTTPRequestHandler`` would otherwise answer with an HTML error
        page, breaking the JSON contract clients expect from this server.
        ``HEAD`` sends headers only, with no body, per HTTP semantics.
        """
        log.warning("unsupported %s request for suggestions server", self.command)
        try:
            body = json.dumps({"message": f"unsupported method: {self.command}"}).encode("utf-8")
        except (TypeError, ValueError) as exception:
            log.error("could not encode unsupported-method error as JSON: %s", exception)
            self._reply(500)
            return stat.Abort()
        self.send_response(501)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body) if self.command != "HEAD" else 0))
        self.end_headers()
        if body and self.command != "HEAD":
            self.wfile.write(body)
        return stat.Abort()

    # noinspection pep8-naming
    def do_PUT(self) -> Status:
        """Reject ``PUT`` with a JSON ``501``; see ``_unsupported``."""
        return self._unsupported()

    # noinspection pep8-naming
    def do_DELETE(self) -> Status:
        """Reject ``DELETE`` with a JSON ``501``; see ``_unsupported``."""
        return self._unsupported()

    # noinspection pep8-naming
    def do_PATCH(self) -> Status:
        """Reject ``PATCH`` with a JSON ``501``; see ``_unsupported``."""
        return self._unsupported()

    # noinspection pep8-naming
    def do_HEAD(self) -> Status:
        """Reject ``HEAD`` with ``501`` headers only; see ``_unsupported``."""
        return self._unsupported()

    # noinspection pep8-naming
    def do_OPTIONS(self) -> Status:
        """Reject ``OPTIONS`` with a JSON ``501``; see ``_unsupported``."""
        return self._unsupported()

    def _read_post_body(self) -> tuple[str | None, Status | None]:
        """Read the ``POST`` body leniently per the documented contract.

        An absent or empty body is valid (``POST`` requires no body) and
        yields ``""``. A present body reuses ``LazyServer.post`` for
        length/UTF-8 validation; when that helper already replied ``400`` via
        ``_invalid``, this returns ``(None, TokenizeInvalidError)`` so the
        caller only has to return the status.
        """
        raw_length = self.headers.get("Content-Length")
        if raw_length is None or str(raw_length).strip() == "":
            return "", None
        try:
            length = int(str(raw_length).strip())
        except ValueError:
            self._invalid("Invalid HTTP content length.")
            return None, stat.TokenizeInvalidError()
        if length <= 0:
            return "", None
        self.post(self.__class__.__name__)
        if not hasattr(self, "text"):
            return None, stat.TokenizeInvalidError()
        return self.text, None

    def _request_input(self, body_text: str) -> str:
        """Combine the ``POST`` body with the request path fallback.

        When the body is blank and the path carries a segment (``POST
        /gamemod``), the decoded path segment becomes the input. Otherwise
        the body is used as-is. The result is stripped but otherwise
        unvalidated; normalization (prefix handling) happens later.
        """
        if body_text.strip():
            return body_text.strip()
        if self.path not in ("", "/"):
            try:
                segment = unquote(urlsplit(self.path).path).lstrip("/")
                if segment.strip():
                    log.debug("using POST path as suggestion input %r", segment)
                    return segment.strip()
            except ValueError as exception:
                log.warning("could not decode POST path %r: %s", self.path, exception)
        return ""

    @staticmethod
    def _immediate_suggestions(error: ParseError) -> list[str]:
        """Rank *error.expected* via ``fuzzy_str_match`` capped at ``SUGGESTIONS_MAX``.

        Unlike ``ParseError._get_suggestions``, ignores ``suggestions_set_current_size``
        and ``no_suggestions`` so ``POST`` stores the full available pool.
        """
        limit = uctx.SUGGESTIONS_MAX
        pool: list[str] = list(error.expected or ())
        if not pool:
            return []
        return fuzzy_str_match(error.token, pool, limit)

    def _compute_suggestions(self, command_text: str) -> tuple[list[str] | None, Status | None]:
        """Parse *command_text* against the live dispatcher for suggestions.

        Returns ``(suggestions, None)`` on success (``[]`` when the command
        is already complete) or ``(None, error_status)`` when the control
        surface is not ready. Unexpected parse failures are caught and
        reported as ``Abort`` so a malformed grammar can never escape as an
        exception from the HTTP handler.
        """
        try:
            # circular imports go brrr
            from cmd_router.lib.control.api.control import control as _shared_control
        except ImportError as exception:
            log.error("suggestions server could not access the control surface: %s", exception)
            return None, stat.ControlNotInitializedError()
        try:
            deeper = _shared_control.deeper_context
            dispatcher = deeper.dispatcher
            initialized = deeper.initialized
            prefix = deeper.cmd_prefix
        except Exception as exception:
            log.error("suggestions server could not inspect the control surface: %s", exception)
            return None, stat.ControlNotInitializedError()
        if not initialized or dispatcher is None:
            log.error("suggestions POST received before the control surface was initialized")
            return None, stat.ControlNotInitializedError()
        text = command_text.strip()
        if isinstance(prefix, str) and prefix and text.startswith(prefix):
            text = text[len(prefix) :]
        try:
            parsed = dispatcher.parse(text)
        except Exception as exception:
            log.error("suggestions server failed to parse %r: %s", command_text, exception)
            return None, stat.Abort()
        if parsed.ok:
            return [], None
        error = parsed.error
        if error is None:
            return [], None
        return self._immediate_suggestions(error), None

    # noinspection pep8-naming
    def do_POST(self) -> Status:
        """Store suggestions for the posted partial command; reply ``204``.

        Disabled (see class docs): drains any body, replies ``204`` without
        storing anything, and returns ``SuggestionServerDisabled``. Enabled:
        reads the body leniently, falls back to the request path, parses it
        against the live dispatcher, stores the immediate suggestion pool,
        replies ``204``, and returns ``Success``. Body validation failures
        reply ``400`` (via ``LazyServer``) and return ``TokenizeInvalidError``;
        requests before control readiness reply ``503`` and return
        ``ControlNotInitializedError``; unexpected failures reply ``500`` and
        return ``Abort``.
        """
        if self._disabled():
            status = self._err("POST")
            try:
                raw_length = self.headers.get("Content-Length")
                length = int(str(raw_length).strip()) if raw_length is not None else 0
                if length > 0:
                    self.rfile.read(length)
            except (ValueError, OSError) as exception:
                log.warning("could not drain disabled suggestions POST body: %s", exception)
            self._reply(204)
            return status
        body, body_error = self._read_post_body()
        if body_error is not None:
            return body_error
        assert body is not None
        command_text = self._request_input(body)
        suggestions, compute_error = self._compute_suggestions(command_text)
        if compute_error is not None:
            if compute_error.name == stat.ControlNotInitializedError().name:
                self._reply(503)
            else:
                self._reply(500)
            return compute_error
        assert suggestions is not None
        lazy_suggest_srv_ctx.set_suggestions(suggestions, last_input=command_text)
        log.info("suggestions stored for %r (%d item(s))", command_text, len(suggestions))
        self._reply(204)
        return stat.Success()

    # noinspection pep8-naming
    def do_GET(self) -> Status:
        """Return the last stored suggestions as a JSON list; reply ``200``.

        Disabled (see class docs): logs the disabled status, replies ``200``
        with ``[]``, and returns ``SuggestionServerDisabled`` so polling
        clients keep a fixed JSON-list shape instead of a dropped connection.
        Enabled: replies ``200`` with the stored list (``[]`` when no ``POST``
        has succeeded yet) and returns ``Success``; serialization failures
        reply ``500`` and return ``Abort``.
        """
        if self._disabled():
            status = self._err("GET")
            failure = self._send_json_list([])
            if failure is not None:
                return failure
            return status
        suggestions = lazy_suggest_srv_ctx.get_suggestions()
        log.info("suggestions served (%d item(s))", len(suggestions))
        failure = self._send_json_list(suggestions)
        if failure is not None:
            return failure
        return stat.Success()
