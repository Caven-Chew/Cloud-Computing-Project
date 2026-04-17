"""Metrics: R₀, final size, time-to-half, containment efficacy."""
from __future__ import annotations
from statistics import mean, stdev
from orchestrator import Telemetry

def r0(tel: Telemetry) -> float:
    """R₀ = secondary infections caused by patient zero.
    This is the correct epidemiological definition: number of infections
    produced by one infector in a fully susceptible population."""
    return float(tel.secondary_infections.get(0, 0))

def final_size(tel: Telemetry, n_agents: int) -> float:
    return len(tel.infection_times) / n_agents

def time_to_half(tel: Telemetry, n_agents: int) -> int | None:
    for t, c in enumerate(tel.infected_per_tick, start=1):
        if c >= n_agents / 2:
            return t
    return None

def containment_efficacy(baseline: Telemetry, defended: Telemetry, n: int) -> float:
    b = final_size(baseline, n)
    d = final_size(defended, n)
    return 0.0 if b == 0 else 1 - d / b

# ── Multi-seed helpers ──
def avg_and_std(values: list[float]) -> tuple[float, float]:
    m = mean(values)
    s = stdev(values) if len(values) > 1 else 0.0
    return m, s
