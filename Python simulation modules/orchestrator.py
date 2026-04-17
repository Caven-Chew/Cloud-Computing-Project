"""Orchestrator: tick loop, patient-zero injection, telemetry.
Supports centralized vs decentralized defense deployment."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable
import random
from agent import Agent, Trifecta, _is_worm_bearing
from llm import LLM

@dataclass
class Telemetry:
    infected_per_tick: list[int] = field(default_factory=list)
    infection_times: dict[int, int] = field(default_factory=dict)
    secondary_infections: dict[int, int] = field(default_factory=dict)
    blocked_inbound: int = 0
    blocked_outbound: int = 0

class Orchestrator:
    def __init__(self, contacts: dict[int, list[int]], llm: LLM,
                 sidecar=None, exposure_fn: Callable[[int], Trifecta] = None,
                 seed: int = 0, deployment: str = "decentralized", rho: float = 0.0):
        self.contacts = contacts
        self.sidecar = sidecar
        self.deployment = deployment
        self.rho = rho
        self.rng = random.Random(seed)
        ef = exposure_fn or (lambda aid: Trifecta())
        self.agents: dict[int, Agent] = {
            aid: Agent(aid=aid, llm=llm, trifecta=ef(aid)) for aid in contacts
        }
        self.tel = Telemetry()
        self._infector_of: dict[int, int] = {}
        n = len(contacts)
        n_bypass = int(n * rho)
        all_aids = list(contacts.keys())
        self.rng.shuffle(all_aids)
        self._bypass_agents = set(all_aids[:n_bypass]) if deployment == "centralized" else set()

    def _get_sidecar_for(self, aid: int):
        if self.sidecar is None:
            return None
        if self.deployment == "centralized":
            return None if aid in self._bypass_agents else self.sidecar
        return self.sidecar

    def inject(self, patient_zero: int, payload: str):
        """Patient zero is attacker-controlled — always forwards on tick 1."""
        agent = self.agents[patient_zero]
        agent.infected_since = 0
        agent.memory.append("[t0] INJECTED")
        agent._pending_forward = payload  # deterministic: always forwards
        self.tel.infection_times[patient_zero] = 0
        # Pre-schedule deliveries for tick 1
        self._inject_deliveries = [(patient_zero, c, payload)
                                   for c in self.contacts[patient_zero]]

    def run(self, ticks: int) -> Telemetry:
        for t in range(1, ticks + 1):
            if self.sidecar:
                self.sidecar.reset_tick()
            deliveries = []
            # Tick 1: include patient zero's pre-scheduled deliveries
            if t == 1 and hasattr(self, '_inject_deliveries'):
                deliveries.extend(self._inject_deliveries)
                del self._inject_deliveries
            for aid, agent in self.agents.items():
                had_inbound = bool(agent.mailbox)
                sc = self._get_sidecar_for(aid)
                agent.tick(t, sc)
                fwd = agent.pending_forward()
                if fwd and had_inbound:
                    for contact in self.contacts[aid]:
                        deliveries.append((aid, contact, fwd))
            for src, dst, msg in deliveries:
                src_sc = self._get_sidecar_for(src)
                if src_sc and src_sc.block_outbound(self.agents[src], msg):
                    self.tel.blocked_outbound += 1
                    continue
                self.agents[dst].mailbox.append(msg)
                if _is_worm_bearing(msg) and dst not in self.tel.infection_times:
                    if dst not in self._infector_of:  # keep first infector only
                        self._infector_of[dst] = src
            for aid, agent in self.agents.items():
                if agent.infected_since is not None and aid not in self.tel.infection_times:
                    self.tel.infection_times[aid] = t
                    parent = self._infector_of.get(aid)
                    if parent is not None:
                        self.tel.secondary_infections[parent] = \
                            self.tel.secondary_infections.get(parent, 0) + 1
            self.tel.infected_per_tick.append(len(self.tel.infection_times))
        return self.tel
