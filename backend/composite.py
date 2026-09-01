"""Composite curve construction for the Total Site Profile program.

A composite curve is the cumulative enthalpy of all streams of one kind
(hot or cold) plotted against temperature. The interval temperatures are the
union of the streams' endpoints; between two consecutive intervals the total
heat capacity flow rate is the sum of the CPs of the streams spanning that
interval::

    Q_interval = sum(CP) * (T_high - T_low)

Both curves accumulate in the same direction: starting at the lowest
temperature with Q = 0 and ending at the highest temperature with the total
duty. For the hot composite this means the enthalpy at temperature T is the
heat released by the hot streams between T_min and T.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .streams import Stream, StreamKind, UtilityStream


@dataclass(frozen=True)
class CompositeCurve:
    """Cumulative enthalpy profile of one stream kind.

    ``temperatures`` and ``enthalpy`` are parallel tuples ordered along the
    curve: temperature increases and enthalpy accumulates from 0 at the
    lowest temperature up to the total duty at the highest temperature, for
    both hot and cold composites.
    """

    kind: StreamKind
    temperatures: tuple[float, ...]  # C, ascending
    enthalpy: tuple[float, ...]  # kW, cumulative

    @property
    def total_enthalpy(self) -> float:
        """Total duty of the composite in kW."""
        return self.enthalpy[-1] if self.enthalpy else 0.0

    def points(self) -> list[tuple[float, float]]:
        """Curve as (temperature, enthalpy) pairs."""
        return list(zip(self.temperatures, self.enthalpy))

    def shifted(self, delta_t_min: float) -> "CompositeCurve":
        """Same enthalpy profile with temperatures shifted by *delta_t_min*.

        Hot composites are shifted down and cold composites up. This is the
        standard way to visualize the minimum approach: where the hot curve
        meets the shifted cold curve, the actual approach equals
        *delta_t_min* (the pinch).
        """
        if self.kind is StreamKind.HOT:
            temperatures = tuple(t - delta_t_min for t in self.temperatures)
        else:
            temperatures = tuple(t + delta_t_min for t in self.temperatures)
        return CompositeCurve(self.kind, temperatures, self.enthalpy)


def build_composite(streams: list[Stream], kind: StreamKind) -> CompositeCurve:
    """Build the composite curve for one stream kind.

    Only streams of the requested :class:`StreamKind` contribute. Returns an
    empty curve when there are no matching streams. The curve starts at the
    lowest temperature with Q = 0 and ends at the highest temperature with
    the total duty.
    """
    selected = [s for s in streams if s.kind is kind]
    if not selected:
        return CompositeCurve(kind, (), ())

    temps = sorted({t for s in selected for t in (s.tin, s.tout)})

    # Heat released/absorbed between each pair of consecutive temperatures.
    steps: list[float] = []
    for t_low, t_high in zip(temps, temps[1:]):
        cp = sum(
            s.heat_capacity_flow
            for s in selected
            if min(s.tin, s.tout) <= t_low and max(s.tin, s.tout) >= t_high
        )
        steps.append(cp * (t_high - t_low))

    enthalpy = [0.0]
    for step in steps:
        enthalpy.append(enthalpy[-1] + step)

    return CompositeCurve(kind, tuple(temps), tuple(enthalpy))


@dataclass(frozen=True)
class UtilityTargets:
    """Composite curves plus the minimum utility amounts from the combined PTA.

    ``hot`` is the plain hot composite; ``cold`` is the plain cold composite
    shifted right by exactly the minimum cold utility. With delta_t_min = 0
    the two curves touch at the pinch; with delta_t_min > 0 the vertical gap
    at the pinch equals delta_t_min. No curve extensions are applied.
    """

    min_hot: float  # kW
    min_cold: float  # kW
    pinch_temperature: float | None  # shifted, C
    hot: CompositeCurve
    cold: CompositeCurve


def enthalpy_at(curve: CompositeCurve, temperature: float) -> float:
    """Enthalpy of *curve* at *temperature* (linear interpolation, clamped)."""
    temps, qs = curve.temperatures, curve.enthalpy
    if not temps:
        return 0.0
    if temperature <= temps[0]:
        return qs[0]
    if temperature >= temps[-1]:
        return qs[-1]
    for i in range(len(temps) - 1):
        if temps[i] <= temperature <= temps[i + 1]:
            span = temps[i + 1] - temps[i]
            if span <= 0:
                return qs[i]
            frac = (temperature - temps[i]) / span
            return qs[i] + frac * (qs[i + 1] - qs[i])
    return qs[-1]


def temperature_at(curve: CompositeCurve, enthalpy: float) -> float:
    """Temperature of *curve* at *enthalpy* (linear interpolation, clamped)."""
    temps, qs = curve.temperatures, curve.enthalpy
    if not temps:
        return 0.0
    if enthalpy <= qs[0]:
        return temps[0]
    if enthalpy >= qs[-1]:
        return temps[-1]
    for i in range(len(qs) - 1):
        if qs[i] <= enthalpy <= qs[i + 1]:
            span = qs[i + 1] - qs[i]
            if span <= 0:
                return temps[i]
            frac = (enthalpy - qs[i]) / span
            return temps[i] + frac * (temps[i + 1] - temps[i])
    return temps[-1]


def build_utility_targets(
    streams: list[Stream], delta_t_min: float = 0.0
) -> UtilityTargets:
    """Minimum utility amounts and the shifted cold composite curve.

    Runs the combined problem table to get QH,min, QC,min and the pinch,
    then shifts the plain cold composite right by exactly QC,min. The hot
    composite is returned unchanged (no extensions). Both curves keep their
    actual temperatures, so with delta_t_min = 0 they touch at the pinch,
    and with delta_t_min > 0 the smallest vertical gap equals delta_t_min.
    """
    from .pta import problem_table

    pt = problem_table(streams, "combined", delta_t_min)

    hot = build_composite(streams, StreamKind.HOT)
    cold = build_composite(streams, StreamKind.COLD)

    min_hot = pt.min_hot_utility or 0.0
    min_cold = pt.min_cold_utility or 0.0
    pinch = pt.pinch_temperatures[0] if pt.pinch_temperatures else None

    if cold.enthalpy:
        cold = CompositeCurve(
            cold.kind,
            cold.temperatures,
            tuple(q + min_cold for q in cold.enthalpy),
        )

    return UtilityTargets(min_hot, min_cold, pinch, hot, cold)


@dataclass(frozen=True)
class GrandCompositeCurve:
    """Heat cascade from the combined PTA plotted vs shifted temperature.

    ``heat_flow`` (kW) and ``temperatures`` (shifted C) are parallel tuples
    at the interval levels, ordered from the hottest level down. The curve
    starts at the minimum hot utility at the top, crosses zero at the pinch
    and ends at the minimum cold utility at the bottom.
    """

    heat_flow: tuple[float, ...]
    temperatures: tuple[float, ...]

    @property
    def min_hot(self) -> float:
        """Minimum hot utility in kW (heat flow at the top)."""
        return self.heat_flow[0] if self.heat_flow else 0.0

    @property
    def min_cold(self) -> float:
        """Minimum cold utility in kW (heat flow at the bottom)."""
        return self.heat_flow[-1] if self.heat_flow else 0.0

    @property
    def pinch_temperature(self) -> float | None:
        """Highest level where the cascade is zero (shifted C)."""
        if not self.heat_flow:
            return None
        tol = 1e-6 * max(1.0, max(abs(v) for v in self.heat_flow))
        for q, t in zip(self.heat_flow, self.temperatures):
            if abs(q) <= tol:
                return t
        return None


def build_gcc(streams: list[Stream], delta_t_min: float = 0.0) -> GrandCompositeCurve:
    """Grand composite curve from the combined problem table.

    Empty stream lists produce an empty curve.
    """
    from .pta import problem_table

    pt = problem_table(streams, "combined", delta_t_min)
    if not pt.levels:
        return GrandCompositeCurve((), ())
    return GrandCompositeCurve(pt.cascade, pt.levels)


@dataclass(frozen=True)
class TotalSiteProfileCurves:
    """Hot and cold composite curves in the Total Site Profile convention.

    Both curves start at energy 0: ``cold`` at its lowest temperature on the
    positive side of the energy axis, ``hot`` at its highest temperature on
    the negative side (enthalpy <= 0). They are the plain composites, with
    no utility shifts applied.
    """

    hot: CompositeCurve  # enthalpy <= 0, starts at 0 at the highest T
    cold: CompositeCurve  # enthalpy >= 0, starts at 0 at the lowest T


def build_tsp_curves(
    streams: list[Stream], delta_t_min: float = 0.0
) -> TotalSiteProfileCurves:
    """Total site profile curves: cold positive, hot negated.

    The cold composite is used as-is (starting at energy 0 at its lowest
    temperature). The hot composite is negated and mirrored so it also
    starts at energy 0, at its highest temperature, and accumulates
    negatively toward its lowest temperature.
    """
    hot = build_composite(streams, StreamKind.HOT)
    cold = build_composite(streams, StreamKind.COLD)
    if hot.enthalpy:
        total = hot.total_enthalpy
        hot = CompositeCurve(
            hot.kind,
            hot.temperatures,
            tuple(q - total for q in hot.enthalpy),
        )
    return TotalSiteProfileCurves(hot, cold)


def utility_staircase(
    hot_curve: CompositeCurve, utility_temperatures: list[float]
) -> list[tuple[float, float]]:
    """Staircase tracing the hot composite at the utility temperatures.

    Starts at the hot curve's most negative energy at the lowest utility
    temperature, then steps: horizontally at each utility temperature to the
    energy where the hot composite reaches the next utility temperature,
    then vertically up to it. Utility temperatures outside the hot
    composite's range are clamped to its ends. Returns (energy, temperature)
    points; zero-length horizontal steps are dropped.
    """
    temps = sorted(utility_temperatures)
    if not temps or not hot_curve.enthalpy:
        return []
    t_min = hot_curve.temperatures[0]
    t_max = hot_curve.temperatures[-1]
    points: list[tuple[float, float]] = [(hot_curve.enthalpy[0], temps[0])]
    for i in range(len(temps) - 1):
        t_next = temps[i + 1]
        if t_next <= t_min:
            x_next = hot_curve.enthalpy[0]
        elif t_next >= t_max:
            x_next = hot_curve.enthalpy[-1]
        else:
            x_next = enthalpy_at(hot_curve, t_next)
        if not math.isclose(x_next, points[-1][0]):
            points.append((x_next, temps[i]))  # horizontal step
        points.append((x_next, t_next))  # vertical step
    return points


def cold_utility_staircase(
    cold_curve: CompositeCurve, utility_temperatures: list[float]
) -> list[tuple[float, float]]:
    """Staircase above the cold composite at the utility temperatures.

    Starts at energy 0 at the lowest utility temperature, then steps:
    vertically up at the current energy to the next utility temperature,
    then horizontally to the right until it touches the cold composite at
    that temperature. Because the cold composite rises in temperature with
    energy, each horizontal step sits at or above the curve. Utility
    temperatures outside the cold composite's range are clamped to its ends.
    Returns (energy, temperature) points; zero-length horizontal steps are
    dropped.
    """
    temps = sorted(utility_temperatures)
    if not temps or not cold_curve.enthalpy:
        return []
    t_min = cold_curve.temperatures[0]
    t_max = cold_curve.temperatures[-1]
    points: list[tuple[float, float]] = [(0.0, temps[0])]
    for i in range(len(temps) - 1):
        t_next = temps[i + 1]
        x_cur = points[-1][0]
        points.append((x_cur, t_next))  # vertical step up
        if t_next <= t_min:
            x_next = cold_curve.enthalpy[0]
        elif t_next >= t_max:
            x_next = cold_curve.enthalpy[-1]
        else:
            x_next = enthalpy_at(cold_curve, t_next)
        if not math.isclose(x_next, x_cur):
            points.append((x_next, t_next))  # horizontal step to the curve
    return points


def _vertical_segments(
    steps: list[tuple[float, float]]
) -> dict[tuple[float, float], float]:
    """Map (t_low, t_high) -> x for the vertical segments of a staircase."""
    segments: dict[tuple[float, float], float] = {}
    for (x1, t1), (x2, t2) in zip(steps, steps[1:]):
        if math.isclose(x1, x2) and not math.isclose(t1, t2):
            lo, hi = min(t1, t2), max(t1, t2)
            segments[(lo, hi)] = x1
    return segments


def tsp_shift_amount(
    hot_steps: list[tuple[float, float]],
    cold_steps: list[tuple[float, float]],
) -> float | None:
    """Shortest horizontal distance between the two staircases' verticals.

    For each temperature interval between consecutive utility temperatures
    the hot staircase has a vertical segment and the cold staircase has one
    (drawn at the energies where the respective composite reaches the
    interval's temperatures). The gap is the energy difference between the
    two verticals of the same interval. Returns the minimum gap -- the
    amount the cold utility staircase must shift left so the closest
    verticals touch -- or None when there are no common verticals.
    """
    hot_segs = _vertical_segments(hot_steps)
    cold_segs = _vertical_segments(cold_steps)
    common = set(hot_segs) & set(cold_segs)
    if not common:
        return None
    return min(cold_segs[span] - hot_segs[span] for span in common)


@dataclass(frozen=True)
class SugccSegment:
    """Net utility heat between two consecutive utility temperatures.

    This is the horizontal distance between the cold and hot staircase
    verticals of the interval once the cold staircase has been shifted left
    by the TSP shift, i.e. the enclosed area width at that temperature level.
    """

    t_low: float  # C
    t_high: float  # C
    heat: float  # kW, >= 0


def build_sugcc(
    hot_steps: list[tuple[float, float]],
    cold_steps: list[tuple[float, float]],
    shift: float,
) -> list[SugccSegment]:
    """Net utility heat at each temperature interval after the TSP shift.

    For every temperature interval between consecutive utility temperatures
    the heat is the energy distance between the cold and hot staircase
    verticals once the cold staircase moves left by *shift*, so the closest
    interval has zero heat. Intervals are ordered by temperature.
    """
    hot_segs = _vertical_segments(hot_steps)
    cold_segs = _vertical_segments(cold_steps)
    spans = sorted(set(hot_segs) & set(cold_segs))
    return [
        SugccSegment(
            t_low,
            t_high,
            max(0.0, cold_segs[(t_low, t_high)] - shift - hot_segs[(t_low, t_high)]),
        )
        for t_low, t_high in spans
    ]


CARNOT_FACTOR = 0.00133  # kW of power per (C of delta T * kW of heat)


@dataclass(frozen=True)
class CogenerationRow:
    """One expansion zone of the cogeneration targets table."""

    zone: str  # e.g. "g/f" (higher utility / lower utility)
    t_low: float  # C
    t_high: float  # C
    delta_t: float  # C
    heat: float  # Q, kW
    power: float  # W, kW


def build_cogeneration_table(
    segments: list[SugccSegment],
    utility_streams: list[UtilityStream],
) -> list[CogenerationRow]:
    """Cogeneration targets for each SUGCC expansion zone.

    Only intervals with positive net heat form expansion zones. Each zone is
    named after its bounding utilities (higher temperature / lower
    temperature, e.g. "g/f") and the cogeneration target is the Carnot
    factor times the temperature span times the net heat::

        W = 0.00133 * delta T * Q
    """
    names = {u.temperature: u.name for u in utility_streams}
    rows: list[CogenerationRow] = []
    for seg in segments:
        if seg.heat <= 1e-9:
            continue
        delta_t = seg.t_high - seg.t_low
        name_high = names.get(seg.t_high, f"{seg.t_high:g}")
        name_low = names.get(seg.t_low, f"{seg.t_low:g}")
        rows.append(
            CogenerationRow(
                zone=f"{name_high}/{name_low}",
                t_low=seg.t_low,
                t_high=seg.t_high,
                delta_t=delta_t,
                heat=seg.heat,
                power=CARNOT_FACTOR * delta_t * seg.heat,
            )
        )
    return rows
