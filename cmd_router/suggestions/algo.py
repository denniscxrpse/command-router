#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

"""Algorithms for suggestions."""

__all__ = ["fuzzy_str_match", "fit_to_budget"]

from bisect import bisect_right
from collections.abc import Iterable, Sequence
from heapq import nsmallest
from itertools import accumulate, chain, islice
from typing import Final

from cmd_router.utils import flags, log, uctx

_ENC = "utf-8"

try:
    from rapidfuzz.distance import Levenshtein
except ImportError:
    log.error("Levenshtein uninstalled, suggestions might behave worse.")
    Levenshtein = None

X: Final[int] = uctx.SUGGESTIONS_MAX
"""Absolute limit on the number of suggestions."""
Y: Final[int] = flags.suggestions_payload
"""Suggestion payload; read ``flags.suggestions_payload``."""
Z: Final[int] = 4
"""Overhead of the ranked string in a list where we count:
- BRACKETS = ``"["`` + ``"]"`` = 2
- SPACES = ``","`` + ``" "`` = 2
"""

# Methods mustn't use the logger. They are supposed to be stateless (and fast).


def _emit(ranked: Iterable[str], budget: int, salvage: bool = False) -> list[str]:
    """Materialize *ranked* (final order) into a list whose str() fits *budget*.

    Model: ``bytes(str(list)) == sum(len(w.encode()) + Z)``. The running total is
    the only state; the cut index is *reached* in emission order — never
    searched — and items past the cut are never measured at all.
    """
    out: list[str] = []
    total = 0
    for w in ranked:
        cost = len(w.encode(_ENC)) + Z
        if total + cost > budget:
            if salvage:
                room = budget - total - Z
                if room > 0:
                    out.append(w.encode(_ENC)[:room].decode(_ENC, "ignore"))
            break
        total += cost
        out.append(w)
    return out


def fit_to_budget(ranked: Sequence[str], budget: int) -> list[str]:
    """Truncate an already-ranked list so ``str(result)`` fits *budget*.

    Separate utility for lists built by *other* producers, where ranking and
    budgeting happen at different times with consumer-specific budgets. Unlike
    the fused emission inside ``fuzzy_str_match`` (which measures only shipped
    words while materializing), this measures the whole list first: cumulative
    serialized costs via ``accumulate`` (``cumsum``), then the cut index via
    ``bisect_right`` (``searchsorted``) — ``O(n)`` measure plus ``O(log n)``
    search. Same ``+Z``-per-word cost model (words assumed free of
    quotes/backslashes).

    Args:
        ranked: Suggestions in final order; the result is always a prefix.
        budget: Maximum ``len(str(result).encode(_ENC))``. Values ``<= 0``
            yield ``[]``.

    Returns:
        The longest prefix of *ranked* whose serialized form fits *budget*.
    """
    if budget <= 0:
        return []
    items = list(ranked)
    if not items:
        return []
    totals = list(accumulate(len(w.encode(_ENC)) + Z for w in items))
    return items[: bisect_right(totals, budget)]


def fuzzy_str_match(token: str | None, pool: list[str], limit: int, budget: int = Y) -> list[str]:
    """
    Rank *pool* against the failing *token*; up to *limit* hints, and
    ``len(str(result).encode(_ENC)) <= budget`` *by construction*
    (words assumed free of quotes/backslashes, per the ``+Z`` model).

    Shared ranking used by both ``ParseError._get_suggestions`` (router
    ``error["suggestions"]``) and ``LazySuggestionsServer._immediate_suggestions``
    (``POST``/``GET`` suggestions).

    The three stages, in order:

    1. No fragment (``token`` is ``None`` or ``""``): incomplete input or a
       tokenization failure leaves nothing to rank against, so return the pool
       in definition order, truncated to *limit*.
    2. Prefix narrowing (Brigadier parity): return literals with
       ``candidate.startswith(token)`` in pool order, truncated to *limit*.
       This is the affordable exact path, e.g. ``gamemod`` narrows to ``gamemode``.
    3. Typo fallback: when no literal shares the prefix, score literals with
       Levenshtein distance (``rapidfuzz``), keep distance ``<= 2`` (the same
       "did you mean" cap git/npm use), sort by ``(distance, name)``, and
       truncate to *limit*, e.g. ``tlel`` still suggests ``tell``. If
       ``rapidfuzz`` is unavailable, this stage is skipped. When no literal is
       close, ``<placeholders>`` (entries starting with ``"<"``) are returned
       instead of misleading names, so type hints survive; otherwise ``[]``.

    Complexity:
        Output-bounded. Every stage emits in final ranked order, so the byte
        budget is enforced while materializing — the cut is reached, never
        searched. At most ``min(limit, budget // Z)`` items are emitted, and
        at most ``budget`` bytes are measured, regardless of pool size; the
        discarded tail is never measured. Ranking costs are unchanged
        (cutoff-pruned Levenshtein pass, ``O(n log limit)`` top-k).

    Args:
        token: Unmatched input fragment from the parse error, or ``None`` when
            input ended before a command was complete.
        pool: Candidate strings from ``ParseError.expected``. Entries starting
            with ``"<"`` are treated as type-hint placeholders, the rest as
            matchable literals.
        limit: Maximum hints to return. Values ``<= 0`` yield ``[]`` (slicing
            with a negative limit would otherwise wrap around).
        budget: Maximum bytes to measure in the result, e.g. ``1024``. Values
            ``<= 0`` yield ``[]`` (slicing with a negative limit would
            otherwise wrap around).

    Returns:
        At most *limit* suggestion strings; never ``None``. ``None`` (disabled
        hints) is decided by callers via ``flags.no_suggestions``, not here.
    """
    # Pure-math cardinality cap, O(1) and lossless: every item costs >= Z
    # serialized bytes, so nothing shippable is discarded — and it bounds
    # every stage below by the OUTPUT size, not the pool size.
    limit = min(limit, X, budget // Z)
    if limit <= 0:
        return []
    if not token:
        # Incomplete input / tokenization failure: pool order, budgeted.
        return _emit(islice(iter(pool), limit), budget)

    literals = [c for c in pool if not c.startswith("<")]

    # 1. Prefix narrowing. The peek decides stage precedence; emission then
    # stops at `limit` hits OR budget exhaustion — the same early-exit shape.
    prefixed = islice((c for c in literals if c.startswith(token)), limit)
    first = next(prefixed, None)
    if first is not None:
        return _emit(chain((first,), prefixed), budget)

    # 2. Typo fallback. Ranking is global (one cutoff-pruned passes over the
    # pool), but emission stays streaming: only shipped words get measured.
    if Levenshtein is not None:
        scored = [(d, c) for c in literals if (d := Levenshtein.distance(token, c, score_cutoff=2)) <= 2]
        if scored:
            return _emit((c for _, c in nsmallest(limit, scored)), budget)

    # 3. Placeholders — lazy as before, now also budgeted.
    return _emit(islice((c for c in pool if c.startswith("<")), limit), budget)
