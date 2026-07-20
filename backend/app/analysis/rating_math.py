"""VA combined-rating arithmetic per 38 CFR §4.25 (combined ratings table)
and §4.26 (bilateral factor).

§4.25: ratings are combined, not added. Order ratings descending; combine the
first two as `a + b*(100-a)/100`; combine that intermediate value (NOT
rounded) with the next rating; only the FINAL combined value is rounded to
the nearest degree divisible by 10 (values ending in 5 round up).

§4.26: when compensable disabilities affect paired limbs (or paired skeletal
muscles), combine just those, add 10% of that combined value (the bilateral
factor), and treat the sum as ONE rating which is then combined with the
rest. Per the regulation the bilateral factor is applied before other
combinations and the intermediate value keeps its decimal.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Rating:
    percent: int
    bilateral_group: str | None = None  # e.g. "legs", "arms"; None = not paired
    label: str = ""


def _combine_pair(a: float, b: float) -> float:
    return a + b * (100.0 - a) / 100.0


def _combine_descending(values: list[float]) -> float:
    total = 0.0
    for v in sorted(values, reverse=True):
        total = _combine_pair(total, v)
    return total


def _round_to_ten(value: float) -> int:
    return int(round(value / 10.0)) * 10


def combined_value(percents: list[int]) -> float:
    """Unrounded §4.25 combined value (e.g. [60, 30] → 72.0)."""
    return _combine_descending([float(p) for p in percents if p > 0])


def combined_rating(percents: list[int]) -> int:
    """Final §4.25 combined degree, rounded to nearest 10 ([60,30] → 70)."""
    if not any(p > 0 for p in percents):
        return 0
    return _round_to_ten(combined_value(percents))


def combined_rating_bilateral(ratings: list[Rating]) -> int:
    """Full §4.25 + §4.26 combination.

    Bilateral groups with 2+ compensable ratings get the bilateral factor;
    the factored value participates as a single rating in the final
    descending combination.
    """
    groups: dict[str, list[float]] = {}
    rest: list[float] = []
    for r in ratings:
        if r.percent <= 0:
            continue
        if r.bilateral_group:
            groups.setdefault(r.bilateral_group, []).append(float(r.percent))
        else:
            rest.append(float(r.percent))

    values: list[float] = list(rest)
    for members in groups.values():
        if len(members) >= 2:
            base = _combine_descending(members)
            values.append(base * 1.10)  # +10% bilateral factor, decimal kept
        else:
            values.extend(members)

    if not values:
        return 0
    return _round_to_ten(_combine_descending(values))


def what_if(current: list[Rating], added: Rating) -> dict:
    """Projected impact of one additional rating."""
    before = combined_rating_bilateral(current)
    after = combined_rating_bilateral(current + [added])
    return {"before": before, "after": after, "delta": after - before}
