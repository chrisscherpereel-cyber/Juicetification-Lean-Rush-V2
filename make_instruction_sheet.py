"""
Generates `instruction_sheet.pdf` — a one-page, visual quick guide to hand to
students playing "Juicetification: The Lean Rush".

    python make_instruction_sheet.py

Pure matplotlib, no external assets, and it deliberately avoids colour emoji
(which don't render in PDF fonts) so it looks identical everywhere.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle, Rectangle
from matplotlib.lines import Line2D

TEAL = "#2a9d8f"
DARK = "#264653"
AMBER = "#ffd166"
BLUE = "#8ecae6"
RED = "#e76f51"
GREY = "#5f6b6b"
LGREY = "#9aa0a0"
PALE = "#f2f8f7"

fig = plt.figure(figsize=(8.5, 11))
fig.patch.set_facecolor("white")
T = fig.transFigure
L, R = 0.07, 0.93


def box(x, y, w, h, fc=PALE, ec=TEAL, lw=1.1, r=0.010, z=1):
    fig.add_artist(FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0.003,rounding_size={r}",
        transform=T, facecolor=fc, edgecolor=ec, lw=lw, zorder=z,
        mutation_aspect=0.55))


def txt(x, y, s, size=9, color=DARK, weight="normal", ha="left", va="center",
        style="normal", z=4):
    fig.text(x, y, s, fontsize=size, color=color, fontweight=weight, ha=ha,
             va=va, style=style, zorder=z)


def rule(y, x0=L, x1=R, color="#e2e6e6", lw=0.9):
    fig.add_artist(Line2D([x0, x1], [y, y], transform=T, color=color, lw=lw))


def arrow(p0, p1, color=LGREY, lw=1.5, rad=0.0, scale=10, z=2):
    fig.add_artist(FancyArrowPatch(p0, p1, transform=T, arrowstyle="-|>",
                                   mutation_scale=scale, lw=lw, color=color,
                                   connectionstyle=f"arc3,rad={rad}", zorder=z))


def section(y, n, title):
    txt(L, y, f"{n} · {title}", 13, DARK, "bold")
    rule(y - 0.008, color=TEAL, lw=1.4)


# ----------------------------------------------------------------- header ---
fig.add_artist(Rectangle((0, 0.918), 1, 0.082, transform=T,
                         facecolor=TEAL, edgecolor="none", zorder=0))
txt(L, 0.958, "Juicetification: The Lean Rush", 22, "white", "bold")
txt(L, 0.934,
    "Student quick guide  ·  about 30–45 min, best in one sitting  ·  a required "
    "debrief is reviewed",
    10.0, "#dff3ef")

# --------------------------------------------- 1. how one round works ---
section(0.893, 1, "How one round works — the PDCA loop")

# PDCA as a clean 2x2 cycle
bw, bh = 0.098, 0.030
cx1, cx2 = 0.155, 0.310            # column centres
cy1, cy2 = 0.816, 0.762            # row centres
for cx, cy, lab in [(cx1, cy1, "CHECK"), (cx2, cy1, "ACT"),
                    (cx2, cy2, "PLAN"), (cx1, cy2, "DO")]:
    box(cx - bw / 2, cy - bh / 2, bw, bh, fc="white", ec=TEAL, lw=1.4, r=0.008, z=3)
    txt(cx, cy, lab, 10.5, TEAL, "bold", ha="center", z=4)
arrow((cx1 + bw / 2 + 0.005, cy1), (cx2 - bw / 2 - 0.005, cy1))          # CHECK->ACT
arrow((cx2, cy1 - bh / 2 - 0.004), (cx2, cy2 + bh / 2 + 0.004))          # ACT->PLAN
arrow((cx2 - bw / 2 - 0.005, cy2), (cx1 + bw / 2 + 0.005, cy2))          # PLAN->DO
arrow((cx1, cy2 + bh / 2 + 0.004), (cx1, cy1 - bh / 2 - 0.004))          # DO->CHECK
txt((cx1 + cx2) / 2, (cy1 + cy2) / 2, "kaizen", 8.5, LGREY, "bold", ha="center", z=4)

sx, sy = 0.44, 0.828
for i, (k, d) in enumerate([
        ("CHECK", "Read the top panel: Lean Score, profit, which wastes are red."),
        ("ACT", "The coach asks one question. Answer it — this unlocks RUN."),
        ("PLAN", "The coach opens the ONE decision worth the most. Change it."),
        ("DO", "Press the flashing RUN button in the sidebar.")]):
    fig.add_artist(Circle((sx + 0.012, sy), 0.011, transform=T, facecolor=TEAL,
                          edgecolor="none", zorder=3))
    txt(sx + 0.012, sy, str(i + 1), 8.5, "white", "bold", ha="center", z=4)
    txt(sx + 0.035, sy + 0.008, k, 9.5, TEAL, "bold")
    txt(sx + 0.035, sy - 0.009, d, 8.5, GREY)
    sy -= 0.030

# --------------------------------------------------------- 2. your goal ---
section(0.700, 2, "You finish when all four are ticked")

goals = [("Wastes worth fixing", "countered where it pays"),
         ("Lean Score  ≥ 70", "quality, speed, flow"),
         ("Profit  > $0", "the shop makes money"),
         ("Spending pays off", "drop what doesn't pay")]
gw = (R - L - 3 * 0.014) / 4
for i, (title, sub) in enumerate(goals):
    gx = L + i * (gw + 0.014)
    box(gx, 0.612, gw, 0.062, fc=PALE, ec=TEAL, lw=1.3)
    fig.add_artist(Circle((gx + 0.020, 0.655), 0.009, transform=T,
                          facecolor=TEAL, edgecolor="none", zorder=3))
    txt(gx + 0.020, 0.655, "✓", 8, "white", "bold", ha="center", z=4)
    txt(gx + 0.035, 0.655, title, 8.6, DARK, "bold")
    txt(gx + 0.012, 0.632, sub, 7.4, GREY)
txt(L, 0.599, "There is no fixed number of rounds — take as many as you need.",
    8.6, GREY, style="italic")

# ------------------------------------------- 3. the 7 wastes and fixes ---
section(0.570, 3, "The 7 wastes and how you fix each one")

wastes = [
    ("Overproduction", "Making drinks before they're ordered",
     "5S #1 Sort — batch 1, no pre-made", "free"),
    ("Transport", "Drinks carried back and forth",
     "5S #2 Set in order — line up the stations", "$1"),
    ("Motion", "Staff hunting for tools",
     "5S #3 Shine — clean & label", "$3–6"),
    ("Overprocessing", "Every drink made a different way",
     "5S #4 Standardize — recipe cards", "$2–8"),
    ("Inventory", "Stock sitting around going stale",
     "5S #5 Sustain — one-piece / FIFO / pull", "free–$3"),
    ("Defects", "Wrong drinks that must be remade",
     "Visual signals — a ticket rail", "$2–10"),
    ("Waiting", "Customers walking out",
     "Capacity — only at the bottleneck", "varies"),
]
ry = 0.536
for i, (w, prob, fix, cost) in enumerate(wastes):
    if i % 2 == 0:
        fig.add_artist(Rectangle((L, ry - 0.0115), R - L, 0.023, transform=T,
                                 facecolor="#f7fafa", edgecolor="none", zorder=0))
    txt(L + 0.004, ry, w, 8.8, DARK, "bold")
    txt(L + 0.135, ry, prob, 8.2, GREY)
    txt(L + 0.40, ry, fix, 8.2, TEAL, "bold")
    txt(R - 0.004, ry, cost, 8.2, DARK, ha="right")
    ry -= 0.023
rule(ry + 0.011)

# ------------------------------------------------ 4. what to do first ---
section(0.348, 4, "What to do first — cheap beats expensive")

ladder = [("1", "Order", "the line", "almost free"),
          ("2", "5S clean", "& label", "low"),
          ("3", "Recipe", "cards", "low"),
          ("4", "Visual", "ticket rail", "low"),
          ("5", "Sustain", "stock", "low"),
          ("6", "Add staff /", "blender", "high — last")]
lwid = (R - L - 5 * 0.010) / 6
for i, (n, l1, l2, cost) in enumerate(ladder):
    lx = L + i * (lwid + 0.010)
    last = i == len(ladder) - 1
    box(lx, 0.268, lwid, 0.058, fc="#fdf3e3" if last else PALE,
        ec=AMBER if last else TEAL, lw=1.2)
    txt(lx + lwid / 2, 0.313, n, 9, AMBER if last else TEAL, "bold", ha="center")
    txt(lx + lwid / 2, 0.298, l1, 8.4, DARK, "bold", ha="center")
    txt(lx + lwid / 2, 0.287, l2, 8.4, DARK, "bold", ha="center")
    txt(lx + lwid / 2, 0.275, cost, 7.4, GREY, ha="center")
    if not last:
        arrow((lx + lwid + 0.0015, 0.297), (lx + lwid + 0.0085, 0.297),
              lw=1.2, scale=8, z=3)
txt(L, 0.255, "The cheapest organising changes return the most per dollar.",
    8.4, GREY, style="italic")
txt(L, 0.244, "Capacity costs money every rush — add it only at the real bottleneck.",
    8.4, GREY, style="italic")

# --------------------------------------------- 5. reading the flow map ---
section(0.215, 5, "Reading the flow diagram")

fx, fy = L + 0.012, 0.163
step = 0.062
for i, n in enumerate(["CUP", "FRT", "ICE", "BLD", "FIN"]):
    bx = fx + i * step
    box(bx, fy - 0.013, 0.050, 0.026, fc=BLUE, ec=DARK, lw=1.0, r=0.006, z=3)
    txt(bx + 0.025, fy, n, 8.2, DARK, "bold", ha="center", z=4)
    if i < 4:                      # green forward arcs, clearly ABOVE the blocks
        arrow((bx + 0.025, fy + 0.017), (bx + step + 0.025, fy + 0.017),
              color=TEAL, lw=1.7, rad=-0.55, scale=10, z=2)
# one red backtrack arc, clearly BELOW the blocks
arrow((fx + 3 * step + 0.025, fy - 0.017), (fx + 0.025, fy - 0.017),
      color=RED, lw=1.7, rad=-0.30, scale=10, z=2)
txt(fx + 0.330, fy + 0.020, "green above = forward flow (good)", 8.3, TEAL, "bold")
txt(fx + 0.330, fy - 0.022, "red below = backtracking (waste)", 8.3, RED, "bold")
txt(L, 0.113,
    "Drag the stations into the order a drink is actually made, until every arrow "
    "is green.", 8.6, GREY, style="italic")

# ----------------------------------------------------------- 6. finish ---
box(L, 0.052, R - L, 0.054, fc=PALE, ec=TEAL, lw=1.2)
txt(L + 0.016, 0.091, "Finishing up — how to hand in", 10, DARK, "bold")
txt(L + 0.016, 0.074,
    "When all four objectives are ticked, a debrief opens. The four reflections and "
    "the 5-question check are", 8.5, GREY)
txt(L + 0.016, 0.062,
    "required and reviewed by your instructor. Download the report any time: page 1 says "
    "COMPLETE or INCOMPLETE.", 8.5, GREY)

fig.text(0.5, 0.028, "Juicetification: The Lean Rush  ·  student quick guide",
         fontsize=7.5, color=LGREY, ha="center")

import os
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUT = os.path.join(_ROOT, "docs", "instruction_sheet.pdf")
os.makedirs(os.path.dirname(_OUT), exist_ok=True)
fig.savefig(_OUT, format="pdf")
print("wrote", _OUT)
