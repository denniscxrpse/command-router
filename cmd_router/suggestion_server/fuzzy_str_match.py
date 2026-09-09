#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.


__all__ = ["fuzzy_str_match"]

from heapq import nsmallest
from itertools import islice

try:
    from rapidfuzz.distance import Levenshtein
except ImportError:
    Levenshtein = None


def fuzzy_str_match(token: str | None, pool: list[str], limit: int) -> list[str]:
    """Rank *pool* against the failing *token* and return up to *limit* hints.

    Shared ranking used by both ``ParseError._get_suggestions`` (router
    ``error["suggestions"]``) and ``LazySuggestionsServer._immediate_suggestions``
    (``POST``/``GET`` suggestions). The three stages, in order:

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

    Args:
        token: Unmatched input fragment from the parse error, or ``None`` when
            input ended before a command was complete.
        pool: Candidate strings from ``ParseError.expected``. Entries starting
            with ``"<"`` are treated as type-hint placeholders, the rest as
            matchable literals.
        limit: Maximum hints to return. Values ``<= 0`` yield ``[]`` (slicing
            with a negative limit would otherwise wrap around).

    Returns:
        At most *limit* suggestion strings; never ``None``. ``None`` (disabled
        hints) is decided by callers via ``flags.no_suggestions``, not here.

    Complexity:
        Prefix scan is ``O(n)`` with ``n == len(pool)`` and stops after
        *limit* hits. Typo fallback is one Levenshtein comparison per literal,
        but the ``score_cutoff`` prunes most pairs to ``O(1)`` (length check,
        then bounded DP with early termination) instead of a full matrix;
        top-k selection is ``O(n log limit)``.
    """
    if limit <= 0:
        return []
    if not token:
        # Incomplete input or tokenization failure: no fragment to rank
        # against, so return the pool in order (gives up early when short).
        return pool[:limit]

    literals = [c for c in pool if not c.startswith("<")]

    # 1. Brigadier-style prefix narrowing (cheap, exact); stop at `limit`
    # hits instead of scanning the rest of the pool.
    prefixed = list(islice((c for c in literals if c.startswith(token)), limit))
    if prefixed:
        return prefixed

    # 2. Forgiving typo fallback, capped so suggestions cannot drift far.
    # The cutoff is handed to the metric so unreachable pairs never run the
    # matrix. `(d, c)` tuples make plain comparison equal the documented
    # `(distance, name)` key, and top-k avoids a full sort.
    if Levenshtein is not None:
        scored = [(d, c) for c in literals if (d := Levenshtein.distance(token, c, score_cutoff=2)) <= 2]
        if scored:
            return [c for _, c in nsmallest(limit, scored)]

    # 3. No literal close: preserve type hints rather than misleading names.
    # Partitioned lazily so the common paths above never build this list.
    return list(islice((c for c in pool if c.startswith("<")), limit))
