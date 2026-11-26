"""1RM estimation from recent training history rather than a single set.

Model, for a given lift and date:
  1. Take every set of that lift within the last `window_days` (up to and including the date).
  2. Estimate a 1RM per set: singles count as-is, otherwise the mean of Epley and Brzycki
     (Epley overshoots at low reps, Brzycki undershoots at high reps; the mean is steadier).
     Sets above `max_reps` are ignored -- they say little about max strength.
  3. Weight each estimate by recency (exponential decay, `half_life_days`) and by rep count
     (1/sqrt(reps): low-rep sets are better max predictors).
  4. Take a weighted high percentile (default p90). Back-off / volume work is intentionally
     submaximal, so a mean would systematically under-estimate.
  5. Floor at the heaviest weight lifted (any reps) in the window: you can't be weaker than what you lifted.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from .config import (
    ESTIMATE_HALF_LIFE_DAYS,
    ESTIMATE_MAX_REPS,
    ESTIMATE_PERCENTILE,
    ESTIMATE_WINDOW_DAYS,
)


@dataclass(frozen=True)
class SetObs:
    date: date
    weight_kg: float
    reps: int


def set_e1rm(weight_kg: float, reps: int, max_reps: int = ESTIMATE_MAX_REPS) -> float | None:
    if reps < 1 or weight_kg <= 0 or reps > max_reps:
        return None
    if reps == 1:
        return weight_kg
    epley = weight_kg * (1 + reps / 30)
    brzycki = weight_kg * 36 / (37 - reps)
    return (epley + brzycki) / 2


def weighted_percentile(values: list[tuple[float, float]], q: float) -> float:
    """values = [(value, weight)]; smallest value whose cumulative weight reaches q of the total."""
    items = sorted(values)
    total = sum(w for _, w in items)
    target = q * total
    acc = 0.0
    for v, w in items:
        acc += w
        if acc >= target - 1e-12:
            return v
    return items[-1][0]


def estimate_1rm(
    sets: list[SetObs],
    as_of: date,
    window_days: int = ESTIMATE_WINDOW_DAYS,
    half_life_days: float = ESTIMATE_HALF_LIFE_DAYS,
    percentile: float = ESTIMATE_PERCENTILE,
    max_reps: int = ESTIMATE_MAX_REPS,
) -> float | None:
    start = as_of - timedelta(days=window_days)
    obs: list[tuple[float, float]] = []
    best_single = 0.0
    for s in sets:
        if not (start < s.date <= as_of):
            continue
        if s.reps >= 1:
            # Any completed rep proves at least that weight as a single.
            best_single = max(best_single, s.weight_kg)
        e = set_e1rm(s.weight_kg, s.reps, max_reps)
        if e is None:
            continue
        age = (as_of - s.date).days
        w = math.pow(0.5, age / half_life_days) / math.sqrt(s.reps)
        obs.append((e, w))
    if not obs:
        return None
    return round(max(weighted_percentile(obs, percentile), best_single), 2)


def estimate_series(sets: list[SetObs], **kw) -> list[dict]:
    """Estimate as of every training date for this lift."""
    out = []
    for d in sorted({s.date for s in sets}):
        e = estimate_1rm(sets, d, **kw)
        if e is not None:
            out.append({"date": d.isoformat(), "e1rm_kg": e})
    return out


# DOTS coefficients (IPF, 2019+). Bodyweight is clamped to the formula's valid range.
_DOTS = {
    "m": ((-307.75076, 24.0900756, -0.1918759221, 0.0007391293, -0.000001093), (40.0, 210.0)),
    "f": ((-57.96288, 13.6175032, -0.1126655495, 0.0005158568, -0.0000010706), (40.0, 150.0)),
}


def dots(total_kg: float, bodyweight_kg: float, sex: str = "m") -> float:
    (a, b, c, d, e), (lo, hi) = _DOTS[sex]
    bw = min(max(bodyweight_kg, lo), hi)
    denom = a + b * bw + c * bw**2 + d * bw**3 + e * bw**4
    return round(total_kg * 500 / denom, 2)
