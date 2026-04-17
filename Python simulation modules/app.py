"""WormLab UI — Simple Streamlit wrapper around existing code.

Run:  streamlit run app.py
"""
import streamlit as st
import random
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Import existing code directly
from llm import MockLLM
from topology import BUILDERS
from worm import VARIANTS
from wormguard import WormGuard
from orchestrator import Orchestrator
from analyzer import r0, final_size, containment_efficacy

# ─── Page setup ──────────────────────────────────────────────────────

st.set_page_config(page_title="WormLab", page_icon="🐛", layout="wide")
st.title("🐛 WormLab — Prompt Worm Propagation Simulator")

# ─── Sidebar controls ───────────────────────────────────────────────

st.sidebar.header("Simulation Settings")

topology = st.sidebar.selectbox("Topology", ["star", "ring", "scale_free", "mesh"])
n_agents = st.sidebar.slider("Agents", 6, 50, 20)
variant = st.sidebar.selectbox("Worm Variant", ["naive", "obfuscated", "polymorphic"])
ticks = st.sidebar.slider("Ticks", 5, 30, 20)
num_seeds = st.sidebar.slider("Seeds (for averaging)", 1, 10, 5)

st.sidebar.header("Defense Layers")
use_pattern = st.sidebar.checkbox("Pattern Detector")
use_judge = st.sidebar.checkbox("Semantic Judge")
use_policy = st.sidebar.checkbox("Rate Limiter")

run_btn = st.sidebar.button("▶ Run Simulation", type="primary", use_container_width=True)

# ─── Run simulation using existing code ──────────────────────────────

def run_one(topo, n, var, def_cfg, seed, ticks):
    """Exact same logic as main.py's run_one."""
    contacts = BUILDERS[topo](n, seed) if topo == "scale_free" else BUILDERS[topo](n)
    llm = MockLLM(obedience=0.92, seed=seed)
    rng = random.Random(seed)
    sidecar = WormGuard(**def_cfg) if def_cfg else None
    if sidecar:
        sidecar._rng = random.Random(seed + 1000)
    orch = Orchestrator(contacts, llm, sidecar=sidecar, seed=seed)
    payload = VARIANTS[var](rng, tick=0)
    orch.inject(patient_zero=0, payload=payload)
    tel = orch.run(ticks)
    return tel, payload, contacts

