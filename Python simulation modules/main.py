"""WormLab — full experiment suite with publication-quality plots.

Usage:
  python main.py                 # full sweep (n=30, seeds=8)
  python main.py --quick         # fast smoke test
"""
from __future__ import annotations
import argparse, random, os
from collections import defaultdict
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from llm import MockLLM
from agent import Trifecta
from topology import BUILDERS
from worm import VARIANTS
from wormguard import WormGuard
from orchestrator import Orchestrator
from analyzer import r0, final_size, time_to_half, containment_efficacy, avg_and_std

OUT = "results"
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.size": 11, "axes.titlesize": 13, "figure.dpi": 150})


def run_one(topo_name, n, variant, defense_cfg, seed=0, ticks=15,
            deployment="decentralized", rho=0.0, exposure_fn=None):
    contacts = BUILDERS[topo_name](n, seed) if topo_name == "scale_free" else BUILDERS[topo_name](n)
    llm = MockLLM(obedience=0.92, seed=seed)
    rng = random.Random(seed)
    sidecar = WormGuard(**defense_cfg) if defense_cfg else None
    if sidecar:
        sidecar._rng = random.Random(seed + 1000)  # distinct from other rngs
    orch = Orchestrator(contacts, llm, sidecar=sidecar, seed=seed,
                        deployment=deployment, rho=rho, exposure_fn=exposure_fn)
    payload = VARIANTS[variant](rng, tick=0)
    orch.inject(patient_zero=0, payload=payload)
    return orch.run(ticks)


# ═══════════════════════════════════════════════════════════════════════
# Experiment 1: Baseline sweep
# ═══════════════════════════════════════════════════════════════════════

def experiment_baseline(n, ticks, seeds):
    topos = ["star", "ring", "scale_free", "mesh"]
    variants = ["naive", "obfuscated", "polymorphic"]
    defenses = {
        "none":         None,
        "policy_only":  dict(policy=True, pattern=False, judge=False),
        "pattern_only": dict(policy=False, pattern=True, judge=False),
        "judge_only":   dict(policy=False, pattern=False, judge=True),
        "full":         dict(policy=True, pattern=True, judge=True),
    }
    results = []
    hdr = f"{'topo':<12}{'variant':<14}{'defense':<16}{'R0':>8}{'final%':>9}{'eff':>8}"
    print(f"\n{hdr}\n{'─'*67}")

    for topo in topos:
        for v in variants:
            baselines = [run_one(topo, n, v, None, seed=s, ticks=ticks) for s in range(seeds)]
            r0s = [r0(t) for t in baselines]
            fss = [final_size(t, n) for t in baselines]
            r0_m, r0_s = avg_and_std(r0s)
            fs_m, _ = avg_and_std(fss)
            row = dict(topo=topo, variant=v, defense="none",
                       r0_mean=r0_m, r0_std=r0_s, final_pct=fs_m, efficacy=0.0, eff_std=0.0,
                       curves=[t.infected_per_tick for t in baselines])
            results.append(row)
            print(f"{topo:<12}{v:<14}{'none':<16}{r0_m:>7.1f}{fs_m*100:>8.1f}%{'—':>8}")

            for dname, dcfg in defenses.items():
                if dcfg is None:
                    continue
                tels = [run_one(topo, n, v, dcfg, seed=s, ticks=ticks) for s in range(seeds)]
                dr0s = [r0(t) for t in tels]
                dfss = [final_size(t, n) for t in tels]
                effs = [containment_efficacy(b, d, n) for b, d in zip(baselines, tels)]
                dr0_m, dr0_s = avg_and_std(dr0s)
                dfs_m, _ = avg_and_std(dfss)
                eff_m, eff_s = avg_and_std(effs)
                row = dict(topo=topo, variant=v, defense=dname,
                           r0_mean=dr0_m, r0_std=dr0_s, final_pct=dfs_m,
                           efficacy=eff_m, eff_std=eff_s,
                           curves=[t.infected_per_tick for t in tels])
                results.append(row)
                print(f"{topo:<12}{v:<14}{dname:<16}{dr0_m:>7.1f}{dfs_m*100:>8.1f}%{eff_m:>8.2f}")
        print()
    return results


