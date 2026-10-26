import os
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
DECISION_START = date(2026, 1, 1)
DECISION_END = date(2026, 1, 31)
ELEXON_BASE = "https://data.elexon.co.uk/bmrs/api/v1"
ALIGNMENT = (
    "Hourly WINDFOR treated as representative of [start, start + 1 hour); actual MW is the "
    "mean of both FUELHH half-hours. Pilot alignment assumption; no half-hour forecast imputation."
)
SCOPE = "Great Britain system-operator-visible wind; not complete UK wind generation."


@dataclass(frozen=True)
class Settings:
    snapshot_path: Path = field(
        default_factory=lambda: Path(
            os.getenv(
                "WINDSCOPE_SNAPSHOT_PATH", str(BACKEND_ROOT / "data/processed/snapshot.json.gz")
            )
        )
    )
    cors_origins: tuple[str, ...] = field(
        default_factory=lambda: tuple(
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://localhost:8080"
            ).split(",")
            if origin.strip()
        )
    )
