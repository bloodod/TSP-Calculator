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

from dataclasses import dataclass

from .streams import Stream, StreamKind


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