# ═══════════════════════════════════════════════════════════════════════
# Experiment 2: Deployment sweep
# ═══════════════════════════════════════════════════════════════════════

def experiment_deployment(n, ticks, seeds):
    rhos = np.arange(0.0, 1.05, 0.1)
    variant = "polymorphic"
    topo = "scale_free"
    defense_cfg = dict(policy=True, pattern=True, judge=True)
    baselines = [run_one(topo, n, variant, None, seed=s, ticks=ticks) for s in range(seeds)]
    res = {"rho": list(rhos), "c_mean": [], "c_std": [], "d_mean": [], "d_std": []}
    print(f"\n{'rho':>5}  {'central':>10}  {'decentral':>10}")
    print("─" * 30)
    for rho in rhos:
        c_tels = [run_one(topo, n, variant, defense_cfg, seed=s, ticks=ticks,
                          deployment="centralized", rho=rho) for s in range(seeds)]
        d_tels = [run_one(topo, n, variant, defense_cfg, seed=s, ticks=ticks,
                          deployment="decentralized") for s in range(seeds)]
        c_effs = [containment_efficacy(b, d, n) for b, d in zip(baselines, c_tels)]
        d_effs = [containment_efficacy(b, d, n) for b, d in zip(baselines, d_tels)]
        cm, cs = avg_and_std(c_effs)
        dm, ds = avg_and_std(d_effs)
        res["c_mean"].append(cm); res["c_std"].append(cs)
        res["d_mean"].append(dm); res["d_std"].append(ds)
        print(f"{rho:>5.1f}  {cm:>10.3f}  {dm:>10.3f}")
    return res


# ═══════════════════════════════════════════════════════════════════════
# Experiment 3: Trifecta ablation
# ═══════════════════════════════════════════════════════════════════════

def experiment_trifecta(n, ticks, seeds):
    topo = "scale_free"
    variant = "naive"
    configs = {
        "Full trifecta":         lambda aid: Trifecta(True, True, True),
        "No data access":        lambda aid: Trifecta(False, True, True),
        "No untrusted input":    lambda aid: Trifecta(True, False, True),
        "No external comms":     lambda aid: Trifecta(True, True, False),
        "Only untrusted input":  lambda aid: Trifecta(False, True, False),
    }
    results = {}
    print(f"\n{'config':<24}{'final%':>9}{'R0':>8}")
    print("─" * 42)
    for name, efn in configs.items():
        tels = [run_one(topo, n, variant, None, seed=s, ticks=ticks, exposure_fn=efn)
                for s in range(seeds)]
        fs_vals = [final_size(t, n) for t in tels]
        r0_vals = [r0(t) for t in tels]
        fsm, fss = avg_and_std(fs_vals)
        r0m, _ = avg_and_std(r0_vals)
        results[name] = dict(final_mean=fsm, final_std=fss, r0=r0m)
        print(f"{name:<24}{fsm*100:>8.1f}%{r0m:>8.1f}")
    return results


# ═══════════════════════════════════════════════════════════════════════
# Plots
# ═══════════════════════════════════════════════════════════════════════

TOPO_COLORS = {"star": "#e74c3c", "ring": "#3498db", "scale_free": "#27ae60", "mesh": "#8e44ad"}
VAR_COLORS = {"naive": "#e74c3c", "obfuscated": "#f39c12", "polymorphic": "#8e44ad"}
DEF_COLORS = {"pattern_only": "#3498db", "judge_only": "#e67e22", "full": "#27ae60"}


