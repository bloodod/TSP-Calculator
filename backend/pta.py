"""Problem Table Algorithm (PTA) for the Total Site Profile program.

The classic heat cascade from pinch analysis:

* Interval temperatures are the union of the *shifted* stream endpoints:
  hot streams are shifted DOWN by delta_t_min / 2 and cold streams UP by
  delta_t_min / 2.
* Within each interval the net heat flow is the CP sum times the interval
  width. In the combined table hot CPs count positive and cold CPs
  negative; in the hot-only / cold-only tables all CPs are summed positive.
* Cascading the heat from the hottest level downward gives the minimum hot
  and cold utility targets (combined table). The pinch is at the levels
  where the final cascade is zero.
"""

from __future__ import annotations

from dataclasses import dataclass

from .streams import Stream, StreamKind

KINDS = ("hot", "cold", "combined")


@dataclass(frozen=True)
class PtaInterval:
    """One temperature interval of the problem table."""

    index: int  # 1-based, hottest first
    t_high: float  # shifted top temperature, C
    t_low: float  # shifted bottom temperature, C
    cp_sum: float  # net CP (hot - cold for combined), kW/C
    delta_t: float  # C
    delta_h: float  # kW


@dataclass(frozen=True)
class ProblemTable:
    """Result of the problem table algorithm for one stream set.

    ``levels`` are the shifted interval temperatures in descending order
    (n + 1 values); ``intervals`` are the n temperature intervals between
    them; ``cascade`` holds the heat flow at each level (n + 1 values). For
    the combined table the cascade already includes the minimum hot utility
    added at the top, so all values are >= 0 and the pinch is where it is 0.
    """

    kind: str  # "hot" | "cold" | "combined"
    delta_t_min: float
    levels: tuple[float, ...]
    intervals: tuple[PtaInterval, ...]
    cascade: tuple[float, ...]
    min_hot_utility: float | None  # combined only
    min_cold_utility: float | None  # combined only
    pinch_temperatures: tuple[float, ...]  # shifted, combined only

    @property
    def total_duty(self) -> float:
        """Total duty of the table's streams (hot or cold only)."""
        return self.cascade[-1] if self.cascade else 0.0


def problem_table(
    streams: list[Stream],
    kind: str,
    delta_t_min: float = 0.0,
) -> ProblemTable:
    """Run the problem table algorithm over *streams* for one *kind*.

    ``kind`` selects which streams take part: ``"hot"``, ``"cold"`` or
    ``"combined"``.
    """
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")

    if kind == "combined":
        selected = list(streams)
    else:
        want = StreamKind.HOT if kind == "hot" else StreamKind.COLD
        selected = [s for s in streams if s.kind is want]

    half = delta_t_min / 2.0

    def shifted_ends(s: Stream) -> tuple[float, float]:
        if s.kind is StreamKind.HOT:
            return (s.tout - half, s.tin - half)
        return (s.tin + half, s.tout + half)

    levels = tuple(
        sorted({t for s in selected for t in shifted_ends(s)}, reverse=True)
    )

    def spans(s: Stream, t_low: float, t_high: float) -> bool:
        lo, hi = shifted_ends(s)
        return lo <= t_low and hi >= t_high

    intervals: list[PtaInterval] = []
    for i in range(len(levels) - 1):
        t_high, t_low = levels[i], levels[i + 1]
        cp = 0.0
        for s in selected:
            if not spans(s, t_low, t_high):
                continue
            if kind == "combined":
                cp += (
                    s.heat_capacity_flow
                    if s.kind is StreamKind.HOT
                    else -s.heat_capacity_flow
                )
            else:
                cp += s.heat_capacity_flow
        delta_t = t_high - t_low
        intervals.append(PtaInterval(i + 1, t_high, t_low, cp, delta_t, cp * delta_t))

    raw = [0.0]
    for iv in intervals:
        raw.append(raw[-1] + iv.delta_h)

    if kind == "combined":
        min_hot = -min(raw)
        cascade = tuple(v + min_hot for v in raw)
        min_cold = cascade[-1]
        tol = 1e-6 * max(1.0, max(abs(v) for v in cascade))
        pinch = tuple(
            levels[i]
            for i, v in enumerate(cascade)
            if i < len(levels) and abs(v) <= tol
        )
        return ProblemTable(
            kind, delta_t_min, levels, tuple(intervals), cascade,
            min_hot, min_cold, pinch,
        )

    return ProblemTable(
        kind, delta_t_min, levels, tuple(intervals), tuple(raw), None, None, ()
    )
