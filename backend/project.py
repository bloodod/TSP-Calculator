"""Problem-level model for the Total Site Profile (TSP) program.

Holds the stream list and the minimum temperature approach (Delta T min,
default 0 C) that will later be used when the hot and cold site profiles are
shifted to find the utility targets.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .streams import Stream, UtilityStream


class ProjectValidationError(ValueError):
    """Raised when project-level inputs are invalid."""


@dataclass
class TotalSiteProfile:
    """A TSP problem: the stream list plus Delta T min (default 0 C)."""

    delta_t_min: float = 0.0
    streams: list[Stream] = field(default_factory=list)
    utility_streams: list[UtilityStream] = field(default_factory=list)

    def __post_init__(self) -> None:
        if (
            isinstance(self.delta_t_min, bool)
            or not isinstance(self.delta_t_min, (int, float))
            or not math.isfinite(self.delta_t_min)
        ):
            raise ProjectValidationError(
                f"delta T min must be a finite number, got {self.delta_t_min!r}"
            )
        if self.delta_t_min < 0:
            raise ProjectValidationError(
                f"delta T min must be >= 0, got {self.delta_t_min:g}"
            )

    # -- stream list helpers --------------------------------------------

    def add_stream(self, stream: Stream) -> Stream:
        """Append *stream* to the profile and return it."""
        self.streams.append(stream)
        return stream

    def remove_stream(self, stream: Stream) -> None:
        """Remove *stream* from the profile (raises if not present)."""
        self.streams.remove(stream)

    def clear_streams(self) -> None:
        """Remove all streams."""
        self.streams.clear()

    # -- utility stream list helpers ------------------------------------

    def add_utility_stream(self, utility: UtilityStream) -> UtilityStream:
        """Append *utility* to the profile and return it."""
        self.utility_streams.append(utility)
        return utility

    def remove_utility_stream(self, utility: UtilityStream) -> None:
        """Remove *utility* from the profile (raises if not present)."""
        self.utility_streams.remove(utility)

    def clear_utility_streams(self) -> None:
        """Remove all utility streams."""
        self.utility_streams.clear()

    def __len__(self) -> int:
        return len(self.streams)