def plot_fig1_infection_curves(results, n):
    """Infection curves by topology — naive worm, no defense."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for row in results:
        if row["defense"] == "none" and row["variant"] == "naive":
            curves = np.array(row["curves"])
            avg = curves.mean(axis=0) / n * 100
            std = curves.std(axis=0) / n * 100
            t = np.arange(1, len(avg) + 1)
            c = TOPO_COLORS[row["topo"]]
            ax.plot(t, avg, label=row["topo"], color=c, linewidth=2)
            ax.fill_between(t, avg - std, avg + std, color=c, alpha=0.15)
    ax.set_xlabel("Tick")
    ax.set_ylabel("Infected agents (%)")
    ax.set_title("Worm Propagation Speed by Network Topology\n(naive worm, no defense)")
    ax.legend(); ax.set_ylim(0, 105); ax.grid(True, alpha=0.3)
    fig.tight_layout(); fig.savefig(f"{OUT}/fig1_infection_curves.png"); plt.close()
    print(f"  → {OUT}/fig1_infection_curves.png")


def plot_fig2_r0_bars(results):
    """R₀ by topology × variant — with error bars."""
    topos = ["star", "ring", "scale_free", "mesh"]
    variants = ["naive", "obfuscated", "polymorphic"]
    data = defaultdict(dict)
    for row in results:
        if row["defense"] == "none":
            data[row["topo"]][row["variant"]] = (row["r0_mean"], row["r0_std"])
    fig, ax = plt.subplots(figsize=(8, 4.5))
    x = np.arange(len(topos))
    w = 0.25
    for i, v in enumerate(variants):
        means = [data[t].get(v, (0, 0))[0] for t in topos]
        stds = [data[t].get(v, (0, 0))[1] for t in topos]
        ax.bar(x + i * w, means, w, yerr=stds, label=v,
               color=VAR_COLORS[v], edgecolor="white", capsize=3)
    ax.set_xlabel("Topology"); ax.set_ylabel("R₀")
    ax.set_title("Basic Reproduction Number by Topology and Worm Variant")
    ax.set_xticks(x + w); ax.set_xticklabels(topos)
    ax.legend(); ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout(); fig.savefig(f"{OUT}/fig2_r0_bars.png"); plt.close()
    print(f"  → {OUT}/fig2_r0_bars.png")


def plot_fig3_defense_comparison(results):
    """KEY PLOT: defense efficacy by variant — shows pattern fails on polymorphic."""
    variants = ["naive", "obfuscated", "polymorphic"]
    defs = ["pattern_only", "judge_only", "full"]
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.5), sharey=True)
    for vi, v in enumerate(variants):
        ax = axes[vi]
        rows = [r for r in results if r["variant"] == v and r["topo"] == "mesh"]
        means, stds = [], []
        for d in defs:
            match = [r for r in rows if r["defense"] == d]
            means.append(match[0]["efficacy"] if match else 0)
            stds.append(match[0]["eff_std"] if match else 0)
        bars = ax.bar(range(len(defs)), means, yerr=stds,
                      color=[DEF_COLORS[d] for d in defs], edgecolor="white",
                      width=0.6, capsize=4)
        ax.set_xticks(range(len(defs)))
        ax.set_xticklabels(["Pattern", "Judge", "Full"], fontsize=10)
        ax.set_title(f"{v.capitalize()}", fontsize=12)
        ax.set_ylim(0, 1.15); ax.grid(True, axis="y", alpha=0.3)
        # Annotate zero bars
        for bi, m in enumerate(means):
            if m < 0.05:
                ax.text(bi, 0.03, "✗", ha="center", fontsize=14, color="#e74c3c", fontweight="bold")
    axes[0].set_ylabel("Containment efficacy (η)")
    fig.suptitle("Defense Efficacy Across Worm Sophistication (mesh topology)", fontsize=13, y=1.02)
    fig.tight_layout(); fig.savefig(f"{OUT}/fig3_defense_comparison.png", bbox_inches="tight"); plt.close()
    print(f"  → {OUT}/fig3_defense_comparison.png")


def plot_fig4_deployment(res):
    """HEADLINE PLOT: centralized collapses, decentralized holds."""
    fig, ax = plt.subplots(figsize=(7, 4.5))
    rhos = res["rho"]
    cm, cs = res["c_mean"], res["c_std"]
    dm, ds = res["d_mean"], res["d_std"]
    ax.plot(rhos, cm, "o-", color="#e74c3c", linewidth=2.5, markersize=5,
            label="Centralized (API gateway)")
    ax.fill_between(rhos, [m - s for m, s in zip(cm, cs)],
                    [m + s for m, s in zip(cm, cs)], color="#e74c3c", alpha=0.15)
    ax.plot(rhos, dm, "s-", color="#27ae60", linewidth=2.5, markersize=5,
            label="Decentralized (per-agent sidecar)")
    ax.fill_between(rhos, [m - s for m, s in zip(dm, ds)],
                    [m + s for m, s in zip(dm, ds)], color="#27ae60", alpha=0.15)
    ax.set_xlabel("ρ (fraction of locally-run agents)")
    ax.set_ylabel("Containment efficacy (η)")
    ax.set_title("Centralized vs Decentralized Defense\n(polymorphic worm, scale-free, full defense)")
    ax.legend(fontsize=10); ax.set_ylim(-0.05, 1.1); ax.grid(True, alpha=0.3)
    fig.tight_layout(); fig.savefig(f"{OUT}/fig4_deployment_sweep.png"); plt.close()
    print(f"  → {OUT}/fig4_deployment_sweep.png")


def plot_fig5_trifecta(tri):
    """Trifecta ablation — horizontal bar chart with error bars."""
    fig, ax = plt.subplots(figsize=(7, 4))
    names = list(tri.keys())
    means = [tri[k]["final_mean"] * 100 for k in names]
    stds = [tri[k]["final_std"] * 100 for k in names]
    colors = ["#e74c3c", "#3498db", "#27ae60", "#f39c12", "#8e44ad"]
    y = range(len(names))
    ax.barh(y, means, xerr=stds, color=colors[:len(names)], edgecolor="white", capsize=3)
    ax.set_yticks(y); ax.set_yticklabels(names, fontsize=10)
    ax.set_xlabel("Final infection size (%)")
    ax.set_title("Trifecta Ablation: Which Legs Matter for Propagation?")
    ax.set_xlim(0, 115); ax.grid(True, axis="x", alpha=0.3)
    fig.tight_layout(); fig.savefig(f"{OUT}/fig5_trifecta_ablation.png"); plt.close()
    print(f"  → {OUT}/fig5_trifecta_ablation.png")


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=30)
    ap.add_argument("--ticks", type=int, default=20)
    ap.add_argument("--seeds", type=int, default=8)
    ap.add_argument("--quick", action="store_true")
    args = ap.parse_args()
    if args.quick:
        args.n, args.ticks, args.seeds = 15, 12, 4

    print("=" * 67)
    print("  WormLab — Prompt Worm Propagation Testbed")
    print("=" * 67)

    print("\n▶ Experiment 1: Baseline sweep")
    bl = experiment_baseline(args.n, args.ticks, args.seeds)
    plot_fig1_infection_curves(bl, args.n)
    plot_fig2_r0_bars(bl)
    plot_fig3_defense_comparison(bl)

    print("\n▶ Experiment 2: Deployment sweep")
    dp = experiment_deployment(args.n, args.ticks, args.seeds)
    plot_fig4_deployment(dp)

    print("\n▶ Experiment 3: Trifecta ablation")
    tri = experiment_trifecta(args.n, args.ticks, args.seeds)
    plot_fig5_trifecta(tri)

    print(f"\n✓ All done — results in {OUT}/")


if __name__ == "__main__":
    main()
