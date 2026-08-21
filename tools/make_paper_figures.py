"""
Generates the figures for the academic paper on Juicetification: The Lean Rush.
Figures 3 and 4 use the real embedded discrete-event engine so the numbers are
authentic. Run:  python make_paper_figures.py
"""
import types, sys, copy, math, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle
from matplotlib.lines import Line2D

TEAL, DARK, AMBER, BLUE, RED, GREY, LGREY, PALE = (
    "#2a9d8f", "#264653", "#e9a72c", "#8ecae6", "#e76f51",
    "#5f6b6b", "#9aa0a0", "#f2f8f7")
plt.rcParams["font.family"] = "DejaVu Sans"

# Resolve paths relative to the repo root so the script runs from anywhere.
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = os.path.join(ROOT, "docs", "academic_paper", "figures")
os.makedirs(OUTDIR, exist_ok=True)

# ---- load the engine out of app.py (the part before the streamlit UI) --------
src = open(os.path.join(ROOT, "app.py")).read()
eng = types.ModuleType("eng"); eng.__dict__["__name__"] = "eng"; sys.modules["eng"] = eng
exec(compile(src[:src.index("import sys as _sys")], "eng", "exec"), eng.__dict__)
sim = eng
IDEAL = list(sim.ROUTE) + ["Pickup"]
coords = lambda order: {s: (0, i) for i, s in enumerate(order)}
os.chdir(OUTDIR)   # figure files are written here (docs/academic_paper/figures)


# =====================================================================
# FIGURE 1 — Kolb's experiential cycle mapped onto the PDCA game loop
# =====================================================================
def fig1():
    fig, ax = plt.subplots(figsize=(7.8, 5.2)); ax.set_xlim(-0.6, 10.6)
    ax.set_ylim(0.2, 9.8); ax.axis("off")
    quads = [
        (5, 8.4, "DO — run the rush", "Concrete Experience", "operate the shop through a 15-min rush"),
        (8.4, 5, "CHECK — diagnose", "Reflective Observation", "read the 7-wastes & 5S dashboards"),
        (5, 1.6, "ACT — coaching kata", "Abstract Conceptualization", "name the dominant waste & principle"),
        (1.6, 5, "PLAN — decide & test", "Active Experimentation", "choose a counter-measure, predict, commit"),
    ]
    for x, y, phase, kolb, doing in quads:
        ax.add_patch(FancyBboxPatch((x - 1.75, y - 0.95), 3.5, 1.9,
                     boxstyle="round,pad=0.05,rounding_size=0.18",
                     facecolor=PALE, edgecolor=TEAL, lw=1.6, zorder=3))
        ax.text(x, y + 0.55, phase, ha="center", va="center", fontsize=10.5,
                fontweight="bold", color=DARK, zorder=4)
        ax.text(x, y + 0.12, kolb, ha="center", va="center", fontsize=8.6,
                fontstyle="italic", color=TEAL, zorder=4)
        ax.text(x, y - 0.52, doing, ha="center", va="center", fontsize=7.6,
                color=GREY, zorder=4, wrap=True)
    # clockwise arrows
    for a0, a1 in [(90, 0), (0, -90), (-90, 180), (180, 90)]:
        r0, r1 = math.radians(a0), math.radians(a1)
        p0 = (5 + 3.05 * math.cos(r0), 5 + 3.05 * math.sin(r0))
        p1 = (5 + 3.05 * math.cos(r1), 5 + 3.05 * math.sin(r1))
        ax.add_patch(FancyArrowPatch(p0, p1, connectionstyle="arc3,rad=0.28",
                     arrowstyle="-|>", mutation_scale=16, lw=2.0, color=LGREY, zorder=1))
    ax.text(5, 5, "kaizen\n(repeat)", ha="center", va="center", fontsize=9.5,
            fontweight="bold", color=LGREY)
    fig.tight_layout(); fig.savefig("fig1_kolb_pdca.png", dpi=200,
                                    bbox_inches="tight", facecolor="white")
    plt.close(fig)


