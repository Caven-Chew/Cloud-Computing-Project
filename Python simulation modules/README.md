# WormLab — Prompt Worm Propagation Testbed

Tick-based simulator for studying prompt-worm propagation across
LLM-agent networks, with a pluggable sidecar defense (WormGuard).
Applies epidemiological models (R₀, herd immunity) to AI agent security.

## Files
| File | Purpose |
|------|---------|
| `llm.py` | MockLLM (3-level signal detection) + ClaudeLLM wrapper |
| `agent.py` | Agent = LLM + persistent memory + mailbox + trifecta exposure |
| `worm.py` | 3 worm variants: naive (tags), obfuscated (clear NL), polymorphic (subtle NL) |
| `topology.py` | Star, ring, mesh, scale-free (Barabási-Albert) contact graphs |
| `wormguard.py` | 3-layer sidecar: pattern detector + semantic judge + rate limiter |
| `orchestrator.py` | Tick loop, patient-zero injection, centralized/decentralized deployment |
| `analyzer.py` | R₀, final size, containment efficacy, multi-seed stats |
| `main.py` | Full experiment suite: baseline sweep + deployment sweep + trifecta ablation |
| `validate_real_llm.py` | Validation against Claude Haiku / GPT-4.1-mini |

## Quick Start
```bash
pip install networkx matplotlib numpy
python main.py              # full run (n=25, seeds=8, ~2 min)
python main.py --quick      # fast smoke test (n=15, seeds=4, ~30s)
```

## Experiments
1. **Baseline sweep**: topology × worm variant × defense → R₀, final size, containment efficacy
2. **Deployment sweep**: centralized (API gateway) vs decentralized (per-agent sidecar), varying ρ
3. **Trifecta ablation**: selectively disable data_access / untrusted_input / external_comms

## Real LLM Validation
```bash
pip install anthropic openai
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."
python validate_real_llm.py --claude --openai --seeds 3
```

## Key Findings
- **Pattern detection** catches naive worms (explicit tags) but is completely blind to
  obfuscated and polymorphic variants (η=0.00).
- **Semantic judge** catches obfuscated worms but only partially catches polymorphic
  (~55% detection on subtle templates). Topology-dependent: more effective on hub-based
  networks (scale-free) than dense networks (mesh).
- **Defense-in-depth** (pattern + judge + rate limiter) achieves η≈0.96 across all variants.
- **Centralized defense collapses** as agents go local: η drops from 0.96 → 0.00 as ρ→1.
  Decentralized (per-agent sidecar) maintains η=0.96 regardless of ρ.
- **Trifecta ablation**: removing `untrusted_input` or `external_comms` kills propagation
  entirely. Removing `data_access` has zero effect on propagation.

## Design Notes
- Tick-based (not async): ensures reproducibility and clean R₀ measurement.
- Patient zero's initial delivery is deterministic (attacker-controlled injection).
- R₀ = secondary infections from patient zero (strict epidemiological definition).
- MockLLM obedience = 0.92 (base), reduced to 0.78 for subtle polymorphic signals.
- WormGuard judge: 95% accuracy on clear signals, 55% on subtle, 8% FP rate.
