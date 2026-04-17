# WormLab — Prompt Worm Propagation Testbed

> Tick-based epidemic simulator for studying prompt-worm propagation across autonomous LLM agent networks, with a pluggable sidecar defence (WormGuard). Applies classical epidemiological models (R₀, herd immunity) to AI agent security.
>
> **SC4052 Cloud Computing — Topic 4: Cloud Security II**  

---

## Quick Start

```bash
git clone https://github.com/Caven-Chew/Cloud-Computing-Project
cd Cloud-Computing-Project
pip install -r requirements.txt

python main.py              # full experiment suite (~2 min)
python main.py --quick      # fast smoke test (~30s)
```

---

## Simulation UI

WormLab ships with two interfaces for interactive exploration.

### Streamlit Dashboard (recommended)

A browser-based GUI that lets you configure and run simulations without touching code.

```bash
pip install streamlit
streamlit run app.py
```

Open `http://localhost:8501` in your browser. The sidebar lets you:

- Choose **network topology** — star, ring, scale-free, or mesh
- Set **number of agents** (6–50) and **simulation ticks**
- Select **worm variant** — naive, obfuscated, or polymorphic
- Toggle individual **defence layers** — pattern detector, semantic judge, rate limiter
- Adjust **number of seeds** for averaged results

Results are displayed as live infection-curve charts, R₀ readouts, and a containment efficacy summary.

### React Dashboard

A standalone React visualisation component with real-time infection spread animation, R₀ charts, and defence heatmaps.

```bash
# Requires Node.js
# Copy wormlab-ui.jsx into your React project and import it
import WormLabDashboard from './wormlab-ui';
```

---

## Command-Line Experiments

Run the full experiment suite from the terminal:

```bash
# Full sweep (all topologies × worm variants × defence configs, 8 seeds)
python main.py

# Quick smoke test (smaller network, fewer seeds)
python main.py --quick

# Custom parameters
python main.py --n 30 --ticks 20 --seeds 8
```

Output figures are saved to `results/`.

### Experiments included

| # | Experiment | What it measures |
|---|-----------|-----------------|
| 1 | **Baseline sweep** | R₀ and final infection size across topology × worm variant × defence |
| 2 | **Deployment sweep** | Centralised (API gateway) vs decentralised (per-agent sidecar), varying bypass fraction ρ |
| 3 | **Trifecta ablation** | Effect of removing each vulnerability leg — data access, untrusted input, external comms |

---

## Real LLM Validation

Test against production LLMs (Claude Haiku, GPT-4.1-mini):

```bash
# Copy .env.example to .env and add your API keys
cp .env.example .env

pip install anthropic openai python-dotenv
python validate_real_llm.py --claude --openai --seeds 3
```

Pre-computed validation results are included in `results/` to avoid API costs during review.

---

## Module Reference

| File | Purpose |
|------|---------|
| `main.py` | Full experiment runner — entry point |
| `agent.py` | Agent dataclass: MockLLM decision-making, trifecta capability flags, mailbox |
| `llm.py` | MockLLM (3-level signal detection) + ClaudeLLM / OpenAI API wrappers |
| `worm.py` | Three worm variants: naive (explicit tags), obfuscated (business language), polymorphic (social engineering) |
| `topology.py` | Network graph builders: star, ring, mesh, Barabási-Albert scale-free |
| `wormguard.py` | 3-layer WormGuard sidecar: pattern detector, semantic judge, rate limiter |
| `orchestrator.py` | Tick loop, patient-zero injection, centralised / decentralised deployment models |
| `analyzer.py` | R₀, final size, containment efficacy, confidence intervals across seeds |
| `validate_real_llm.py` | Production LLM validation (Claude Haiku, GPT-4.1-mini) |
| `app.py` | Streamlit interactive dashboard |

---

## Key Findings

| Finding | Result |
|---------|--------|
| R₀ by topology | Ring 1.8 · Scale-free 11 · Star/Mesh 29 |
| Pattern detection | η = 0.96 vs naive · η = 0.00 vs obfuscated/polymorphic |
| Full defence-in-depth | η = 0.93–0.96 across all worm variants |
| Centralised defence | Collapses to η = 0.00 as ρ → 1.0 · critical threshold ρ ≈ 0.09 |
| Decentralised sidecar | η = 0.93 regardless of ρ |
| Trifecta ablation | Removing `untrusted_input` or `external_comms` kills propagation · removing `data_access` has zero effect |
| Real LLM validation | Claude Haiku: 100% obedience · MockLLM is a conservative lower bound |

---

## Design Notes

- **Tick-based (not async)** — ensures reproducibility and clean R₀ measurement.
- **Deterministic patient zero** — initial injection is always agent 0, always forwards, modelling an attacker-controlled seed.
- **R₀ definition** — secondary infections caused by patient zero (strict epidemiological definition, not network average).
- **MockLLM** — obedience = 0.92 base, reduced to 0.78 for subtle polymorphic signals.
- **WormGuard judge** — 95% accuracy on clear signals (level 2), 55% on subtle (level 3), 8% false positive rate.
- **Single outbound filter point** — `block_outbound` is called only in `Orchestrator.run()`, not inside `Agent.tick()`, to prevent double-counting rate-limit increments.

---

## Requirements

```
networkx
matplotlib
numpy
anthropic
openai
python-dotenv
streamlit
```

Install all at once:

```bash
pip install -r requirements.txt
```