if run_btn:
    # Build defense config
    def_cfg = None
    if use_pattern or use_judge or use_policy:
        def_cfg = dict(policy=use_policy, pattern=use_pattern, judge=use_judge)

    # Run with defense
    with st.spinner("Running simulation..."):
        defended_tels = []
        baseline_tels = []
        sample_payload = None
        sample_contacts = None

        for s in range(num_seeds):
            tel, payload, contacts = run_one(topology, n_agents, variant, def_cfg, s, ticks)
            defended_tels.append(tel)
            sample_payload = payload
            sample_contacts = contacts

            # Also run baseline (no defense) for comparison
            tel_base, _, _ = run_one(topology, n_agents, variant, None, s, ticks)
            baseline_tels.append(tel_base)

    # ─── Metrics ─────────────────────────────────────────────────────

    avg_r0 = np.mean([r0(t) for t in defended_tels])
    avg_fs = np.mean([final_size(t, n_agents) for t in defended_tels])
    avg_r0_base = np.mean([r0(t) for t in baseline_tels])
    avg_fs_base = np.mean([final_size(t, n_agents) for t in baseline_tels])
    avg_eff = np.mean([containment_efficacy(b, d, n_agents)
                       for b, d in zip(baseline_tels, defended_tels)])

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("R₀", f"{avg_r0:.1f}", delta=f"{avg_r0 - avg_r0_base:.1f} vs baseline",
                delta_color="inverse")
    col2.metric("Final Infected", f"{avg_fs*100:.0f}%",
                delta=f"{(avg_fs - avg_fs_base)*100:.0f}% vs baseline", delta_color="inverse")
    col3.metric("Containment η", f"{avg_eff:.2f}")
    col4.metric("Baseline Infected", f"{avg_fs_base*100:.0f}%")

    # ─── Payload preview ────────────────────────────────────────────

    with st.expander("📨 Worm Payload"):
        st.code(sample_payload, language=None)

    # ─── Plots ───────────────────────────────────────────────────────

    left, right = st.columns(2)

    # Fig 1: Infection curve
    with left:
        st.subheader("Infection Curve")
        fig1, ax1 = plt.subplots(figsize=(6, 4))

        # Baseline curves
        base_curves = np.array([t.infected_per_tick for t in baseline_tels])
        base_avg = base_curves.mean(axis=0) / n_agents * 100
        base_std = base_curves.std(axis=0) / n_agents * 100
        t_axis = np.arange(1, len(base_avg) + 1)
        ax1.plot(t_axis, base_avg, color="#ef4444", linewidth=2, label="No defense")
        ax1.fill_between(t_axis, base_avg - base_std, base_avg + base_std,
                         color="#ef4444", alpha=0.15)

        # Defended curves
        def_curves = np.array([t.infected_per_tick for t in defended_tels])
        def_avg = def_curves.mean(axis=0) / n_agents * 100
        def_std = def_curves.std(axis=0) / n_agents * 100
        ax1.plot(t_axis, def_avg, color="#22c55e", linewidth=2, label="With defense")
        ax1.fill_between(t_axis, def_avg - def_std, def_avg + def_std,
                         color="#22c55e", alpha=0.15)

        ax1.set_xlabel("Tick")
        ax1.set_ylabel("Infected (%)")
        ax1.set_ylim(0, 105)
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        ax1.set_title(f"{topology} / {variant}")
        fig1.tight_layout()
        st.pyplot(fig1)
        plt.close()

    # Fig 2: Per-tick new infections
    with right:
        st.subheader("New Infections Per Tick")
        fig2, ax2 = plt.subplots(figsize=(6, 4))

        # Compute new infections per tick from cumulative
        for label, tels, color in [("No defense", baseline_tels, "#ef4444"),
                                    ("With defense", defended_tels, "#22c55e")]:
            curves = np.array([t.infected_per_tick for t in tels])
            avg = curves.mean(axis=0)
            new_per_tick = np.diff(avg, prepend=1)  # first tick has patient zero
            ax2.bar(np.arange(1, len(new_per_tick) + 1) + (0.2 if "No" in label else -0.2),
                    new_per_tick, width=0.4, color=color, alpha=0.7, label=label)

        ax2.set_xlabel("Tick")
        ax2.set_ylabel("New infections")
        ax2.legend()
        ax2.grid(True, axis="y", alpha=0.3)
        ax2.set_title("Propagation rate")
        fig2.tight_layout()
        st.pyplot(fig2)
        plt.close()

    # ─── Defense comparison sweep ────────────────────────────────────

    st.subheader("Defense Comparison")
    st.caption("Same topology and worm, comparing all defense configs")

    defense_configs = {
        "None": None,
        "Pattern only": dict(policy=False, pattern=True, judge=False),
        "Judge only": dict(policy=False, pattern=False, judge=True),
        "Rate limit only": dict(policy=True, pattern=False, judge=False),
        "Full": dict(policy=True, pattern=True, judge=True),
    }

    with st.spinner("Comparing defenses..."):
        eff_results = {}
        for dname, dcfg in defense_configs.items():
            effs = []
            for s in range(num_seeds):
                tel_d, _, _ = run_one(topology, n_agents, variant, dcfg, s, ticks)
                tel_b = baseline_tels[s]
                effs.append(containment_efficacy(tel_b, tel_d, n_agents))
            eff_results[dname] = (np.mean(effs), np.std(effs))

    fig3, ax3 = plt.subplots(figsize=(8, 4))
    names = list(eff_results.keys())
    means = [eff_results[n][0] for n in names]
    stds = [eff_results[n][1] for n in names]
    colors = ["#64748b", "#3b82f6", "#f59e0b", "#a855f7", "#22c55e"]
    bars = ax3.bar(names, means, yerr=stds, color=colors, edgecolor="white",
                   capsize=5, width=0.6)
    ax3.set_ylabel("Containment efficacy (η)")
    ax3.set_ylim(0, 1.1)
    ax3.grid(True, axis="y", alpha=0.3)
    ax3.set_title(f"Defense efficacy — {variant} worm on {topology}")

    # Add value labels
    for bar, m in zip(bars, means):
        ax3.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.03,
                 f"{m:.2f}", ha="center", fontsize=10, fontweight="bold")

    fig3.tight_layout()
    st.pyplot(fig3)
    plt.close()

    # ─── Raw data ────────────────────────────────────────────────────

    with st.expander("📊 Raw Results"):
        st.write("**Per-seed results (defended):**")
        for i, tel in enumerate(defended_tels):
            st.text(f"  seed {i}: R₀={r0(tel):.0f}  final={final_size(tel, n_agents)*100:.0f}%  "
                    f"curve={tel.infected_per_tick}")

else:
    st.info("👈 Configure settings in the sidebar and click **Run Simulation**.")
    st.markdown("""
    ### How it works

    1. **Pick a topology** — how agents are connected (star, ring, scale-free, mesh)
    2. **Pick a worm** — naive (obvious tags), obfuscated (business language), polymorphic (subtle hints)
    3. **Toggle defenses** — pattern filter, semantic judge, rate limiter
    4. **Run** — the simulator injects patient zero and tracks how the worm spreads tick by tick

    The simulation uses the exact same code as the command-line experiments.
    """)