# =====================================================================
# FIGURE 2 — making waste visible: scrambled vs. lean process layout
# =====================================================================
def _flow(ax, order, title):
    abbr = {"Cups": "CUP", "Fruit": "FRT", "Ice": "ICE", "Blender": "BLD",
            "Finish": "FIN", "Pickup": "PICK"}
    proc = list(sim.ROUTE) + ["Pickup"]
    stepno = {s: i + 1 for i, s in enumerate(proc)}
    xpos = {s: i for i, s in enumerate(order)}
    n = len(order)
    ax.set_xlim(-0.7, n - 0.3); ax.set_ylim(-1.7, 1.7); ax.axis("off")
    for a, b in zip(proc, proc[1:]):
        xa, xb = xpos[a], xpos[b]
        if xb > xa:
            color, y, rad = TEAL, 0.42, -0.28
        else:
            color, y, rad = RED, -0.6, -0.32
        ax.add_patch(FancyArrowPatch((xa, y), (xb, y),
                     connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>",
                     mutation_scale=12, lw=1.9, color=color, zorder=1))
    for s, x in xpos.items():
        ax.add_patch(FancyBboxPatch((x - 0.33, -0.26), 0.66, 0.52,
                     boxstyle="round,pad=0.02,rounding_size=0.1", lw=1.3,
                     edgecolor=DARK, facecolor=AMBER if s == "Pickup" else BLUE,
                     zorder=2))
        ax.text(x, 0, abbr[s], ha="center", va="center", fontsize=9,
                fontweight="bold", color=DARK, zorder=3)
        ax.add_patch(Circle((x - 0.23, 0.16), 0.1, facecolor=DARK, zorder=4))
        ax.text(x - 0.23, 0.16, str(stepno[s]), ha="center", va="center",
                fontsize=6.5, color="white", fontweight="bold", zorder=5)
    ax.set_title(title, fontsize=10.5, fontweight="bold", color=DARK)


def fig2():
    fig, axes = plt.subplots(2, 1, figsize=(7.2, 5.0))
    _flow(axes[0], ["Fruit", "Pickup", "Blender", "Cups", "Ice", "Finish"],
          "(a) Inherited layout — red arrows show backtracking (transport waste)")
    _flow(axes[1], IDEAL,
          "(b) Redesigned layout — process order, every arrow forward (green)")
    fig.tight_layout(); fig.savefig("fig2_flow_waste.png", dpi=200,
                                    bbox_inches="tight", facecolor="white")
    plt.close(fig)


