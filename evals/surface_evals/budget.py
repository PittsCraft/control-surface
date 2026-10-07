"""What a campaign spends, and where it stops.

Two measures, both read from the streams of the sessions. The cost in USD at list price, which
a stream sums per session. And, on a subscription, the weekly use the stream reports as a gauge
from 0 to 1: the ledger adds up how far it rose while sessions ran. That rise counts everything
the account did meanwhile, not the campaign alone, and the gauge moves by whole points: it is a
ceiling to stop at, on the safe side, not a bill.

Runs played together note their sessions as each one ends, so a reading may be older than the
last one counted. Within a week the gauge only rises: a reading is counted for what it stands
above the highest of its week, and a lower one is an older one, never a fall. Only a later week,
which a stream dates by when it ends, starts the count again from where the gauge then stands.
"""

import json
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from surface_evals.sessions import Gauge, SessionLog

LEDGER = "ledger.json"


@dataclass(slots=True)
class Ledger:
    """What the sessions of an output folder cost so far, kept in that folder."""

    path: Path
    usd: float = 0.0
    points: float = 0.0  # the rise of the weekly gauge while sessions ran, in points of 1%
    sessions: int = 0
    max_usd: float | None = None
    max_points: float | None = None
    _paid: dict[str, float] = field(default_factory=dict[str, float])  # the cost seen, per session
    _gauge: float | None = None  # the highest reading of the week, of this launch only
    _week: float | None = None  # when that week ends, as the last reading dated it
    _lock: threading.Lock = field(default_factory=threading.Lock)  # runs may be played together

    @classmethod
    def load(cls, out: Path, *, max_usd: float | None, max_points: float | None) -> "Ledger":
        path = out / LEDGER
        ledger = cls(path=path, max_usd=max_usd, max_points=max_points)
        if path.is_file():
            kept = cast("dict[str, object]", json.loads(path.read_text(encoding="utf-8")))
            ledger.usd = float(cast("float", kept["usd"]))
            ledger.points = float(cast("float", kept["points"]))
            ledger.sessions = int(cast("int", kept["sessions"]))
        return ledger

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        kept = {
            "usd": round(self.usd, 4),
            "points": round(self.points, 2),
            "sessions": self.sessions,
        }
        self.path.write_text(json.dumps(kept, indent=2) + "\n", encoding="utf-8")

    def note(self, log: SessionLog) -> None:
        """Add what a session cost. A resumed session reports its total: only the rise counts."""
        key = log.session_id or str(log.path)
        with self._lock:
            self.usd += max(0.0, log.cost - self._paid.get(key, 0.0))
            self._paid[key] = max(log.cost, self._paid.get(key, 0.0))
            self.sessions += 1
            for gauge in log.gauges:
                self._read(gauge)
            self.save()

    def _read(self, gauge: Gauge) -> None:
        """Count how far a reading stands above the highest of its week."""
        week, last = gauge.week, self._week
        if week is not None and last is not None and week < last:
            return  # a reading of the week before, noted late
        turned = week is not None and last is not None and week > last
        if self._gauge is None or (turned and gauge.used < self._gauge):
            # The first reading of a launch, or of a week that turned: the count goes on from it.
            self._gauge = gauge.used
        elif gauge.used > self._gauge:
            self.points = round(self.points + (gauge.used - self._gauge) * 100, 4)
            self._gauge = gauge.used
        if week is not None:
            self._week = week

    def exhausted(self) -> str | None:
        """Say why no further session may start, or None while one may."""
        if self.max_usd is not None and self.usd >= self.max_usd:
            return f"the ceiling of {self.max_usd:g} USD is reached ({self.usd:.2f} spent)"
        if self.max_points is not None and self.points >= self.max_points:
            return (
                f"the weekly gauge rose by {self.points:g} points while sessions ran,"
                f" the ceiling is {self.max_points:g}"
            )
        return None
