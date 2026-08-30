"""Tracks YouTube Data API v3 quota units consumed during a single run.

A safety valve, not a rate limiter — if a run's cumulative cost exceeds
max_units_per_run (config/settings.yaml), further channel processing stops
and the run exits with a warning, rather than silently burning through the
10,000-unit/day free quota (e.g. if channels.yaml balloons unexpectedly, or a
bug causes runaway pagination).
"""


class QuotaExceededError(Exception):
    pass


class QuotaTracker:
    def __init__(self, max_units_per_run: int):
        self.max_units_per_run = max_units_per_run
        self.units_used = 0
        self._log: list[tuple[str, int]] = []

    def charge(self, operation: str, units: int) -> None:
        self.units_used += units
        self._log.append((operation, units))
        if self.units_used > self.max_units_per_run:
            raise QuotaExceededError(
                f"Quota budget exceeded: {self.units_used} units used "
                f"(max_units_per_run={self.max_units_per_run}). "
                f"Stopping to avoid burning through the daily 10,000-unit cap."
            )

    def summary(self) -> str:
        by_op: dict[str, int] = {}
        for op, units in self._log:
            by_op[op] = by_op.get(op, 0) + units
        lines = [f"Total quota used: {self.units_used} units"]
        for op, units in sorted(by_op.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {op}: {units} units")
        return "\n".join(lines)
