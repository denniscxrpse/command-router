#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Shared constants and paths used by the commands-router packages.

``uctx`` is deliberately not a mutable commands configuration object.  It
provides schema constants, serialized grammar keys, and a read-only listener
for the latest stderr message; fixture-owned settings such as ``cmd_prefix``,
the help policy, action functions, and argument overrides live on
``FixturesSetup`` instances in the control API.  Keeping commands settings out
of this module avoids hidden global state between independent control surfaces
and fixture initializations.
"""

__all__ = (
    "paths",
    "uctx",
)

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

from cmd_router.lib.control.api.result import ControlResultKinds
from cmd_router.utils.status import Status


@dataclass
class _Paths:
    @staticmethod
    def _get_root() -> Path:
        """Traverse up to find the project root (containing pyproject.toml)."""
        curr: Path = Path(__file__).resolve().parent
        while curr != curr.parent:
            if (curr / "uv.lock").exists():
                return curr
            curr: Path = curr.parent
        # Fallback to current directory if not found
        return Path.cwd()

    ROOT: Path = _get_root()
    FIXTURES: Path = ROOT / "fixtures"
    FIXTURES_HTTP: Path = FIXTURES / "http"
    LOGS_DIR: Path = ROOT / "logs"


@dataclass(frozen=True, slots=True)
class _UniversalContext:
    """Namespace containing shared constants and read-only observations."""

    INTERNAL_JSON_CONTRACT: Final[dict[str, Any]] = field(
        default_factory=lambda: {
            "ok": bool,  # [bool]
            "code": Status,  # code.name [_StatusContract]
            "kind": ControlResultKinds,  # [ControlResultKinds]
            "input": ...,  # [stdin?/Any]
            "command": str,  # [str]
            "value": ...,  # [Any]
            "suggestions": [str, ...],  # [list[str]]
            "parsed_args": None,  # context.args [CommandContext|null]
            "error": {...},  # error.to_dict [ParseError]
            "message": None,  # [str|null]
            "exception": None,  # [str|null]
        }
    )
    """Full response contract returned by ``ControlResult.to_dict``.

    Every mapping contains exactly these keys, in both plain dictionaries
    and JSON. Absent values are ``None`` (``null`` in JSON) instead of being
    omitted, so consumers can rely on a fixed shape:

    - ``ok`` (bool): whether the attempt succeeded.
    - ``code`` (str): ``code.name`` status string, e.g. ``"Success"``.
    - ``kind`` (str): result stage, e.g. ``"COMMAND"``, ``"INPUT"``,
      ``"UNEXPECTED_TOKEN"``. Stored as ``str`` so enums stay
      JSON-serializable.
    - ``input`` (Any): exact caller input, passed through unvalidated.
    - ``command`` (str|null): matched command without prefix, or ``None``
      for non-command ``INPUT`` results.
    - ``value`` (Any): action return value, or pass-through input for
      ``INPUT``. ``None`` when no action produced a value. Passed through
      as-is; the API never parses, validates, or converts it.
    - ``suggestions`` (list[str]|null): completion hints, or ``None`` when
      suggestions are disabled.
    - ``parsed_args`` (dict|null): ``context.args`` when a parse produced
      arguments, else ``None``.
    - ``error`` (dict|null): ``error.to_dict()`` for parse failures, else
      ``None``. The nested dict is itself fixed-shape and JSON-serializable.
    - ``message`` (str|null): human-readable detail, or ``None`` when there
      is nothing to report. A valid request such as ``/help advancement``
      therefore returns ``"message": None`` instead of dropping the key.
    - ``exception`` (str|null): formatted ``"Type: detail"`` for action
      failures, else ``None``.

    Valid requests (``ok=True``) carry the result in ``value`` with
    ``error``/``exception`` as ``None``; ``message`` is usually ``None``.
    Invalid requests (``ok=False``) keep ``value`` as ``None`` (unless a
    partial value exists), describe the failure in ``message``, and expose
    structured detail in ``error`` and/or ``exception``. In both cases all
    eleven keys are present.
    """

    INTERNAL_JSON_CONTRACT_COMPACT: Final[dict[str, Any]] = field(
        default_factory=lambda: {
            "ok": bool,  # [bool]
            "input": ...,  # [stdin?/Any]
            "value": ...,  # [Any]
            "suggestions": [str, ...],  # [list[str]]
            "error": Any,  # _transport_value(...) [Any]
            "message": None,  # [str|null]
        }
    )
    """Compact response contract returned by ``ControlResult.to_response``.

    Every mapping contains exactly these keys, in both plain dictionaries
    and JSON. Absent values are ``None`` (``null`` in JSON) instead of being
    omitted. It carries the outcome without the full diagnostic metadata,
    which saves bytes and CPU cycles on the hot stderr path:

    - ``ok`` (bool): whether the attempt succeeded.
    - ``input`` (Any): exact caller input, passed through unvalidated.
    - ``value`` (Any): action return value (or pass-through input),
      ``None`` when absent. Passed through as-is.
    - ``suggestions`` (list[str]|null): completion hints, or ``None`` when
      disabled.
    - ``error`` (Any): transported ``error_payload`` — a ``ParseError``
      dict, an exception string, or another caller payload; ``None`` when
      there is no error.
    - ``message`` (str|null): human-readable detail, or ``None`` when there
      is nothing to report.

    Valid requests (``ok=True``) return the outcome in ``value`` with
    ``error`` as ``None`` and ``message`` usually ``None``. Invalid requests
    (``ok=False``) return the failure in ``error``/``message`` with ``value``
    as ``None``. In both cases all six keys are present.
    """

    # Constant values used while validating grammar files.
    VALID_SCHEMAS: Final[frozenset[int]] = frozenset({1})
    "The valid schemas for the grammars."

    # Serialized key names used by grammar containers.
    cmd_router: Final[str] = "cmd-router"
    grammar: Final[str] = "grammar"
    schema_version: Final[str] = "schema-version"


paths: Final[_Paths] = _Paths()
uctx: Final[_UniversalContext] = _UniversalContext()
