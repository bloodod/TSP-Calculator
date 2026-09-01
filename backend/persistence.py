"""Save and load the TSP problem data.

Only the streams and the utility streams are persisted for now.
"""

from __future__ import annotations

import json

from .project import TotalSiteProfile
from .streams import Stream, UtilityStream


def save_profile(tsp: TotalSiteProfile, path: str) -> None:
    """Write *tsp*'s streams and utility streams to *path* as JSON."""
    data = {
        "streams": [
            {
                "name": s.name,
                "tin": s.tin,
                "tout": s.tout,
                "energy": s.energy,
                "cp": s.cp,
            }
            for s in tsp.streams
        ],
        "utility_streams": [
            {"name": u.name, "temperature": u.temperature}
            for u in tsp.utility_streams
        ],
    }
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_profile(path: str) -> TotalSiteProfile:
    """Load streams and utility streams from a JSON file.

    Raises OSError for unreadable files and ValueError for malformed or
    invalid content.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid problem file: {exc}") from exc

    tsp = TotalSiteProfile()
    try:
        for entry in data.get("streams", []):
            tsp.add_stream(
                Stream(
                    name=entry.get("name", ""),
                    tin=entry["tin"],
                    tout=entry["tout"],
                    energy=entry.get("energy"),
                    cp=entry.get("cp"),
                )
            )
        for entry in data.get("utility_streams", []):
            tsp.add_utility_stream(
                UtilityStream(
                    name=entry.get("name", ""),
                    temperature=entry["temperature"],
                )
            )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid problem file: {exc}") from exc
    return tsp