# =====================================================================
# FIGURE 3 — Lean Score & profit trajectory across a guided improvement path
# =====================================================================
def fig3():
    base = dict(demand_level="Normal", five_s="Disorganized", standard_level=0,
                visual_level=0, batch_size=4, premade=10,
                layout=coords(["Fruit", "Pickup", "Blender", "Cups", "Ice", "Finish"]))
    # The actual four-round guided arc (the game's ROUND_PLAN sequence).
    L2 = coords(IDEAL)
    steps = [
        ("R1\nInherited mess", {}),
        ("R2\nSort + Set-in-order", {"layout": L2, "batch_size": 1, "premade": 0}),
        ("R3\nShine + Standard + Visual",
         {"layout": L2, "batch_size": 1, "premade": 0, "five_s": "Full 5S",
          "standard_level": 2, "visual_level": 1}),
        ("R4\nSustain + Capacity",
         {"layout": L2, "batch_size": 1, "premade": 0, "five_s": "Full 5S",
          "standard_level": 2, "visual_level": 1, "employees": 5, "blenders": 3}),
    ]
    scores, profits = [], []
    for _, ov in steps:
        d = dict(base); d.update(ov)
        r = sim.run_simulation(sim.Config(**d), base_seed=7)
        scores.append(r.lean_score); profits.append(r.profit)
    x = list(range(len(steps)))
    fig, ax1 = plt.subplots(figsize=(7.6, 4.5))
    ax1.plot(x, scores, "-o", color=TEAL, lw=2.6, markersize=8, label="Lean Score", zorder=3)
    ax1.set_ylabel("Lean Score (0–100)", color=TEAL, fontsize=10, fontweight="bold")
    ax1.tick_params(axis="y", labelcolor=TEAL)
    ax1.set_ylim(0, 100)
    ax1.axhline(70, ls="--", lw=1.2, color=TEAL, alpha=0.5)
    ax1.text(0.03, 72, "completion threshold (Lean Score ≥ 70)", fontsize=7.8, color=TEAL)
    ax2 = ax1.twinx()
    ax2.plot(x, profits, "-s", color=AMBER, lw=2.4, markersize=7, label="Profit ($)", zorder=3)
    ax2.axhline(0, ls=":", lw=1.0, color="#b5811f", alpha=0.6)
    ax2.set_ylabel("Profit per rush ($)", color="#b5811f", fontsize=10, fontweight="bold")
    ax2.tick_params(axis="y", labelcolor="#b5811f")
    ax2.set_ylim(-140, 140)
    ax2.annotate("one-piece flow before\ncapacity → lost sales",
                 xy=(1, profits[1]), xytext=(1.25, -125), fontsize=7.6,
                 color=RED, ha="left",
                 arrowprops=dict(arrowstyle="->", color=RED, lw=1.1))
    ax2.annotate("capacity relieves the\nbottleneck → profit rebounds",
                 xy=(3, profits[3]), xytext=(2.2, 118), fontsize=7.6,
                 color="#b5811f", ha="left",
                 arrowprops=dict(arrowstyle="->", color="#b5811f", lw=1.1))
    ax1.set_xticks(x); ax1.set_xticklabels([s for s, _ in steps], fontsize=8)
    ax1.set_xlim(-0.3, 3.3)
    ax1.set_xlabel("Guided improvement round", fontsize=9.5)
    ax1.set_title("Lean Score climbs steadily; profit exposes the sequencing lesson",
                  fontsize=11, fontweight="bold", color=DARK)
    ax1.grid(axis="y", alpha=0.15)
    fig.tight_layout(); fig.savefig("fig3_trajectory.png", dpi=200,
                                    bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return scores, profits


# =====================================================================
# FIGURE 4 — impact vs. effort: what each intervention returns per dollar
# =====================================================================
def fig4():
    final = sim.Config(layout=coords(IDEAL), five_s="Full 5S", standard_level=2,
                       visual_level=1, batch_size=1, premade=0, employees=5,
                       blenders=3, demand_level="Normal")
    base = sim.run_simulation(copy.deepcopy(final), base_seed=7)

    def contrib(name, cost, **revert):
        c = copy.deepcopy(final)
        for k, v in revert.items():
            setattr(c, k, v)
        v = sim.run_simulation(c, base_seed=7)
        return name, cost, base.profit - v.profit

    rows = [
        contrib("Order the line", 1.0, layout=coords(["Fruit", "Pickup", "Blender",
                                                      "Cups", "Ice", "Finish"])),
        contrib("5S clean & label", 6.0, five_s="Disorganized"),
        contrib("Standard work", 4.0, standard_level=0),
        contrib("Visual signals", 2.0, visual_level=0),
        contrib("One-piece flow", 0.0, batch_size=4, premade=10),
        contrib("Add capacity", 30.0, employees=3, blenders=1),
    ]
    fig, ax = plt.subplots(figsize=(6.6, 4.4))
    ax.axhline(0, color="#999", lw=1)
    for name, cost, dp in rows:
        good = dp >= 1.0
        ax.scatter(cost, dp, s=110, color=TEAL if good else RED,
                   edgecolors=DARK, zorder=3)
        ax.annotate(name, (cost, dp), fontsize=8, xytext=(6, 5),
                    textcoords="offset points", color=DARK)
    ax.set_xlabel("Cost to add ($/rush)  →  more expensive", fontsize=9.5)
    ax.set_ylabel("Profit contributed ($/rush)", fontsize=9.5)
    ax.set_title("Impact vs. effort: the cheapest organising moves pay back most",
                 fontsize=10.5, fontweight="bold", color=DARK)
    ax.grid(alpha=0.15)
    fig.tight_layout(); fig.savefig("fig4_impact_effort.png", dpi=200,
                                    bbox_inches="tight", facecolor="white")
    plt.close(fig)


# =====================================================================
# FIGURE 5 — mapping learning theory to concrete design features
# =====================================================================
def fig5():
    rows = [
        ("Experiential learning cycle", "Kolb (1984)",
         "Every round runs Do → Check → Act → Plan"),
        ("Productive failure", "Kapur (2008)",
         "Inherited messy shop; overproduction trap before instruction"),
        ("Disorienting dilemma", "Mezirow (1991)",
         "Batching feels fast but the data show it is worst"),
        ("Scaffolding within the ZPD", "Wood et al. (1976)",
         "Guided mode opens one decision; fades to Free Play"),
        ("Cognitive-load management", "Sweller (1988)",
         "Only the actionable waste is surfaced each round"),
        ("Feed-forward feedback", "Hattie & Timperley (2007)",
         "Predict-then-test; coach states 'where to next'"),
        ("Debriefing", "Fanning & Gaba (2007)",
         "Gated end-of-game synthesis + knowledge check"),
        ("Coaching Kata", "Rother (2010)",
         "Five-question routine drives the Act phase"),
        ("Constructive alignment", "Biggs (1996)",
         "Objectives, activity, and PDF rubric aligned"),
        ("Transfer (hugging/bridging)", "Perkins & Salomon (1988)",
         "Closing task maps wastes to the learner's own workplace"),
    ]
    fig, ax = plt.subplots(figsize=(7.4, 5.4)); ax.axis("off")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    x0, x1, x2 = 0.02, 0.34, 0.56
    top = 0.96; rh = 0.086
    ax.add_patch(Rectangle((0, top - rh + 0.004), 1, rh, facecolor=TEAL, edgecolor="none"))
    ax.text(x0, top - rh/2 + 0.004, "Learning principle", fontsize=9.5,
            fontweight="bold", color="white", va="center")
    ax.text(x1, top - rh/2 + 0.004, "Source", fontsize=9.5, fontweight="bold",
            color="white", va="center")
    ax.text(x2, top - rh/2 + 0.004, "Design feature in the simulation", fontsize=9.5,
            fontweight="bold", color="white", va="center")
    y = top - rh
    for i, (prin, src, feat) in enumerate(rows):
        if i % 2 == 0:
            ax.add_patch(Rectangle((0, y - rh + 0.004), 1, rh, facecolor="#f4f8f7",
                                   edgecolor="none"))
        ax.text(x0, y - rh/2 + 0.004, prin, fontsize=8.4, color=DARK, va="center",
                fontweight="bold")
        ax.text(x1, y - rh/2 + 0.004, src, fontsize=8.2, color=TEAL, va="center",
                fontstyle="italic")
        ax.text(x2, y - rh/2 + 0.004, feat, fontsize=8.0, color=GREY, va="center")
        y -= rh
    fig.tight_layout(); fig.savefig("fig5_theory_map.png", dpi=200,
                                    bbox_inches="tight", facecolor="white")
    plt.close(fig)


fig1(); fig2(); sc, pr = fig3(); fig4(); fig5()
print("figures written")
print("trajectory scores:", [round(s, 1) for s in sc])
print("trajectory profit:", [round(p, 1) for p in pr])
