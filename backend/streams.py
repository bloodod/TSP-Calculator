"""Stream input model for the Total Site Profile (TSP) program.

A stream is defined by its inlet/outlet temperatures (in C) and exactly one
of the two duty inputs:

* ``energy`` -- total energy in kW, or
* ``cp``     -- heat capacity flow rate in kW/C.

The missing quantity is derived from the absolute temperature difference::

    CP = Q / |Tout - Tin|    (when Q is given)
    Q  = CP * |Tout - Tin|   (when CP is given)

``energy`` and ``cp`` always hold the values the user entered (the other one
is ``None``). Use the :attr:`Stream.total_energy` and
:attr:`Stream.heat_capacity_flow` properties for the resolved values so the
model stays consistent even if temperatures are edited after construction.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum


class StreamValidationError(ValueError):
    """Raised when a stream's inputs are missing or inconsistent."""


class StreamKind(Enum):
    """Direction of heat exchange implied by the stream temperatures."""

    HOT = "hot"    # cools down between inlet and outlet (releases heat)
    COLD = "cold"  # heats up between inlet and outlet (requires heat)


@dataclass
class Stream:
    """A process stream with temperatures and a duty or heat capacity.

    Exactly one of *energy* (kW) and *cp* (kW/C) must be provided; the other
    is derived from the absolute temperature difference. Duties are entered
    as magnitudes (>= 0); whether the stream releases or absorbs heat follows
    from the temperature direction (see :attr:`kind`).
    """

    tin: float  # inlet temperature, C
    tout: float  # outlet temperature, C
    name: str = ""  # optional stream label
    energy: float | None = None  # total energy, kW (optional input)
    cp: float | None = None  # heat capacity flow rate, kW/C (optional input)

    def __post_init__(self) -> None:
        _require_finite("inlet temperature", self.tin)
        _require_finite("outlet temperature", self.tout)
        if math.isclose(self.tin, self.tout):
            raise StreamValidationError(
                "inlet and outlet temperatures must differ, "
                f"got {self.tin:g} and {self.tout:g} C"
            )

        has_energy = self.energy is not None
        has_cp = self.cp is not None
        if has_energy == has_cp:
            raise StreamValidationError(
                "provide exactly one of 'energy' (kW) or 'cp' (kW/C)"
            )
        if has_energy:
            _require_finite("energy", self.energy)
            _require_non_negative("energy", self.energy)
        if has_cp:
            _require_finite("cp", self.cp)
            _require_non_negative("cp", self.cp)

    # -- resolved values -------------------------------------------------

    @property
    def temperature_difference(self) -> float:
        """Absolute |Tout - Tin| in C."""
        return abs(self.tout - self.tin)

    @property
    def heat_capacity_flow(self) -> float:
        """Heat capacity flow rate in kW/C (derived when only Q is given)."""
        if self.cp is not None:
            return self.cp
        return self.energy / self.temperature_difference

    @property
    def total_energy(self) -> float:
        """Total duty in kW (derived when only CP is given)."""
        if self.energy is not None:
            return self.energy
        return self.cp * self.temperature_difference

    @property
    def kind(self) -> StreamKind:
        """Hot (releases heat) when cooling down, cold when heating up."""
        return StreamKind.COLD if self.tout > self.tin else StreamKind.HOT


@dataclass
class UtilityStream:
    """A utility stream (hot or cold utility) at a fixed temperature."""

    name: str
    temperature: float  # C

    def __post_init__(self) -> None:
        _require_finite("utility temperature", self.temperature)


def _require_finite(label: str, value: float) -> None:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
    ):
        raise StreamValidationError(
            f"{label} must be a finite number, got {value!r}"
        )


def _require_non_negative(label: str, value: float) -> None:
    if value < 0:
        raise StreamValidationError(
            f"{label} must be >= 0, got {value:g}"
        )
