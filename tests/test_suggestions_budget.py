#  The Clear BSD License
#
#  Copyright (c) 2026 Ian Hylton
#  All rights reserved.

#  The Clear BSD License
#
"""Byte-budget contract for suggestion emission.

``fuzzy_str_match`` fuses ranking and emission so ``len(str(out).encode())``
fits the budget by construction; ``fit_to_budget`` is the separate
cumsum+searchsorted fitter for already-ranked lists from other producers.
"""

import random

from cmd_router.suggestions.algo import fit_to_budget, fuzzy_str_match
from cmd_router.utils.cli import flags
from cmd_router.utils.context import uctx

_BUDGET = flags.suggestions_payload


def _size(words: list[str]) -> int:
    return len(str(words).encode("utf-8"))


def _typo_mutants(token: str = "abcde") -> list[str]:
    """Single-substitution mutants: all len 5, distance 1, no prefix hit."""
    out: list[str] = []
    for i in range(len(token)):
        for letter in "xyz":
            if letter != token[i]:
                out.append(token[:i] + letter + token[i + 1 :])
    return out


def test_explicit_large_budget_restores_count_truncation() -> None:
    many = [f"w{i}" for i in range(uctx.SUGGESTIONS_MAX + 50)]
    assert fuzzy_str_match(None, many, uctx.SUGGESTIONS_MAX, budget=10**6) == many[: uctx.SUGGESTIONS_MAX]


def test_nonpositive_budget_yields_empty() -> None:
    assert fuzzy_str_match(None, ["a", "b"], 5, budget=0) == []
    assert fuzzy_str_match("abcde", ["abcdf"], 5, budget=-1) == []
    assert fit_to_budget(["a", "b"], 0) == []
    assert fit_to_budget(["a", "b"], -3) == []
    assert fit_to_budget([], 100) == []


def test_byte_invariant_holds_by_construction() -> None:
    random.seed(77)
    words = [
        "say",
        "tell",
        "gamemode",
        "advancement",
        "help",
        "tp",
        "debug",
        "survival",
        "x",
        "tlel",
        "gamemod",
        "<target>",
        "<m...>",
        "supercalifragilistic",
        "héllo",
    ]
    tokens = [None, "", "g", "gamemod", "tlel", "zzz", "say", "supercali"]
    for i in range(300):
        pool = [random.choice(words) for _ in range(random.randint(0, 12))]
        token = tokens[i % len(tokens)]
        limit = random.choice([1, 2, 5, 255])
        out = fuzzy_str_match(token, pool, limit)
        assert len(out) <= limit
        assert _size(out) <= _BUDGET
        # Budgeted output is a prefix of the unbounded ranking.
        full = fuzzy_str_match(token, pool, limit, budget=10**9)
        assert out == full[: len(out)]


def test_typo_stage_costs_live_in_narrow_band() -> None:
    token = "abcde"
    pool = _typo_mutants(token) + ["zzzzz", "qq", "<target>"]
    out = fuzzy_str_match(token, pool, 255, budget=10**9)
    assert len(out) > 5  # typo stage actually hit
    costs = {len(w.encode("utf-8")) + 4 for w in out}
    # Levenshtein bound: survivors satisfy |len(w) - len(token)| <= 2.
    assert costs <= set(range(len(token) + 2, len(token) + 7))


def test_typo_stage_closed_form_estimate_is_exact() -> None:
    token = "abcde"
    pool = _typo_mutants(token) + ["zzzzz", "qq"]
    # All survivors are len 5 (cost 9); k == budget // (t + 4) exactly.
    assert fuzzy_str_match(token, pool, 255, budget=100) == sorted(pool[:15])[:11]
    assert len(fuzzy_str_match(token, pool, 255, budget=100)) == 100 // (len(token) + 4) == 11
    assert len(fuzzy_str_match(token, pool, 255, budget=95)) == 95 // (len(token) + 4) == 10


def test_prefix_stage_has_no_bounded_estimate() -> None:
    pool = ["g", "g" * 10, "g" * 51, "g" * 200]
    out = fuzzy_str_match("g", pool, 255, budget=100)
    # Naive typo-style estimate assumes a narrow cost band around len(token).
    naive = 100 // (len("g") + 4)
    assert out == ["g", "g" * 10, "g" * 51]
    assert len(out) != naive  # 3 != 20: tails are unbounded, fusion is required
    costs = [len(w.encode("utf-8")) + 4 for w in out]
    assert max(costs) - min(costs) > 4  # band violated: no O(1) estimate exists
    assert _size(out) <= 100  # ...yet measured emission still fits


def test_fit_to_budget_matches_fused_emission() -> None:
    random.seed(13)
    words = ["say", "tell", "gamemode", "x", "tlel", "<target>", "héllo", "qq"]
    for _ in range(100):
        pool = [random.choice(words) for _ in range(random.randint(0, 10))]
        token = random.choice([None, "gamemod", "tlel", "zzz"])
        ranked = fuzzy_str_match(token, pool, 5, budget=10**9)
        for budget in (0, 1, 7, 50, 508, 10**6):
            assert fit_to_budget(ranked, budget) == fuzzy_str_match(token, pool, 5, budget=budget)


def test_fit_to_budget_boundaries() -> None:
    assert fit_to_budget(["ab", "cd"], _size(["ab", "cd"])) == ["ab", "cd"]
    assert fit_to_budget(["ab", "cd"], _size(["ab", "cd"]) - 1) == ["ab"]
    # Multibyte words are measured in bytes, not characters.
    assert fit_to_budget(["héllo"], 10) == ["héllo"]
    assert fit_to_budget(["héllo"], 9) == []


def test_fit_to_budget_does_not_mutate_input() -> None:
    ranked = ["b", "a", "c"]
    assert fit_to_budget(ranked, 100) == ["b", "a", "c"]
    assert ranked == ["b", "a", "c"]


def test_salvage_default_is_off() -> None:
    # A word that cannot fit whole is dropped, never truncated.
    assert fit_to_budget(["toolongword"], 8) == []
