"""
Juicetification: The Lean Rush — a lean-operations juice bar simulation (single file)

Everything (discrete-event engine + Streamlit interface) lives in this one file.
Run with:  streamlit run app.py
"""
from __future__ import annotations


import hashlib
import heapq
import json
import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Tuple


# --------------------------------------------------------------------------
# Static parameters (kept explicit so students / instructors can read them).
# --------------------------------------------------------------------------

HORIZON_S = 900.0          # 15-minute rush window (seconds)
WALK_SECONDS_PER_UNIT = 3.0  # seconds to walk one grid cell (Manhattan)

# The route every fresh drink follows.
ROUTE = ["Cups", "Fruit", "Ice", "Blender", "Finish"]

# Base "touch" time (seconds) to work each station, before 5S/motion effects.
BASE_STEP_TIME = {
    "Cups": 4.0,
    "Fruit": 9.0,
    "Ice": 5.0,
    "Blender": 18.0,   # actual blending
    "Finish": 8.0,     # pour, lid, label, hand off
}
BLEND_SETUP = 6.0       # per blend cycle -- this is what batching amortizes
HANDOFF_TIME = 2.0      # seconds lost passing an order between specialists

# Money.  All in dollars.
COSTS = {
    "employee_per_min": 0.55,   # fully-loaded wage
    "blender_per_rush": 12.0,   # amortized equipment
    "ingredients_per_drink": 0.80,
    "spoilage_per_unit": 0.80,
    "drink_price": 4.50,        # revenue per served customer
    "lost_sale_penalty": 4.50,  # opportunity cost of a walkout
    "defect_goodwill": 2.00,    # goodwill hit on top of the refund for a wrong drink
}

# Per-rush *implementation / upkeep* cost of each lean improvement. Lean is not
# free: organizing, training, signage and kanban all cost something every rush.
# These let students judge whether a change actually pays for itself.
# Note how the cheapest changes (layout, basic 5S) are also the highest-impact --
# that is the lesson about what to do first.
LEAN_COSTS = {
    "layout_change": 1.0,   # rearranging stations -- almost free
    "five_s_basic": 3.0,    # sort/label/clean upkeep
    "five_s_full": 6.0,     # full 5S program with audits
    "pull_system": 3.0,     # kanban + more frequent restock trips
    "fifo": 1.0,            # use-oldest-first labelling/rotation discipline
}

# Tiered improvements.  Each higher tier costs more but the extra benefit shrinks,
# so students learn that some levels are great value and the top ones are usually
# too expensive to be worth it.  "defect" = drop in wrong-order probability.
STANDARD_LEVELS = [
    {"name": "None", "cost": 0.0, "defect": 0.00, "cv": 0.55, "finish": 1.00,
     "desc": "Every barista improvises each drink — slow and error-prone."},
    {"name": "Recipe cards", "cost": 2.0, "defect": 0.05, "cv": 0.35, "finish": 0.92,
     "desc": "A laminated recipe at each station. Cheap, big consistency gain."},
    {"name": "Cards + training", "cost": 4.0, "defect": 0.07, "cv": 0.22, "finish": 0.82,
     "desc": "Staff trained to one agreed method. Steady speed, few mistakes."},
    {"name": "Full SOP + audits", "cost": 8.0, "defect": 0.08, "cv": 0.18, "finish": 0.78,
     "desc": "Documented procedures with audits. Small extra gain, a lot more cost."},
]
VISUAL_LEVELS = [
    {"name": "None", "cost": 0.0, "defect": 0.00,
     "desc": "Orders shouted across the bar — easy to mix up or lose."},
    {"name": "Whiteboard ticket rail", "cost": 2.0, "defect": 0.04,
     "desc": "A cheap visible queue of order tickets. Most of the benefit, little cost."},
    {"name": "Digital order screen", "cost": 5.0, "defect": 0.06,
     "desc": "A screen shows each order. A few fewer errors, noticeably more cost."},
    {"name": "Full display + call lights", "cost": 10.0, "defect": 0.07,
     "desc": "High-tech display with alerts. Tiny extra gain for a big price."},
]


def implementation_cost(cfg):
    """Return (total $/rush, breakdown dict) for the active lean improvements."""
    b = {}
    if path_distance(cfg.layout) < path_distance(DEFAULT_LAYOUT):
        b["Layout change"] = LEAN_COSTS["layout_change"]
    if cfg.five_s == "Basic":
        b["5S upkeep"] = LEAN_COSTS["five_s_basic"]
    elif cfg.five_s == "Full 5S":
        b["5S upkeep"] = LEAN_COSTS["five_s_full"]
    if cfg.standard_level > 0:
        b["Standard work"] = STANDARD_LEVELS[cfg.standard_level]["cost"]
    if cfg.visual_level > 0:
        b["Visual signals"] = VISUAL_LEVELS[cfg.visual_level]["cost"]
    if cfg.pull_replenishment:
        b["Pull system"] = LEAN_COSTS["pull_system"]
    if cfg.fifo_rotation:
        b["FIFO rotation"] = LEAN_COSTS["fifo"]
    return sum(b.values()), b

# Default layout: (row, col) on a 4x4 floor.  Deliberately bad -- ingredients
# scattered so the walking path is long.  Pickup is the customer counter.
DEFAULT_LAYOUT = {
    "Cups": (0, 0),
    "Fruit": (3, 3),
    "Ice": (0, 3),
    "Blender": (3, 0),
    "Finish": (1, 2),
    "Pickup": (0, 1),
}

DRINK_TYPES = ["Berry", "Green", "Tropical", "Citrus"]


# --------------------------------------------------------------------------
# Configuration container
# --------------------------------------------------------------------------

@dataclass
class Config:
    # capacity
    employees: int = 3
    blenders: int = 1

    # flow
    assignment_mode: str = "Whole-order"        # or "Specialized stations"
    # employee split for specialized mode: Prep / Blend / Finish
    spec_prep: int = 1
    spec_blend: int = 1
    spec_finish: int = 1

    # lean levers
    layout: Dict[str, Tuple[int, int]] = field(
        default_factory=lambda: dict(DEFAULT_LAYOUT)
    )
    five_s: str = "Disorganized"                 # Disorganized / Basic / Full 5S
    standard_level: int = 0                       # 0..3 tier of standard work
    visual_level: int = 0                         # 0..3 tier of visual signals
    batch_size: int = 1                          # drinks made per blend cycle
    pull_replenishment: bool = False
    fifo_rotation: bool = False                  # use-oldest-first stock rotation
    premade: int = 0                             # pre-made drinks staged at open

    # scenario / demand
    demand_level: str = "Normal"                 # Light / Normal / Slammed
    replications: int = 8

    # per-session randomised scenario modifiers (defaults = neutral, so existing
    # behaviour is unchanged unless a scenario overrides them)
    time_mult: Dict[str, float] = field(default_factory=dict)  # slow station "twist"
    demand_mult: float = 1.0                      # scales arrival rate
    patience_mean: float = 150.0                  # avg customer patience (s)
    defect_base: float = 0.16                     # baseline mistake proneness

    # convenience read-only views (a tier > 0 means the practice is "on")
    @property
    def standard_recipes(self) -> bool:
        return self.standard_level > 0

    @property
    def visual_signals(self) -> bool:
        return self.visual_level > 0


# --------------------------------------------------------------------------
# Tiny discrete-event scheduler + resource
# --------------------------------------------------------------------------

class _Sim:
    def __init__(self, seed: int):
        self.now = 0.0
        self._heap: List[Tuple[float, int, Callable]] = []
        self._seq = 0
        self.rng = random.Random(seed)

    def schedule(self, delay: float, cb: Callable):
        heapq.heappush(self._heap, (self.now + max(0.0, delay), self._seq, cb))
        self._seq += 1

    def run(self, until: float):
        while self._heap and self._heap[0][0] <= until:
            t, _, cb = heapq.heappop(self._heap)
            self.now = t
            cb()

    def drain(self):
        # finish everyone already in the system (rush tail), no new arrivals.
        while self._heap:
            t, _, cb = heapq.heappop(self._heap)
            self.now = t
            cb()


class _Resource:
    """A pool of identical servers with a FIFO wait queue of callbacks."""

    def __init__(self, capacity: int):
        self.capacity = max(1, capacity)
        self.busy = 0
        self.queue: List[Callable] = []

    def request(self, cb: Callable):
        if self.busy < self.capacity:
            self.busy += 1
            cb()
        else:
            self.queue.append(cb)

    def release(self):
        self.busy -= 1
        if self.queue:
            nxt = self.queue.pop(0)
            self.busy += 1
            nxt()


# --------------------------------------------------------------------------
# Derived quantities
# --------------------------------------------------------------------------

def manhattan(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def path_distance(layout: Dict[str, Tuple[int, int]]) -> int:
    """Grid distance walked to make one fresh drink: Cups->...->Finish->Pickup."""
    seq = ROUTE + ["Pickup"]
    return sum(manhattan(layout[seq[i]], layout[seq[i + 1]])
               for i in range(len(seq) - 1))


def _five_s_factor(level: str) -> float:
    return {"Disorganized": 1.6, "Basic": 1.25, "Full 5S": 1.0}.get(level, 1.6)


def _demand_rates(level: str) -> Tuple[float, float]:
    """(start rate, peak rate) in customers per second, ramped linearly."""
    per_min = {
        "Light": (1.0, 4.0),
        "Normal": (1.5, 7.0),
        "Slammed": (2.5, 10.0),
    }.get(level, (1.5, 7.0))
    return per_min[0] / 60.0, per_min[1] / 60.0


def defect_probability(cfg: Config) -> float:
    p = cfg.defect_base
    p -= STANDARD_LEVELS[cfg.standard_level]["defect"]
    p -= VISUAL_LEVELS[cfg.visual_level]["defect"]
    p -= {"Disorganized": 0.0, "Basic": 0.015, "Full 5S": 0.03}[cfg.five_s]
    return max(0.02, p)


def service_cv(cfg: Config) -> float:
    """Coefficient of variation of service time -- standard work shrinks it."""
    return STANDARD_LEVELS[cfg.standard_level]["cv"]


# --------------------------------------------------------------------------
# Order + the two process flows
# --------------------------------------------------------------------------

@dataclass
class _Order:
    oid: int
    arrive: float
    dtype: str
    patience: float
    started: bool = False
    done: bool = False
    abandoned: bool = False
    finish_t: float = 0.0
    reworked: bool = False
    from_premade: bool = False


def _lognormal(sim: _Sim, mean: float, cv: float) -> float:
    if mean <= 0:
        return 0.0
    sigma = math.sqrt(math.log(1 + cv * cv))
    mu = math.log(mean) - 0.5 * sigma * sigma
    return math.exp(sim.rng.gauss(mu, sigma))


def _run_once(cfg: Config, seed: int) -> Dict:
    sim = _Sim(seed)
    fs = _five_s_factor(cfg.five_s)
    cv = service_cv(cfg)
    dist = path_distance(cfg.layout)
    p_defect = defect_probability(cfg)

    # Pre-blend / blend / post timings (used by whole-order phased service).
    def _tm(station):                              # per-station "slow day" twist
        return cfg.time_mult.get(station, 1.0)
    fetch_time = (BASE_STEP_TIME["Cups"] * _tm("Cups")
                  + BASE_STEP_TIME["Fruit"] * _tm("Fruit")
                  + BASE_STEP_TIME["Ice"] * _tm("Ice")) * fs
    finish_time = (BASE_STEP_TIME["Finish"] * _tm("Finish")
                   * STANDARD_LEVELS[cfg.standard_level]["finish"])
    # Blending a batch takes one setup + one blend cycle regardless of size; the
    # CUSTOMER still waits the full cycle, so batching does NOT speed their drink.
    # Its only "benefit" is the (batch_size-1) extra drinks made ahead -> premade
    # stock (overproduction) that spoils or gets served stale.
    blend_time = BASE_STEP_TIME["Blender"] * _tm("Blender") + BLEND_SETUP
    PREMADE_DEFECT_BONUS = 0.25  # a made-ahead drink is often stale / mismatched
    motion_time = dist * WALK_SECONDS_PER_UNIT
    # Specialized mode keeps workers at stations: far less transport.
    spec_motion = HANDOFF_TIME * len(ROUTE)

    employees = _Resource(cfg.employees)
    blenders = _Resource(cfg.blenders)

    # metrics accumulators
    served: List[float] = []       # cycle times
    walk_units = 0.0
    defects = 0
    waste_units = 0.0
    abandoned = 0
    arrivals = 0
    in_system = 0
    wip_area = 0.0
    last_evt = 0.0
    peak_queue = 0
    series = [(0.0, 0)]          # (time, number in shop) change points
    arr_t, srv_t, ab_t = [], [], []   # arrival / served / abandon timestamps

    # premade inventory keyed by drink type (roughly even split)
    premade: Dict[str, int] = {d: 0 for d in DRINK_TYPES}
    for i in range(cfg.premade):
        premade[DRINK_TYPES[i % len(DRINK_TYPES)]] += 1

    def touch_wip():
        nonlocal wip_area, last_evt, peak_queue
        wip_area += in_system * (sim.now - last_evt)
        last_evt = sim.now
        if in_system > peak_queue:
            peak_queue = in_system
        series.append((sim.now, in_system))

    def nonlocal_walk(d):
        nonlocal walk_units
        walk_units += d

    def make_ahead(o: _Order):
        # a blend cycle yields batch_size drinks; extras become premade stock
        extras = cfg.batch_size - 1
        if extras > 0:
            premade[o.dtype] = premade.get(o.dtype, 0) + extras

    def complete(o: _Order, from_premade: bool = False):
        nonlocal in_system, defects, waste_units
        touch_wip()
        o.done = True
        o.finish_t = sim.now
        in_system -= 1
        series.append((sim.now, in_system))
        srv_t.append(sim.now)
        served.append(o.finish_t - o.arrive)
        p = p_defect + (PREMADE_DEFECT_BONUS if from_premade else 0.0)
        if sim.rng.random() < p:
            # caught + reworked: extra ingredients wasted, counts as incorrect.
            defects += 1
            waste_units += 1
            o.reworked = True

    # ---- Whole-order flow: one employee owns the drink end to end ----------
    def wo_start(o: _Order):
        employees.request(lambda: wo_phase1(o))

    def wo_phase1(o: _Order):
        if o.abandoned:               # walked out while queued -> free the server
            employees.release()
            return
        o.started = True
        # try premade first (skip the line), else walk the route and make fresh
        if premade.get(o.dtype, 0) > 0:
            premade[o.dtype] -= 1
            o.from_premade = True
            sim.schedule(_lognormal(sim, finish_time, cv), lambda: wo_finish(o))
        else:
            nonlocal_walk(dist)
            pre = _lognormal(sim, fetch_time + motion_time, cv)
            sim.schedule(pre, lambda: wo_blend_req(o))

    def wo_blend_req(o: _Order):
        # employee is HELD while waiting for a blender -> visible waiting waste
        blenders.request(lambda: wo_blend(o))

    def wo_blend(o: _Order):
        sim.schedule(_lognormal(sim, blend_time, cv), lambda: wo_post(o))

    def wo_post(o: _Order):
        blenders.release()
        make_ahead(o)                 # extras from the batch -> premade stock
        sim.schedule(_lognormal(sim, finish_time, cv), lambda: wo_finish(o))

    def wo_finish(o: _Order):
        employees.release()
        complete(o, o.from_premade)

    # ---- Specialized flow: tandem line Prep -> Blend -> Finish -------------
    prep = _Resource(cfg.spec_prep)
    blendstn = _Resource(cfg.spec_blend)
    finstn = _Resource(cfg.spec_finish)

    def sp_start(o: _Order):
        prep.request(lambda: sp_prep(o))

    def sp_prep(o: _Order):
        if o.abandoned:               # walked out while queued -> free the server
            prep.release()
            return
        o.started = True
        if premade.get(o.dtype, 0) > 0:
            premade[o.dtype] -= 1
            o.from_premade = True
            prep.release()
            finstn.request(lambda: sp_finish(o))
            return
        nonlocal_walk(spec_motion / WALK_SECONDS_PER_UNIT)
        sim.schedule(_lognormal(sim, fetch_time + spec_motion, cv),
                     lambda: (prep.release(), blendstn.request(lambda: sp_blend_req(o))))

    def sp_blend_req(o: _Order):
        blenders.request(lambda: sp_blend(o))

    def sp_blend(o: _Order):
        sim.schedule(_lognormal(sim, blend_time, cv), lambda: sp_blend_done(o))

    def sp_blend_done(o: _Order):
        blenders.release()
        blendstn.release()
        make_ahead(o)
        finstn.request(lambda: sp_finish(o))

    def sp_finish(o: _Order):
        sim.schedule(_lognormal(sim, finish_time, cv), lambda: sp_finish_done(o))

    def sp_finish_done(o: _Order):
        finstn.release()
        complete(o, o.from_premade)

    start_flow = wo_start if cfg.assignment_mode == "Whole-order" else sp_start

    # ---- Arrivals (non-homogeneous Poisson via thinning) -------------------
    r0, rpeak = _demand_rates(cfg.demand_level)
    r0 *= cfg.demand_mult
    rpeak *= cfg.demand_mult

    def rate(t: float) -> float:
        frac = min(1.0, t / HORIZON_S)
        return r0 + (rpeak - r0) * frac

    def schedule_arrival(prev_t: float):
        nonlocal arrivals, in_system
        t = prev_t
        while True:
            t += sim.rng.expovariate(rpeak)
            if t > HORIZON_S:
                return
            if sim.rng.random() <= rate(t) / rpeak:
                break

        def arrive(at=t):
            nonlocal arrivals, in_system
            sim.now = at
            touch_wip()
            arrivals += 1
            in_system += 1
            series.append((at, in_system))
            arr_t.append(at)
            patience = _lognormal(sim, cfg.patience_mean, 0.5)
            o = _Order(arrivals, at, sim.rng.choice(DRINK_TYPES), patience)
            orders[o.oid] = o
            start_flow(o)
            # reneging: if never started by deadline, walk out
            sim.schedule(patience, lambda oo=o: renege(oo))
            schedule_arrival(at)

        sim.schedule(t - sim.now, arrive)

    orders: Dict[int, _Order] = {}

    def renege(o: _Order):
        nonlocal abandoned, in_system
        if not o.started and not o.done and not o.abandoned:
            touch_wip()
            o.abandoned = True
            abandoned += 1
            in_system -= 1
            series.append((sim.now, in_system))
            ab_t.append(sim.now)
            # try to remove its still-pending callback from the entry queue
            for res in (employees, prep):
                res.queue = [cb for cb in res.queue
                             if getattr(cb, "_oid", None) != o.oid]

    schedule_arrival(0.0)
    sim.run(HORIZON_S)
    sim.drain()
    touch_wip()

    # ---- End-of-rush waste: overproduction + spoilage ----------------------
    leftover_premade = sum(premade.values())
    waste_units += leftover_premade                      # unsold made-ahead drinks
    if not cfg.pull_replenishment:
        # push replenishment overstocks perishable prep -> spoilage; batching
        # makes the overstock worse. FIFO rotation (use-oldest-first) keeps the
        # held stock fresh, so far less of it spoils -- a cheap discipline that
        # mitigates spoilage without lowering the stock level the way pull does.
        prep_stock = 6 + 3 * (cfg.batch_size - 1)
        spoil_rate = 0.05 if cfg.fifo_rotation else 0.15
        waste_units += spoil_rate * prep_stock

    horizon_min = HORIZON_S / 60.0
    labor = cfg.employees * COSTS["employee_per_min"] * horizon_min
    equip = cfg.blenders * COSTS["blender_per_rush"]
    ingredients = len(served) * COSTS["ingredients_per_drink"]
    spoil = waste_units * COSTS["spoilage_per_unit"]
    lost = abandoned * COSTS["lost_sale_penalty"]
    # a wrong order is refunded (lost revenue) plus a goodwill hit
    refunds = defects * (COSTS["drink_price"] + COSTS["defect_goodwill"])
    upkeep, _ = implementation_cost(cfg)     # cost of running the lean program
    revenue = len(served) * COSTS["drink_price"]
    total_cost = labor + equip + ingredients + spoil + lost + refunds + upkeep

    # sample the congestion + cumulative curves onto a 30-second grid
    grid = [t for t in range(0, int(HORIZON_S) + 1, 30)]
    wip_grid = _sample_step(series, grid)
    cum_arr = [sum(1 for x in arr_t if x <= g) for g in grid]
    cum_srv = [sum(1 for x in srv_t if x <= g) for g in grid]
    cum_ab = [sum(1 for x in ab_t if x <= g) for g in grid]

    return {
        "arrivals": arrivals,
        "served": len(served),
        "cycle_times": served,
        "avg_cycle": statistics.mean(served) if served else 0.0,
        "defects": defects,
        "waste": waste_units,
        "walk_units": walk_units,
        "abandoned": abandoned,
        "avg_wip": wip_area / max(1e-9, sim.now),
        "peak_queue": peak_queue,
        "labor": labor,
        "equip": equip,
        "ingredients": ingredients,
        "spoil": spoil,
        "lost": lost,
        "refunds": refunds,
        "upkeep": upkeep,
        "revenue": revenue,
        "total_cost": total_cost,
        "profit": revenue - total_cost,
        "path_distance": dist,
        "grid_min": [g / 60.0 for g in grid],
        "wip_grid": wip_grid,
        "cum_arr": cum_arr,
        "cum_srv": cum_srv,
        "cum_ab": cum_ab,
    }


def _sample_step(series, grid):
    """Value of a step function (list of (t, value)) at each grid time."""
    series = sorted(series)
    out, j, cur = [], 0, 0
    for g in grid:
        while j < len(series) and series[j][0] <= g:
            cur = series[j][1]
            j += 1
        out.append(cur)
    return out


# --------------------------------------------------------------------------
# Public API: run replications and aggregate
# --------------------------------------------------------------------------

@dataclass
class RoundResult:
    avg_cycle: float
    avg_cycle_sd: float
    served: float
    arrivals: float
    defects: float
    waste: float
    walk_units: float
    abandoned: float
    abandon_pct: float
    avg_wip: float
    peak_queue: float
    total_cost: float
    revenue: float
    profit: float
    upkeep: float
    path_distance: int
    lean_score: float
    all_cycle_times: List[float]
    served_series: List[float]
    cost_breakdown: Dict[str, float]
    timeline: Dict[str, List[float]]
    reps: List[Dict]


def _mean(xs):
    return statistics.mean(xs) if xs else 0.0


def run_simulation(cfg: Config, base_seed: int = 1234) -> RoundResult:
    reps = [_run_once(cfg, base_seed + 100 * r) for r in range(max(1, cfg.replications))]

    avg_cycle = _mean([r["avg_cycle"] for r in reps])
    served = _mean([r["served"] for r in reps])
    arrivals = _mean([r["arrivals"] for r in reps])
    defects = _mean([r["defects"] for r in reps])
    waste = _mean([r["waste"] for r in reps])
    walk = _mean([r["walk_units"] for r in reps])
    abandoned = _mean([r["abandoned"] for r in reps])
    wip = _mean([r["avg_wip"] for r in reps])
    cost = _mean([r["total_cost"] for r in reps])
    revenue = _mean([r["revenue"] for r in reps])
    profit = _mean([r["profit"] for r in reps])
    upkeep = _mean([r["upkeep"] for r in reps])
    peak = _mean([r["peak_queue"] for r in reps])
    cyc_sd = statistics.pstdev([r["avg_cycle"] for r in reps]) if len(reps) > 1 else 0.0

    all_ct: List[float] = []
    for r in reps:
        all_ct.extend(r["cycle_times"])

    cost_breakdown = {
        "Labor": _mean([r["labor"] for r in reps]),
        "Equipment": _mean([r["equip"] for r in reps]),
        "Ingredients": _mean([r["ingredients"] for r in reps]),
        "Waste/spoilage": _mean([r["spoil"] for r in reps]),
        "Rework & refunds": _mean([r["refunds"] for r in reps]),
        "Lost sales": _mean([r["lost"] for r in reps]),
        "Lean upkeep": upkeep,
    }

    # pick a representative rep (served closest to the mean) for the timeline
    rep0 = min(reps, key=lambda r: abs(r["served"] - served))
    timeline = {
        "min": rep0["grid_min"],
        "wip": rep0["wip_grid"],
        "arrived": rep0["cum_arr"],
        "served": rep0["cum_srv"],
        "walked_out": rep0["cum_ab"],
    }

    abandon_pct = 100.0 * abandoned / arrivals if arrivals else 0.0
    score = _lean_score(avg_cycle, served, arrivals, defects, waste,
                        abandon_pct, wip, cost)

    return RoundResult(
        avg_cycle=avg_cycle,
        avg_cycle_sd=cyc_sd,
        served=served,
        arrivals=arrivals,
        defects=defects,
        waste=waste,
        walk_units=walk,
        abandoned=abandoned,
        abandon_pct=abandon_pct,
        avg_wip=wip,
        peak_queue=peak,
        total_cost=cost,
        revenue=revenue,
        profit=profit,
        upkeep=upkeep,
        path_distance=reps[0]["path_distance"],
        lean_score=score,
        all_cycle_times=all_ct,
        served_series=[r["served"] for r in reps],
        cost_breakdown=cost_breakdown,
        timeline=timeline,
        reps=reps,
    )


def _lean_score(cycle, served, arrivals, defects, waste, abandon_pct, wip, cost) -> float:
    """0-100 composite of five operational dimensions, each scored 0..1 and
    weighted. Every dimension is a RATE (per-drink / per-customer), so the score
    means the same thing in a quiet shop or a slammed one and rises smoothly and
    monotonically as the shop gets leaner — no flat penalty that floors a busy
    shop at 0 and hides incremental progress."""
    def clamp(x):
        return max(0.0, min(1.0, x))

    n = max(1.0, arrivals)
    served_n = max(1.0, served)
    defect_rate = defects / served_n
    # correctly-served fraction: a wrong drink is not a good service
    eff_service = clamp((served - defects) / n)
    quality = clamp(1.0 - defect_rate / 0.15)             # 0% def=1, 15%+=0
    speed = clamp(1.0 - (cycle - 60.0) / 180.0)           # 60s=1, 240s=0
    flow = clamp(1.0 - (wip - 3.0) / 12.0)                # WIP<=3=1, 15+=0
    # waste as a rate per customer so it doesn't scale with sheer demand; a leaner
    # shop always scores higher, and the overproduction trap (lots of waste) is
    # penalised here as well as through its extra defects.
    waste_score = clamp(1.0 - (waste / n) / 0.5)          # 0/drink=1, 0.5/drink=0

    # Waste carries the most weight: eliminating it is the heart of lean, and it
    # keeps the overproduction trap (batching/pre-making) from ever winning while
    # still letting the score rise smoothly with every genuine improvement.
    score = 100.0 * (0.25 * eff_service + 0.15 * quality + 0.10 * speed
                     + 0.10 * flow + 0.40 * waste_score)
    return round(max(0.0, min(100.0, score)), 1)


def seven_wastes_diagnostic(cfg: Config, res: RoundResult) -> List[Dict]:
    """Map current configuration + results onto TIMWOOD with a RAG flag."""
    def flag(bad, warn):
        return "red" if bad else ("amber" if warn else "green")

    defect_rate = res.defects / max(1.0, res.served)
    items = [
        {
            "waste": "Transport",
            "concept": "5S / layout",
            "flag": flag(res.path_distance > 12, res.path_distance > 7),
            "detail": f"Fresh-drink path is {res.path_distance} grid units "
                      f"(~{res.path_distance*WALK_SECONDS_PER_UNIT:.0f}s walking/drink). "
                      "Relocate ingredients along the flow to shrink it.",
        },
        {
            "waste": "Inventory",
            "concept": "One-piece flow / FIFO / pull",
            "flag": flag(res.avg_wip > 8 or cfg.premade > 8,
                         res.avg_wip > 4 or cfg.premade > 3),
            "detail": f"Avg work-in-process ~{res.avg_wip:.1f} orders; "
                      f"{cfg.premade} premade staged. High inventory hides problems "
                      "and spoils.",
        },
        {
            "waste": "Motion",
            "concept": "5S / visual workspace",
            "flag": flag(cfg.five_s == "Disorganized", cfg.five_s == "Basic"),
            "detail": f"5S level: {cfg.five_s}. Searching for unlabeled items adds "
                      "hidden seconds to every fetch.",
        },
        {
            "waste": "Waiting",
            "concept": "Capacity / bottleneck",
            "flag": flag(res.abandon_pct > 20, res.abandon_pct > 8),
            "detail": f"{res.abandon_pct:.0f}% of customers walked out. "
                      "Balance the line or add capacity at the constraint.",
        },
        {
            "waste": "Overproduction",
            "concept": "Batch size",
            "flag": flag(cfg.batch_size >= 4 or cfg.premade > 8,
                         cfg.batch_size >= 2 or cfg.premade > 3),
            "detail": f"Batch size {cfg.batch_size}, {cfg.premade} premade. "
                      "Making ahead feels fast but creates unsold, spoiling drinks.",
        },
        {
            "waste": "Overprocessing",
            "concept": "Standard work",
            "flag": flag(cfg.standard_level == 0, cfg.standard_level == 1),
            "detail": (f"Standard work: {STANDARD_LEVELS[cfg.standard_level]['name']}. "
                       + STANDARD_LEVELS[cfg.standard_level]["desc"]),
        },
        {
            "waste": "Defects",
            "concept": "Standard work / visual signals",
            "flag": flag(defect_rate > 0.12, defect_rate > 0.06),
            "detail": f"{defect_rate*100:.0f}% of orders wrong -> rework + wasted "
                      "ingredients. Standard recipes and order signals cut this.",
        },
    ]
    return items

import sys as _sys
sim = _sys.modules[__name__]  # expose engine as `sim`

# ==========================================================================
#  USER INTERFACE  (the engine above is exposed through the name `sim`)
# ==========================================================================
import copy

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Circle

import streamlit as st
import student_store as store   # per-student progress (safe no-op when unconfigured)

try:
    from streamlit_sortables import sort_items
    HAVE_DND = True
except Exception:                       # library not installed -> button fallback
    HAVE_DND = False

st.set_page_config(page_title="Juicetification: The Lean Rush", page_icon="🥤",
                   layout="wide", initial_sidebar_state="expanded")

# Darken the small caption/help text — the default light grey was hard to read.
st.markdown(
    "<style>[data-testid='stCaptionContainer'],"
    "[data-testid='stCaptionContainer'] p{color:#3b3b3b !important;}</style>",
    unsafe_allow_html=True)

# ---- styling for the REQUIRED coach question (students were scrolling past it) --
st.markdown("""
<style>
@keyframes jrAskPulse{0%,100%{box-shadow:0 0 0 0 rgba(230,57,70,.50);}
 50%{box-shadow:0 0 0 12px rgba(230,57,70,0);}}
@keyframes jrFlashNow{0%{box-shadow:0 0 0 10px rgba(230,57,70,.85);}
 100%{box-shadow:0 0 0 0 rgba(230,57,70,0);}}
.jr-ask{border:3px solid #e63946;background:#fff5f3;border-radius:12px;
 padding:14px 16px 12px;margin:12px 0 6px;animation:jrAskPulse 1.8s infinite;}
.jr-ask.done{border-color:#2a9d8f;background:#eefaf7;animation:none;}
.jr-ask.jr-flash{animation:jrFlashNow 1.6s ease-out 1;}
.jr-ask-tag{display:inline-block;background:#e63946;color:#fff;font-weight:800;
 font-size:12px;letter-spacing:.05em;text-transform:uppercase;padding:4px 10px;
 border-radius:999px;margin-bottom:9px;}
.jr-ask.done .jr-ask-tag{background:#2a9d8f;}
.jr-ask-h{font-size:1.22rem;font-weight:800;color:#1d1d1d;margin-bottom:4px;}
.jr-ask-q{font-size:1.06rem;line-height:1.5;color:#222;}
.jr-ask-hint{font-size:.86rem;color:#8a2b33;margin-top:8px;font-weight:600;}
.jr-ask.done .jr-ask-hint{color:#1f6f66;}
</style>""", unsafe_allow_html=True)

import re as _re_md


def _mini_md(text):
    """Escape HTML, then honour the **bold** / *italic* used in question text."""
    t = (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    t = _re_md.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = _re_md.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<i>\1</i>", t)
    return t


def jr_jump_button(label="⬆️ Take me to the coach's question",
                   target="jr-act", flash="jr-coachq", height=60):
    """A button that scrolls the main page up to the coach's question and makes
    the question card flash, so a locked student is one click from the fix."""
    import streamlit.components.v1 as _c
    _c.html("""
<button id="jrjump" onclick="jrGo()">""" + label + """</button>
<style>
 html,body{margin:0;padding:0;}
 #jrjump{width:100%;cursor:pointer;border:0;border-radius:9px;padding:11px 12px;
  font-family:"Source Sans Pro","Segoe UI",sans-serif;font-size:15px;
  font-weight:700;color:#fff;background:#e63946;
  box-shadow:0 2px 6px rgba(0,0,0,.18);}
 #jrjump:hover{background:#c62936;}
</style>
<script>
function jrGo(){
  var P=window.parent,D=P.document;
  var el=D.getElementById(\"""" + target + """\");
  if(!el){return;}
  var node=el.parentElement,sc=null;
  while(node){
    var s=P.getComputedStyle(node);
    if(/(auto|scroll)/.test(s.overflowY)&&node.scrollHeight>node.clientHeight+4){
      sc=node;break;}
    node=node.parentElement;
  }
  var off=95;
  if(sc){
    sc.scrollTo({top:sc.scrollTop+el.getBoundingClientRect().top
      -sc.getBoundingClientRect().top-off,behavior:"smooth"});
  }else{
    P.scrollTo({top:P.scrollY+el.getBoundingClientRect().top-off,
      behavior:"smooth"});
  }
  var f=D.getElementById(\"""" + flash + """\");
  if(f){f.classList.remove("jr-flash");void f.offsetWidth;
        f.classList.add("jr-flash");}
}
</script>""", height=height)

# ---- Juicetification Director: instructor-configurable scenario/grading -----
# With no ?cfg=/?game= URL parameter, CFG == built-in defaults and the app is
# unchanged. See manifest.py for the parameter schema and juice_director.py for
# the (shared, unmodified) loader.
from manifest import MANIFEST
from juice_director import serve_manifest_if_requested, resolve_config
serve_manifest_if_requested(MANIFEST)
# `?game=<code>` links pull the instructor's saved configuration straight from
# storage (the same Dropbox the Director writes to); `?cfg=` still works too.
CFG, CTX = resolve_config(MANIFEST, fetch=store.load_game_config)
# apply the instructor's economics / rush overrides to the engine constants
HORIZON_S = CFG["horizon_s"]
BLEND_SETUP = CFG["blend_setup"]
HANDOFF_TIME = CFG["handoff_time"]

# ---- per-student persistence (student_store): identity + resume gate ---------
game = store.game_code()          # ?game= code (or None)
sid = store.get_student_id()      # ?sid= student id (or None)

# Storage self-check: open the app with ?diag=1 to see whether THIS deployment
# actually detects the storage secrets (values are never shown, only presence).
if st.query_params.get("diag"):
    st.title("🔧 Storage diagnostic")
    st.write({
        "storage enabled": store.enabled(),
        "game code (?game=)": game,
        "student id (?sid=)": sid,
        "DB_ENCRYPTION_KEY present": bool(store.DB_ENCRYPTION_KEY),
        "DROPBOX_ACCESS_TOKEN present": bool(store._ACCESS),
        "DROPBOX_REFRESH_TOKEN present": bool(store._REFRESH),
        "DROPBOX_APP_KEY present": bool(store._APP_KEY),
        "DROPBOX_APP_SECRET present": bool(store._APP_SECRET),
        "PROGRESS_ROOT": store.PROGRESS_ROOT,
    })
    st.info("`storage enabled` must be true for logins to persist. It requires "
            "DB_ENCRYPTION_KEY plus either DROPBOX_ACCESS_TOKEN or all three of "
            "DROPBOX_REFRESH_TOKEN + DROPBOX_APP_KEY + DROPBOX_APP_SECRET.")
    st.stop()

# Require a student ID whenever this is a *managed* session — a Director game
# link (?game=) or any deployment with storage enabled. A plain local run with
# neither still skips the gate and behaves exactly as before.
if (game or store.enabled()) and not sid:
    st.title("🥤 Juicetification: The Lean Rush")
    _entered = st.text_input("Enter your student ID to begin", key="_sid_gate")
    if st.button("Start", type="primary") and _entered.strip():
        store.set_student_id(_entered)
        st.rerun()
    if game and not store.enabled():
        st.warning("Progress storage isn't detected on this deployment, so "
                   "progress won't be saved. Instructor: add the storage secrets "
                   "(open this page with `?diag=1` to check which are missing).")
    st.stop()                     # don't build the lab until a student id exists

STATION_EMOJI = {"Cups": "🥤", "Fruit": "🍓", "Ice": "🧊",
                 "Blender": "🌀", "Finish": "🏷️", "Pickup": "🧍"}
STATION_ABBR = {"Cups": "CUP", "Fruit": "FRT", "Ice": "ICE",
                "Blender": "BLD", "Finish": "FIN", "Pickup": "PICK"}
RAG = {"green": "🟢", "amber": "🟡", "red": "🔴"}

PROCESS = sim.ROUTE + ["Pickup"]                 # the order a drink is actually made
STEP_NO = {s: i + 1 for i, s in enumerate(PROCESS)}
IDEAL_ORDER = list(PROCESS)                       # stations lined up in process order


def coords_from_order(order):
    """Stations sit left-to-right in a line; process motion is 1-D distance."""
    return {s: (0, i) for i, s in enumerate(order)}


def order_distance(order):
    return sim.path_distance(coords_from_order(order))


GROUPS = ["layout", "inventory", "quality", "capacity"]
# The guided path follows the 5 S's of lean, in order.
ROUND_PLAN = {
    1: {"unlock": [], "concept": "Baseline",
        "title": "Round 1 — Feel the chaos",
        "focus": "Just press **Run** and watch the messy shop you inherited cope "
                 "with the rush. This is the 'before' you'll improve on.",
        "why": "You need a starting score to prove your later changes worked."},
    2: {"unlock": ["layout", "inventory"], "concept": "5S #1 Sort · #2 Set in order",
        "title": "Round 2 — Sort & Set in order (5S steps 1–2)",
        "focus": "**Sort:** clear out the inherited over-batching and pile of "
                 "pre-made cups (drop batch size to 1 and pre-made toward 0). "
                 "**Set in order:** drag the stations into the order a drink is "
                 "made, killing the red backtracking arrows.",
        "why": "The first two S's are the cheapest, biggest wins: keep only what's "
               "needed, and put the steps in the order they're used."},
    3: {"unlock": ["layout", "inventory", "quality"],
        "concept": "5S #3 Shine · #4 Standardize",
        "title": "Round 3 — Shine & Standardize (5S steps 3–4)",
        "focus": "**Shine:** raise housekeeping so stations are clean and labeled "
                 "(no hunting). **Standardize:** pick a standard-work level and a "
                 "visual-signal level — cheaper tiers give most of the benefit.",
        "why": "A clean, labeled, standardized station is faster and makes far "
               "fewer mistakes."},
    4: {"unlock": ["layout", "inventory", "quality", "capacity"],
        "concept": "5S #5 Sustain · Capacity",
        "title": "Round 4 — Sustain & right-size (5S step 5)",
        "focus": "**Sustain:** turn on pull replenishment so gains stick and "
                 "nothing spoils. Then add staff or blenders **only** where "
                 "customers actually pile up.",
        "why": "Sustain keeps the discipline; capacity is powerful but costs money "
               "every rush, so add it only at the real bottleneck."},
}
# Guided rounds beyond 4 when mastery isn't yet 7/7 — keep every lever open and
# point the student at what's still unaddressed (no "core done" message yet).
CONTINUE = {"unlock": GROUPS, "concept": "Kaizen — finish the job",
            "title": "Keep improving — address all 7 wastes",
            "focus": "A few wastes still need a counter-measure. Use the coach and "
                     "the 7-wastes dashboard to find what's left, then fix it.",
            "why": "The core is complete only when every one of the 7 wastes has a "
                   "sensible counter-measure in place (lean mastery 7/7)."}
FREE_PLAY = {"unlock": GROUPS, "concept": "Kaizen",
             "title": "Free play — keep improving",
             "focus": "Free play: every lever is open. Experiment to push your Lean "
                      "Score and profit higher.",
             "why": "Weigh every tool against its cost and see how high you can go."}
# Shown once all three objectives are met (guided), so the top banner never tells a
# finished student to "keep improving."
DONE_PLAN = {"unlock": GROUPS, "concept": "Kaizen — complete",
             "title": "✅ Objectives met — the core simulation is complete",
             "focus": "You've addressed all 7 wastes with a high Lean Score and a "
                      "healthy profit. Scroll down to your **debrief**; keep "
                      "experimenting here if you'd like.",
             "why": "You met all three objectives — waste, quality/flow, and cost."}

def lean_level(cfg, res):
    """A waste is 'addressed' when the student has the right counter-measure DECISION
    in place — so the count reflects the choices they actually made this round, not a
    lucky green outcome. Every counter-measure is cheap and achievable, so 7/7 is
    always reachable. (Waiting is the one exception: it also counts when walkouts are
    already low, because adding capacity you don't need is not lean.) Returns
    (done, total, items)."""
    capacity_maxed = cfg.employees >= 6 and cfg.blenders >= 4
    items = [
        ("Transport — stations lined up in process order",
         backtracks(cfg_layout_order(cfg)) == 0),
        ("Overproduction — one-piece flow (batch 1, few/no pre-made)",
         cfg.batch_size == 1 and cfg.premade <= 3),
        ("Motion — clean & labelled stations (5S)",
         cfg.five_s != "Disorganized"),
        ("Overprocessing — standard work in place",
         cfg.standard_level >= 1),
        ("Inventory — one-piece flow, pull replenishment, or FIFO rotation",
         cfg.pull_replenishment or cfg.fifo_rotation
         or (cfg.batch_size == 1 and cfg.premade == 0)),
        ("Defects — standard recipes and/or visual signals",
         cfg.visual_level >= 1 or cfg.standard_level >= 2),
        ("Waiting — bottleneck relieved (low walkouts) or capacity added",
         res.abandon_pct < 15 or cfg.employees > 3
         or cfg.blenders > 1 or capacity_maxed),
    ]
    done = sum(1 for _, x in items if x)
    return done, len(items), items


# The core simulation is "complete" only when ALL THREE objectives are met: every
# waste addressed, a high Lean Score, and a profitable shop. Both targets are set
# below what a well-run shop reaches in every random scenario (verified: optimized
# shops score 79-92 and profit $44-143), so the goal is always achievable.
LEAN_TARGET = CFG["lean_target"]      # Lean Score needed to finish (instructor-set)
PROFIT_TARGET = CFG["profit_target"]  # profit the shop must clear (instructor-set)


def objectives_status(cfg, res):
    """The three objectives that must ALL be true to finish the core sim."""
    done, total, items = lean_level(cfg, res)
    wastes_ok = done >= total
    score_ok = res.lean_score >= LEAN_TARGET
    profit_ok = res.profit > PROFIT_TARGET
    return dict(done=done, total=total, items=items, wastes_ok=wastes_ok,
                score_ok=score_ok, profit_ok=profit_ok,
                all_ok=wastes_ok and score_ok and profit_ok)


LADDER = pd.DataFrame([
    ["1", "Put steps in order (layout)", "Almost free", "High",
     "Arrange stations in the order used. Biggest bang for no buck."],
    ["2", "Organize & label (5S)", "Low", "High",
     "A tidy, labeled station means no hunting for the ice scoop."],
    ["3", "Standard recipes", "Low", "High",
     "One agreed way per drink → fewer mistakes, steadier speed."],
    ["4", "Visual order signals", "Low", "Medium",
     "A visible ticket rail so orders aren't lost or mixed up."],
    ["5", "Pull replenishment", "Low", "Medium",
     "Restock only what you use, so nothing spoils."],
    ["6", "One-piece flow", "Free", "High",
     "Make one drink at a time. Resist batching and pre-making."],
    ["7", "Add staff / equipment", "High", "Only if needed",
     "Costs money every shift — add ONLY where customers wait."],
], columns=["Do", "Change", "Cost", "Impact", "Why it's here"])


# End-of-game knowledge check. Each item: question, options, the correct option
# text (`answer`), and a one-line explanation shown after answering. Options are
# shuffled per session so the right answer isn't always in the same place.
DEBRIEF_QUIZ = [
    {"q": "Starting from a messy shop, which change usually delivers the MOST "
           "improvement per dollar — i.e. what should you do first?",
     "options": ["Put the stations in process order (fix the layout)",
                 "Buy the top-tier digital order screen",
                 "Hire two more baristas",
                 "Pre-make a big batch of drinks before the rush"],
     "answer": "Put the stations in process order (fix the layout)",
     "explain": "Ordering the line is almost free and removes backtracking — the "
                "highest-return move, which is why it's step 1 on the ladder."},
    {"q": "Making drinks before they're ordered (overproduction) mostly causes…",
     "options": ["Spoiled, unsold stock and more wrong drinks",
                 "Faster service with no real downside",
                 "Lower ingredient cost",
                 "Happier, more loyal customers"],
     "answer": "Spoiled, unsold stock and more wrong drinks",
     "explain": "Made-ahead drinks go stale or unsold and hide defects. "
                "Overproduction is the worst waste because it masks the others."},
    {"q": "Standard work (agreed recipes/method) helps mainly because it…",
     "options": ["Shrinks the variation in cycle time — fewer bad days — and cuts "
                 "defects",
                 "Guarantees the single fastest possible average time",
                 "Removes the need for any staff",
                 "Lets you safely increase batch size"],
     "answer": "Shrinks the variation in cycle time — fewer bad days — and cuts "
               "defects",
     "explain": "Standard work reduces the spread, not just the average — that's "
                "why it's the lean answer to managing variability."},
    {"q": "When is a lean improvement NOT worth doing?",
     "options": ["When its added cost is greater than the extra value it returns",
                 "Whenever it changes the current layout",
                 "Whenever it requires any training",
                 "Whenever it isn't the very cheapest option"],
     "answer": "When its added cost is greater than the extra value it returns",
     "explain": "Lean means value for least cost. If Δprofit < cost — often the "
                "premium tiers or spare capacity — drop it."},
    {"q": "The Inventory waste (5S 'Sustain') can be controlled by all of these "
           "EXCEPT which one?",
     "options": ["Ordering extra of everything, just in case",
                 "One-piece flow (make to order)",
                 "FIFO rotation (use the oldest stock first)",
                 "Pull replenishment (kanban — restock only what's used)"],
     "answer": "Ordering extra of everything, just in case",
     "explain": "Over-ordering is the opposite of sustaining low, fresh stock. "
                "One-piece flow, FIFO rotation and pull all keep inventory in check."},
]


# --------------------------------------------------------------------------
# Randomised, unique-but-solvable scenario for each session
# --------------------------------------------------------------------------
import random as _random


def make_scenario(seed):
    """Every student gets a slightly different (but always fixable) shop, so the
    best set of decisions differs from person to person."""
    rng = _random.Random(seed)
    order = list(PROCESS)
    rng.shuffle(order)
    # scenario-generation ranges are instructor-configurable via CFG (manifest.py)
    slow = rng.choice(CFG["slow_station_bias"])       # bias to the bottleneck
    slow_mult = round(rng.uniform(*CFG["slow_mult_range"]), 2)
    demand = rng.choice(CFG["demand_mix"])
    demand_mult = round(rng.uniform(*CFG["demand_mult_range"]), 2)
    patience = rng.choice(CFG["patience_choices"])
    defect_base = round(rng.uniform(*CFG["defect_base_range"]), 2)
    start_batch = rng.choice(CFG["start_batch_choices"])    # inherited over-batching
    start_premade = rng.choice(CFG["start_premade_choices"])  # inherited pre-made pile
    sid = f"{seed % 9000 + 1000}"                      # 4-digit scenario id

    demand_word = {"Light": "a steady trickle", "Normal": "a busy morning",
                   "Slammed": "an absolutely packed rush"}[demand]
    patience_word = ("patient today" if patience >= 165 else
                     ("average" if patience >= 140 else "in a real hurry"))
    quality_word = ("error-prone (new crew)" if defect_base >= 0.17
                    else "fairly reliable")
    briefing = (f"**Today's shop — scenario #{sid}.** You inherited a mess from "
                f"the last shift: the stations are **out of order**, and they were "
                f"**blending {start_batch} at a time** with **{start_premade} "
                f"pre-made cups** already sitting out. You're facing "
                f"**{demand_word}**; customers are **{patience_word}**; the crew is "
                f"**{quality_word}**. One station is running slow — the data will "
                "tell you which. Diagnose it and fix what matters most.")
    return dict(sid=sid, order=order, slow=slow, slow_mult=slow_mult,
                demand=demand, demand_mult=demand_mult, patience=patience,
                defect_base=defect_base, start_batch=start_batch,
                start_premade=start_premade, briefing=briefing)


# --------------------------------------------------------------------------
# state
# --------------------------------------------------------------------------
def _baseline_cfg(scenario):
    return dict(order=list(scenario["order"]), five_s="Disorganized",
               mode="Whole-order", employees=3, spec_prep=1, spec_blend=1,
               spec_finish=1, blenders=1, standard_level=0, visual_level=0,
               pull=False, fifo=False, batch=scenario["start_batch"],
               premade=scenario["start_premade"], demand=scenario["demand"],
               reps=8)


def _init_state(new_seed=None):
    if new_seed is not None or "round" not in st.session_state:
        # honour an explicit new seed, else a Director-provided ?seed=, else a
        # stable per-student seed derived from the student id, else random.
        seed = (new_seed if new_seed is not None
                else (CTX["seed"] if CTX["seed"] is not None
                      else (store.derive_seed(game, sid, lo=0, hi=10**6) if sid
                            else _random.randint(0, 10**6))))
        sc = make_scenario(seed)
        st.session_state.scenario = sc
        st.session_state.round = 1
        st.session_state.history = []
        st.session_state.last_result = None
        st.session_state.last_cfg = None
        st.session_state.cfg = _baseline_cfg(sc)
        st.session_state.game_mode = "Guided"
        st.session_state.baseline = {}
        st.session_state.tested = []          # student-tested decisions (Socratic)
        st.session_state.staged = []          # changes implemented for next rush
        st.session_state.reflections = {}     # captured Socratic answers
        st.session_state.student = ""
        st.session_state.order_nonce = 0      # bumps to refresh the drag widget
        st.session_state.coach_q = {}         # cached coach question per round
        st.session_state.asked_coach = set()  # coach question ids already used


# ---- progress persistence (student_store) -----------------------------------
# Only these session-state keys are persisted/resumed. Transient objects
# (last_result, last_cfg, baseline), figures, RNGs and widget keys are excluded.
PROGRESS_KEYS = ["round", "history", "cfg", "scenario", "game_mode",
                 "reflections", "tested", "staged", "coach_q", "asked_coach",
                 "goal_reached_once", "student", "last_cdict", "last_seed"]


def _jsonable(o):
    """Recursively coerce to plain JSON: numpy -> python, sets -> sorted lists,
    DataFrames -> dict-of-lists, anything else -> str (never raises)."""
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, set):
        return sorted(_jsonable(v) for v in o)
    if o is None or isinstance(o, (str, bool, int, float)):
        return o
    if hasattr(o, "to_dict"):                 # pandas DataFrame / Series
        try:
            return o.to_dict("list")
        except Exception:
            try:
                return o.to_dict()
            except Exception:
                return str(o)
    if hasattr(o, "tolist"):                  # numpy array
        return _jsonable(o.tolist())
    if hasattr(o, "item"):                    # numpy scalar
        try:
            return o.item()
        except Exception:
            return str(o)
    return str(o)


def _progress_snapshot():
    ss = st.session_state
    return {k: _jsonable(ss[k]) for k in PROGRESS_KEYS if k in ss}


def _restore_progress(saved):
    for k in PROGRESS_KEYS:
        if k not in saved:
            continue
        v = saved[k]
        if k == "asked_coach":
            v = set(v or [])
        elif k == "coach_q" and isinstance(v, dict):
            v = {int(rk): rv for rk, rv in v.items()}   # JSON stringified int keys
        st.session_state[k] = v


def _autosave():
    """Persist the current snapshot, but only when it has actually changed, so a
    save happens on each meaningful step (answer, round, rush) and never on idle
    reruns. A no-op when storage is unconfigured or no student is identified."""
    if not (store.enabled() and sid):
        return
    snap = _progress_snapshot()
    sig = json.dumps(snap, sort_keys=True, separators=(",", ":"))
    if sig == st.session_state.get("_last_saved_sig"):
        return
    try:
        store.save(game, sid, snap)
        st.session_state["_last_saved_sig"] = sig
    except Exception:
        pass


def _clear_transient_state():
    """Drop per-round widget state and end-of-game flags so a New scenario /
    Restart truly starts clean (no stale answers, no report left unlocked)."""
    _pfx = ("coachmc_", "plancommit_", "helped_", "dquiz_", "debrief_",
            "roibtn_", "order_dnd_")
    _flags = {"dryrun_cache", "roirows", "goal_reached_once", "debrief_ready",
              "_completion_recorded", "_last_saved_sig", "last_cdict", "last_seed"}
    for k in list(st.session_state.keys()):
        if k in _flags or k.startswith(_pfx):
            st.session_state.pop(k, None)


_init_state()
# resume: overlay any saved progress exactly once per session, before the app
# binds C/SC from session_state below.
if store.enabled() and sid and not st.session_state.get("_restored"):
    _saved = store.load(game, sid)
    if _saved:
        _restore_progress(_saved)
    st.session_state["_restored"] = True
C = st.session_state.cfg
SC = st.session_state.scenario


def cfg_from_state(s):
    return sim.Config(
        employees=s["employees"], blenders=s["blenders"],
        assignment_mode=s["mode"], spec_prep=s["spec_prep"],
        spec_blend=s["spec_blend"], spec_finish=s["spec_finish"],
        layout=coords_from_order(s["order"]), five_s=s["five_s"],
        standard_level=s["standard_level"], visual_level=s["visual_level"],
        batch_size=s["batch"], pull_replenishment=s["pull"],
        fifo_rotation=s["fifo"],
        premade=s["premade"], demand_level=s["demand"], replications=s["reps"],
        time_mult={SC["slow"]: SC["slow_mult"]}, demand_mult=SC["demand_mult"],
        patience_mean=SC["patience"], defect_base=SC["defect_base"])


# Resume recovery: last_result / last_cfg are transient objects that are NOT
# saved, so after a browser refresh, an idle reconnect, or a signed-in return
# they are None even though the round has advanced. Rebuild them deterministically
# from the saved decision snapshot + seed, BEFORE the CHECK/ACT panel is rendered
# below, so the coach question reappears and the student can answer it and advance.
# (Previously the panel was skipped and the DO button stayed locked — "stuck".)
if (st.session_state.get("last_result") is None
        and st.session_state.get("last_cdict") is not None
        and st.session_state.get("history")):
    try:
        _lc = cfg_from_state(st.session_state["last_cdict"])
        st.session_state.last_cfg = _lc
        st.session_state.last_result = sim.run_simulation(
            _lc, base_seed=st.session_state.get("last_seed", 1000))
    except Exception:
        pass


# --------------------------------------------------------------------------
# Visuals.  Principle: figures hold ONLY short labels that fit inside their
# shapes; every sentence of explanation is rendered as Streamlit text beneath
# the image, so text can never overlap the graphics.
# --------------------------------------------------------------------------
def _tile(ax, x, y, s, w=0.66, h=0.52):
    ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                 boxstyle="round,pad=0.02,rounding_size=0.1", linewidth=1.4,
                 edgecolor="#264653",
                 facecolor="#ffd166" if s == "Pickup" else "#8ecae6", zorder=2))
    ax.text(x, y, STATION_ABBR[s], ha="center", va="center", fontsize=10,
            fontweight="bold", color="#264653", zorder=3)
    ax.add_patch(Circle((x - 0.23, y + 0.16), 0.1, facecolor="#264653",
                        zorder=4))
    ax.text(x - 0.23, y + 0.16, str(STEP_NO[s]), ha="center", va="center",
            fontsize=7, color="white", fontweight="bold", zorder=5)


def backtracks(order):
    xp = {s: i for i, s in enumerate(order)}
    return sum(1 for a, b in zip(PROCESS, PROCESS[1:]) if xp[b] < xp[a])


def flow_fig(order):
    """Pure flow diagram: numbered tiles, with forward (green) arrows arcing ABOVE
    the blocks and backtrack (red) arrows arcing BELOW — no overlap with tiles."""
    xpos = {s: i for i, s in enumerate(order)}
    n = len(order)
    fig, ax = plt.subplots(figsize=(7.4, 3.3))
    ax.set_xlim(-0.7, n - 0.3); ax.set_ylim(-1.85, 1.7); ax.axis("off")
    # arrows first (zorder 1) so the tiles (zorder 2) sit cleanly on top. Both
    # arc AWAY from the tiles: forward (green) bulges up above the blocks,
    # backtrack (red) starts/ends well below the blocks and bulges further down.
    for a, b in zip(PROCESS, PROCESS[1:]):
        xa, xb = xpos[a], xpos[b]
        if xb > xa:                              # forward → green, above the blocks
            color, y, rad = "#2a9d8f", 0.42, -0.28
        else:                                    # backtrack → red, below the blocks
            color, y, rad = "#e76f51", -0.62, -0.32
        ax.add_patch(FancyArrowPatch((xa, y), (xb, y),
                     connectionstyle=f"arc3,rad={rad}", arrowstyle="-|>",
                     mutation_scale=13, lw=2.0, color=color, zorder=1))
    for s, x in xpos.items():
        _tile(ax, x, 0.0, s)
    ax.text(-0.6, 1.5, "forward flow (good) ▲", ha="left", va="center",
            fontsize=8.5, fontweight="bold", color="#2a9d8f")
    ax.text(-0.6, -1.62, "backtracking = wasted motion ▼", ha="left", va="center",
            fontsize=8.5, fontweight="bold", color="#e76f51")
    ax.set_title("How a drink flows  (steps 1-2-3-4-5-6)",
                 fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig


def _cup(ax, x, y, color, w=0.20, h=0.15):
    ax.add_patch(FancyBboxPatch((x - w / 2, y), w, h,
                 boxstyle="round,pad=0.005,rounding_size=0.03", linewidth=0.7,
                 edgecolor="#555", facecolor=color, zorder=3))


def inventory_map_fig(order, res, cfg):
    """Shows WHERE stock piles up: prep at ingredients, WIP mid-line, made-ahead
    at pickup, and waiting customers at the counter."""
    xpos = {s: i for i, s in enumerate(order)}
    n = len(order)
    fig, ax = plt.subplots(figsize=(7.4, 4.0))
    ax.set_xlim(-0.7, n - 0.3); ax.set_ylim(-2.1, 2.3); ax.axis("off")
    for s, x in xpos.items():
        _tile(ax, x, 0.0, s)

    prep = 0 if cfg.pull_replenishment else 2 + (cfg.batch_size - 1)
    for s in ("Cups", "Fruit", "Ice"):
        x = xpos[s]
        for j in range(min(int(prep), 8)):
            _cup(ax, x, 0.42 + j * 0.19, "#a8dadc")      # prep stock (blue) above

    wip = int(round(res.avg_wip))
    mids = ["Blender", "Finish"]
    for k in range(min(wip, 12)):
        x = xpos[mids[k % 2]]
        _cup(ax, x, -0.42 - (k // 2) * 0.19, "#ffb703")  # WIP (amber) below

    pm = int(cfg.premade)
    xp = xpos["Pickup"]
    for j in range(min(pm, 10)):
        _cup(ax, xp, 0.42 + j * 0.19, "#e76f51")         # made-ahead (red) above

    npk = int(round(res.peak_queue))
    stress = min(1.0, res.abandon_pct / 45.0)
    ccol = plt.cm.RdYlGn_r(0.15 + 0.7 * stress)
    for i in range(min(npk, 15)):
        ax.scatter([xp - 0.28 + (i % 3) * 0.28], [-0.55 - (i // 3) * 0.17],
                   s=60, color=ccol, edgecolors="#333", zorder=4)
    ax.set_title("Where inventory piles up", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig


# Each of the 5 S's maps to a concrete decision the student makes in the shop.
FIVE_S_DECISIONS = [
    ("Sort", "Inventory: batch size & pre-made stock",
     lambda cfg: cfg.batch_size == 1 and cfg.premade <= 3,
     "Keep only what's needed — make one at a time, little or no pre-made stock."),
    ("Set in order", "Station layout (drag into process order)",
     lambda cfg: backtracks(cfg_layout_order(cfg)) == 0,
     "Stations sit in the exact order a drink is made — no backtracking."),
    ("Shine", "Clean & label level (housekeeping)",
     lambda cfg: cfg.five_s in ("Basic", "Full 5S"),
     "Clean, labeled stations so shortages and problems are visible."),
    ("Standardize", "Standard-work level",
     lambda cfg: cfg.standard_level >= 1,
     "One agreed recipe / method for every drink."),
    ("Sustain", "Pull replenishment",
     lambda cfg: cfg.pull_replenishment,
     "Systems keep the gains: restock only what's used, so nothing spoils."),
]


def five_s_status(cfg):
    """Return [(S name, done, which decision, what it does), ...] from the shop."""
    return [(nm, fn(cfg), dec, doing) for nm, dec, fn, doing in FIVE_S_DECISIONS]


def five_s_fig(cfg):
    """5S scoreboard driven by the student's actual decisions (not a slider)."""
    status = five_s_status(cfg)
    done_n = sum(1 for _, d, _, _ in status if d)
    tags = ["1S", "2S", "3S", "4S", "5S"]
    fig, ax = plt.subplots(figsize=(7.2, 1.6))
    ax.set_xlim(-0.5, 5); ax.set_ylim(-0.2, 1.2); ax.axis("off")
    for i, (name, done, _, _) in enumerate(status):
        ax.add_patch(FancyBboxPatch((i - 0.42, 0.05), 0.84, 0.9,
                     boxstyle="round,pad=0.02,rounding_size=0.08", linewidth=1.3,
                     edgecolor="#264653",
                     facecolor="#2a9d8f" if done else "#e9ecef", zorder=2))
        ax.text(i, 0.66, tags[i], ha="center", va="center", fontsize=12,
                fontweight="bold", color="white" if done else "#adb5bd")
        ax.text(i, 0.30, name, ha="center", va="center", fontsize=7.5,
                color="white" if done else "#868e96")
    ax.set_title(f"Your 5S progress: {done_n} / 5 in place", fontsize=11,
                 fontweight="bold")
    fig.tight_layout()
    return fig


def render_5s(cfg):
    """Show the 5S board + a line per S: status, what's done, which decision."""
    import streamlit as _st
    _st.pyplot(five_s_fig(cfg))
    for name, done, decision, doing in five_s_status(cfg):
        mark = "✅" if done else "⬜"
        _st.markdown(f"{mark} **{name}** — {doing}  \n"
                     f"&nbsp;&nbsp;&nbsp;*decision: {decision}*")


def seven_waste_fig(diag):
    """Visual dashboard of the seven wastes as a colored 4x2 tile grid."""
    col = {"green": "#2a9d8f", "amber": "#e9c46a", "red": "#e76f51"}
    word = {"green": "ok", "amber": "watch", "red": "problem"}
    fig, ax = plt.subplots(figsize=(7.4, 2.7))
    ax.set_xlim(-0.5, 4); ax.set_ylim(-2.4, 0.7); ax.axis("off")
    for i, dgn in enumerate(diag):
        r, c = i // 4, i % 4
        x, y = c, -r * 1.15
        ax.add_patch(FancyBboxPatch((x - 0.46, y - 0.5), 0.92, 0.95,
                     boxstyle="round,pad=0.02,rounding_size=0.08", linewidth=1.3,
                     edgecolor="#264653", facecolor=col[dgn["flag"]], zorder=2))
        ax.text(x, y + 0.16, dgn["waste"], ha="center", va="center", fontsize=8.5,
                fontweight="bold", color="white", zorder=3)
        ax.text(x, y - 0.22, word[dgn["flag"]], ha="center", va="center",
                fontsize=8, color="white", zorder=3)
    ax.set_title("The 7 wastes — status right now", fontsize=11, fontweight="bold")
    fig.tight_layout()
    return fig


def cycle_hist(cts, target=120):
    fig, ax = plt.subplots(figsize=(5.2, 2.7))
    if cts:
        ax.hist(cts, bins=20, color="#8ecae6", edgecolor="#264653")
        m = sum(cts) / len(cts)
        ax.axvline(m, color="#e76f51", lw=2, label=f"mean {m:.0f}s")
        ax.axvline(target, color="#2a9d8f", lw=2, ls="--", label=f"target {target}s")
        ax.legend(fontsize=8)
    ax.set_xlabel("customer cycle time (s)"); ax.set_ylabel("customers")
    fig.tight_layout()
    return fig


def impact_effort_chart(rows):
    fig, ax = plt.subplots(figsize=(5.8, 3.6))
    ax.axhline(0, color="#999", lw=1)
    for r in rows:
        worth = r["d_profit"] >= 1.0
        ax.scatter(r["added_cost"], r["d_profit"], s=90,
                   color="#2a9d8f" if worth else "#e76f51",
                   edgecolors="#264653", zorder=3)
        ax.annotate(r["short"], (r["added_cost"], r["d_profit"]),
                    fontsize=7, xytext=(4, 4), textcoords="offset points")
    ax.set_xlabel("cost to add ($/rush)  →  more expensive")
    ax.set_ylabel("extra profit ($/rush)")
    ax.set_title("Impact vs. effort — above the line pays for itself", fontsize=10)
    fig.tight_layout()
    return fig


# --------------------------------------------------------------------------
# "what should I do next" analyzer
# --------------------------------------------------------------------------
ANALYSIS_SEED = 777
ANALYSIS_REPS = 6


def _clone(cfg, **kw):
    c = copy.deepcopy(cfg)
    for k, v in kw.items():
        setattr(c, k, v)
    c.replications = ANALYSIS_REPS
    return c


def next_step_options(cfg, allowed=None):
    """Improvements still available on the current shop, limited to the wastes
    the student can act on THIS rush (`allowed`). Each carries its $/rush cost,
    the modified Config (for testing) and a `change` to apply it to state C."""
    def o(waste, name, short, cost, mod, change):
        return dict(waste=waste, name=name, short=short, cost=cost, mod=mod,
                    change=change)
    opts = []
    if order_distance(cfg_layout_order(cfg)) > order_distance(IDEAL_ORDER):
        opts.append(o("transport", "Line stations up in process order (Set in order)",
                      "Layout", 1.0, _clone(cfg, layout=coords_from_order(IDEAL_ORDER)),
                      {"order": list(IDEAL_ORDER)}))
    if cfg.batch_size > 1:
        opts.append(o("overproduction", "Stop batching — make one at a time (Sort)",
                      "No batch", 0.0, _clone(cfg, batch_size=1), {"batch": 1}))
    if cfg.premade > 0:
        opts.append(o("overproduction", "Stop pre-making drinks (Sort)", "No premade",
                      0.0, _clone(cfg, premade=0), {"premade": 0}))
    if cfg.five_s != "Full 5S":
        nxt = "Basic" if cfg.five_s == "Disorganized" else "Full 5S"
        opts.append(o("motion", f"Shine: raise clean-&-label to {nxt}", "5S+", 3.0,
                      _clone(cfg, five_s=nxt), {"five_s": nxt}))
    if cfg.standard_level < len(sim.STANDARD_LEVELS) - 1:
        nl = cfg.standard_level + 1
        inc = sim.STANDARD_LEVELS[nl]["cost"] - sim.STANDARD_LEVELS[cfg.standard_level]["cost"]
        opts.append(o("overprocessing", f"Standardize → {sim.STANDARD_LEVELS[nl]['name']}",
                      "Std+", inc, _clone(cfg, standard_level=nl), {"standard_level": nl}))
    if cfg.visual_level < len(sim.VISUAL_LEVELS) - 1:
        nl = cfg.visual_level + 1
        inc = sim.VISUAL_LEVELS[nl]["cost"] - sim.VISUAL_LEVELS[cfg.visual_level]["cost"]
        opts.append(o("defects", f"Visual signals → {sim.VISUAL_LEVELS[nl]['name']}",
                      "Vis+", inc, _clone(cfg, visual_level=nl), {"visual_level": nl}))
    if not cfg.fifo_rotation:
        opts.append(o("inventory", "Sustain: FIFO rotation (use oldest stock first)",
                      "FIFO", 1.0, _clone(cfg, fifo_rotation=True), {"fifo": True}))
    if not cfg.pull_replenishment:
        opts.append(o("inventory", "Sustain: add pull replenishment", "Pull", 3.0,
                      _clone(cfg, pull_replenishment=True), {"pull": True}))
    if cfg.blenders < 4:
        opts.append(o("waiting", "Buy another blender", "+Blender",
                      sim.COSTS["blender_per_rush"],
                      _clone(cfg, blenders=cfg.blenders + 1), {"blenders": "+1"}))
    if cfg.assignment_mode == "Whole-order" and cfg.employees < 6:
        wage = round(sim.COSTS["employee_per_min"] * sim.HORIZON_S / 60.0, 1)
        opts.append(o("waiting", "Hire another barista", "+Barista", wage,
                      _clone(cfg, employees=cfg.employees + 1), {"employees": "+1"}))
    if allowed is not None:
        opts = [op for op in opts if op["waste"] in allowed]
    return opts


def test_one_option(cfg, opt):
    """Run ONE chosen change vs the current shop and return the outcome only
    (no ranking, no 'best' verdict -- the student decides)."""
    cur = sim.run_simulation(_clone(cfg), base_seed=ANALYSIS_SEED)
    r = sim.run_simulation(opt["mod"], base_seed=ANALYSIS_SEED)
    return dict(name=opt["name"], short=opt["short"], added_cost=opt["cost"],
                d_profit=r.profit - cur.profit,
                d_score=r.lean_score - cur.lean_score,
                d_served=r.served - cur.served)


def baseline_ref(demand):
    if demand not in st.session_state.baseline:
        b = _baseline_cfg(SC); b["demand"] = demand; b["reps"] = 6
        st.session_state.baseline[demand] = sim.run_simulation(
            cfg_from_state(b), base_seed=555)
    return st.session_state.baseline[demand]


# --------------------------------------------------------------------------
# Socratic reflection questions (ask, don't tell)
# --------------------------------------------------------------------------
def cfg_layout_order(cfg):
    # recover left-to-right order from a coords layout {station:(0,i)}
    return [s for s, _ in sorted(cfg.layout.items(), key=lambda kv: kv[1][1])]


def plan_changes(old, new):
    """Human-readable list of what the current Plan changes vs the last rush."""
    ch = []
    if cfg_layout_order(old) != cfg_layout_order(new):
        ch.append(f"Line re-ordered (walk {order_distance(cfg_layout_order(old))}"
                  f"→{order_distance(cfg_layout_order(new))} steps)")
    if old.five_s != new.five_s:
        ch.append(f"Clean & label (Shine): {old.five_s} → {new.five_s}")
    if old.standard_level != new.standard_level:
        ch.append("Standard work: "
                  f"{sim.STANDARD_LEVELS[old.standard_level]['name']} → "
                  f"{sim.STANDARD_LEVELS[new.standard_level]['name']}")
    if old.visual_level != new.visual_level:
        ch.append("Visual signals: "
                  f"{sim.VISUAL_LEVELS[old.visual_level]['name']} → "
                  f"{sim.VISUAL_LEVELS[new.visual_level]['name']}")
    if old.pull_replenishment != new.pull_replenishment:
        ch.append(f"Pull replenishment: {'ON' if new.pull_replenishment else 'off'}")
    if old.fifo_rotation != new.fifo_rotation:
        ch.append(f"FIFO rotation: {'ON' if new.fifo_rotation else 'off'}")
    if old.batch_size != new.batch_size:
        ch.append(f"Batch size: {old.batch_size} → {new.batch_size}")
    if old.premade != new.premade:
        ch.append(f"Pre-made drinks: {old.premade} → {new.premade}")
    if old.assignment_mode != new.assignment_mode:
        ch.append(f"Staffing model → {new.assignment_mode}")
    if old.employees != new.employees:
        ch.append(f"Baristas: {old.employees} → {new.employees}")
    if old.blenders != new.blenders:
        ch.append(f"Blenders: {old.blenders} → {new.blenders}")
    return ch


def debrief_roi(final_cfg, scenario):
    """Leave-one-out: how much profit / Lean each of the student's improvements
    was actually adding to their FINAL shop (revealed only in the debrief)."""
    base = sim.run_simulation(_clone(final_cfg), base_seed=ANALYSIS_SEED)

    def contrib(name, cost, **revert):
        v = sim.run_simulation(_clone(final_cfg, **revert), base_seed=ANALYSIS_SEED)
        return dict(short=name, added_cost=cost,
                    d_profit=base.profit - v.profit,
                    d_score=base.lean_score - v.lean_score)
    rows = []
    if order_distance(cfg_layout_order(final_cfg)) < order_distance(list(scenario["order"])):
        rows.append(contrib("Order the line", 1.0,
                            layout=coords_from_order(list(scenario["order"]))))
    if final_cfg.five_s != "Disorganized":
        rows.append(contrib("5S / clean & label",
                            {"Basic": 3.0, "Full 5S": 6.0}[final_cfg.five_s],
                            five_s="Disorganized"))
    if final_cfg.standard_level > 0:
        rows.append(contrib("Standard work",
                            sim.STANDARD_LEVELS[final_cfg.standard_level]["cost"],
                            standard_level=0))
    if final_cfg.visual_level > 0:
        rows.append(contrib("Visual signals",
                            sim.VISUAL_LEVELS[final_cfg.visual_level]["cost"],
                            visual_level=0))
    if final_cfg.pull_replenishment:
        rows.append(contrib("Pull replenishment", 3.0, pull_replenishment=False))
    if final_cfg.fifo_rotation:
        rows.append(contrib("FIFO rotation", 1.0, fifo_rotation=False))
    if (final_cfg.batch_size < scenario["start_batch"]
            or final_cfg.premade < scenario["start_premade"]):
        rows.append(contrib("Sort out overproduction", 0.0,
                            batch_size=scenario["start_batch"],
                            premade=scenario["start_premade"]))
    if final_cfg.employees > 3 or final_cfg.blenders > 1:
        wage = sim.COSTS["employee_per_min"] * sim.HORIZON_S / 60.0
        cost = ((final_cfg.employees - 3) * wage
                + (final_cfg.blenders - 1) * sim.COSTS["blender_per_rush"])
        rows.append(contrib("Add capacity", max(0.0, cost),
                            employees=3, blenders=1))
    return rows


def _coach_bank(cfg, res):
    """Every possible coaching question. Each waste has SEVERAL questions so the
    coach can ask something fresh each round. Each item: id, `waste` (which unlocked
    decision it belongs to; 'any' = always allowed), a relevance flag, the MC
    question, options, the best index, guidance, a short `focus` directive and a
    `look` pointer to the on-screen info."""
    dr = res.defects / max(1.0, res.served)
    _over_rel = cfg.batch_size > 1 or cfg.premade > 3
    _trans_rel = backtracks(cfg_layout_order(cfg)) > 0
    _motion_rel = cfg.five_s == "Disorganized"
    _proc_rel = cfg.standard_level == 0
    _def_rel = dr > 0.08
    _inv_rel = (not cfg.pull_replenishment and not cfg.fifo_rotation
                and not (cfg.batch_size == 1 and cfg.premade == 0))
    _wait_rel = res.abandon_pct > 15
    _over_focus = "Sort — drop batch size to 1 and pre-made toward 0"
    _over_look = "the inventory map (red stack at pickup) + the Waste number"
    _over_guide = ("A made-ahead drink only helps if it matches the *next* order — "
                   "otherwise it's stale (wrong) or binned (waste). 👉 In the "
                   "**Overproduction** decision drop batch size to 1 and pre-made "
                   "to 0.")
    _trans_focus = "Set in order — drag stations into process order (all green)"
    _trans_look = "the flow diagram (red vs green arrows) + Walking-per-drink"
    _trans_guide = ("Red arrows are the drink travelling *backward*. 👉 Open the "
                    "**Transport** decision and drag the stations into "
                    "CUP→FRT→ICE→BLD→FIN→PICK order until every arrow is green — "
                    "nearly free, and it cuts cycle time.")
    _motion_focus = "Shine — raise clean-&-label (5S) so nothing is hunted for"
    _motion_look = "the 5S board (is 3S Shine grey?) + cycle time"
    _motion_guide = ("Searching for things is **Motion** waste. 👉 Raise the "
                     "**Motion / Shine** decision to Basic or Full 5S so every item "
                     "has a labeled home.")
    _proc_focus = "Standardize — pick a standard-work level (start cheap)"
    _proc_look = "the cycle-time spread and the Wrong-orders metric"
    _proc_guide = ("Inconsistent steps are **Overprocessing**. 👉 Set the "
                   "**Overprocessing / Standardize** decision to at least 'Recipe "
                   "cards' — cheap, and it cuts both time *and* errors.")
    _def_focus = "Defects — add a cheap visual signal level (not the top tier)"
    _def_look = "the Wrong-orders metric + the Rework & refunds cost line"
    _def_guide = ("Cheap **standard work + a basic visible ticket** attack the root "
                  "cause. 👉 Nudge the **Defects / visual-signal** decision up ONE "
                  "level (not the top) and check standard work is on.")
    _inv_focus = "Sustain — one-piece flow, FIFO rotation, or pull (cheapest that works)"
    _inv_look = "the Waste number + the Waste/spoilage cost line"
    _inv_guide = ("Three **Sustain** moves work — pick the cheapest that does the "
                  "job. 👉 **One-piece flow** (batch 1, no pre-made) is free; **FIFO "
                  "rotation** ($1) keeps held stock fresh; **pull / kanban** ($3) "
                  "restocks only what's used.")
    _wait_focus = "Waiting — relieve the bottleneck (test capacity before buying)"
    _wait_look = "the congestion chart + the inventory map (where WIP stacks)"
    _wait_guide = ("Find the **bottleneck** — the station with WIP stacked in front "
                   "of it. 👉 In your **Plan** add ONE blender or barista there and "
                   "keep it only if profit rises. Capacity elsewhere is pure cost.")

    def q(id, waste, relevant, question, options, best, guide, focus, look):
        return dict(id=id, waste=waste, relevant=relevant, q=question,
                    options=options, best=best, guidance=guide, focus=focus,
                    look=look)

    return [
        # ---- Overproduction ----
        q("overproduction_1", "overproduction", _over_rel,
          (f"This rush you wasted **{res.waste:.0f}** ingredients and made "
           f"**{res.defects:.0f}** wrong drinks. What is making drinks *before "
           "they're ordered* mostly causing?"),
          ["Waste and wrong drinks (overproduction)",
           "Faster service with no real downside",
           "Lower ingredient cost", "Happier, more loyal customers"], 0,
          _over_guide, _over_focus, _over_look),
        q("overproduction_2", "overproduction", _over_rel,
          "You pre-made a stack of drinks 'to save time,' but many end up unsold or "
          "wrong. Which lean principle does that violate?",
          ["One-piece flow — make to the actual order",
           "Economies of scale — always batch bigger",
           "Just-in-case stocking is safest", "The customer is always wrong"], 0,
          _over_guide, _over_focus, _over_look),
        q("overproduction_3", "overproduction", _over_rel,
          "Dropping batch size to 1 and pre-made to 0 will MOST directly reduce…",
          ["Overproduction — spoilage and wrong drinks",
           "Your rent", "Customer patience", "Walking distance"], 0,
          _over_guide, _over_focus, _over_look),
        # ---- Transport / layout ----
        q("transport_1", "transport", _trans_rel,
          "Your flow diagram shows **red arrows**. What do they tell you?",
          ["The drink moves backward = wasted walking (Transport)",
           "The shop is very busy", "Orders are being made wrong",
           "The blender is broken"], 0,
          _trans_guide, _trans_focus, _trans_look),
        q("transport_2", "transport", _trans_rel,
          "A single drink crosses back and forth across the shop. What is the "
          "*cheapest* way to cut that walking?",
          ["Re-order the stations into the make sequence (Set in order)",
           "Buy a conveyor belt", "Hire a runner to fetch things",
           "Make the drinks ahead of time"], 0,
          _trans_guide, _trans_focus, _trans_look),
        q("transport_3", "transport", _trans_rel,
          "Which of the 5 S's puts every station into the sequence a drink is "
          "actually made in?",
          ["Set in order (#2)", "Sort (#1)", "Shine (#3)", "Sustain (#5)"], 0,
          _trans_guide, _trans_focus, _trans_look),
        # ---- Motion ----
        q("motion_1", "motion", _motion_rel,
          "Workers keep hunting for tools and ingredients. Which waste is that, and "
          "the cheap fix?",
          ["Motion — fix with 5S clean & label",
           "Transport — buy a conveyor", "Defects — hire a checker",
           "Waiting — add three baristas"], 0,
          _motion_guide, _motion_focus, _motion_look),
        q("motion_2", "motion", _motion_rel,
          "Ingredients have no labeled home, so staff search on every fetch. The "
          "leanest fix is to…",
          ["Give each item a labeled home (5S Set-in-order / Shine)",
           "Hire more staff to search faster", "Make bigger batches",
           "Buy a second blender"], 0,
          _motion_guide, _motion_focus, _motion_look),
        # ---- Overprocessing ----
        q("overprocessing_1", "overprocessing", _proc_rel,
          "Every barista makes each drink a slightly different, longer way. The "
          "leanest fix is…",
          ["Standard work — one agreed recipe/method",
           "Let everyone keep improvising", "Buy a second blender",
           "Make drinks ahead to save time"], 0,
          _proc_guide, _proc_focus, _proc_look),
        q("overprocessing_2", "overprocessing", _proc_rel,
          "Two baristas make the same drink two different ways at two speeds. "
          "Standard work mainly gives you…",
          ["A consistent, repeatable method (steady time, fewer errors)",
           "A bigger menu", "Cheaper rent", "Permission to batch more"], 0,
          _proc_guide, _proc_focus, _proc_look),
        # ---- Defects ----
        q("defects_1", "defects", _def_rel,
          (f"About **{dr*100:.0f}%** of drinks came out wrong. Which is the "
           "*cheapest* effective way to cut that?"),
          ["Agree one standard recipe + a visible ticket",
           "Buy the most expensive order screen",
           "Hire another barista", "Make more drinks in advance"], 0,
          _def_guide, _def_focus, _def_look),
        q("defects_2", "defects", _def_rel,
          "Wrong drinks get remade — that's rework. The two cheapest root-cause "
          "fixes are…",
          ["Standard recipes + a visible order ticket",
           "A bigger blender + more ice",
           "Pre-making + batching", "Lower prices"], 0,
          _def_guide, _def_focus, _def_look),
        # ---- Inventory / Sustain ----
        q("inventory_1", "inventory", _inv_rel,
          "How do you stop the shop quietly drifting back to overstocked, stale "
          "stock between rushes?",
          ["Sustain it — one-piece flow, FIFO rotation, or pull",
           "Order extra of everything, just in case",
           "Make a big batch at open", "Nothing — it fixes itself"], 0,
          _inv_guide, _inv_focus, _inv_look),
        q("inventory_2", "inventory", _inv_rel,
          "Prep sits and spoils between rushes. Which is the CHEAPEST way to keep "
          "the stock you do hold fresh?",
          ["FIFO rotation — use the oldest stock first",
           "Pull / kanban replenishment", "Buy a bigger fridge",
           "Order more stock so you never run out"], 0,
          _inv_guide, _inv_focus, _inv_look),
        # ---- Waiting ----
        q("waiting_1", "waiting", _wait_rel,
          (f"**{res.abandon_pct:.0f}%** of customers walked out. Where do you look "
           "FIRST, before spending money on staff or blenders?"),
          ["The station where work is piling up (the bottleneck)",
           "Add staff everywhere at once", "Lower your prices",
           "Make more drinks ahead of time"], 0,
          _wait_guide, _wait_focus, _wait_look),
        q("waiting_2", "waiting", _wait_rel,
          "A queue builds at ONE station. Adding a barista at a DIFFERENT station "
          "will…",
          ["Not help — add capacity only at the bottleneck",
           "Fix the queue instantly", "Reduce wrong drinks",
           "Cut your rent"], 0,
          _wait_guide, _wait_focus, _wait_look),
        # ---- Profit / optimisation (always available) ----
        q("profit_1", "any", True,
          "Your flow is fairly clean. What should guide your last moves to get BOTH "
          "a high Lean Score and high profit?",
          ["Keep only changes whose extra profit beats their cost",
           "Add every improvement to the max level",
           "Buy as much capacity as possible",
           "Pre-make drinks to serve faster"], 0,
          ("Lean means value for least cost. 👉 Use the **ACT** dry-run: keep "
           "changes with a **positive Δ profit**, drop the ones that cost more than "
           "they return (often the top tiers and spare capacity)."),
          "Optimize — keep only changes that raise profit AND score",
          "the ACT dry-run (Δ profit of your plan) + the Costs / ROI tab"),
        q("profit_2", "any", True,
          "Two changes both raise the Lean Score, but you can only afford one. How "
          "should you choose?",
          ["Take the one with the higher extra profit per dollar",
           "Take whichever is newest", "Take the most expensive one",
           "Pick at random"], 0,
          ("Rank by return on cost. 👉 The **profit-impact test** and the ACT "
           "dry-run show Δ profit per change — spend where each dollar buys the "
           "most."),
          "Optimize — spend where each dollar returns the most",
          "the profit-impact test (sorted by Δ profit) + the Costs / ROI tab"),
    ]


def _waste_damage(waste, cfg, res):
    """Rough estimate of how much a given waste is hurting the Lean Score right
    now (bigger = worse). Used to weight the coach toward the biggest problem."""
    if waste == "overproduction":
        return (res.waste * 0.8 + res.defects * 0.5) if (
            cfg.batch_size > 1 or cfg.premade > 3) else 0.0
    if waste == "transport":
        # tie the "damage" to actual backtracking so the coach flags a scrambled
        # line even when total distance happens to match the ideal.
        bt = backtracks(cfg_layout_order(cfg))
        extra = max(0.0, order_distance(cfg_layout_order(cfg))
                    - order_distance(IDEAL_ORDER))
        return bt * 6.0 + extra * 0.9
    if waste == "motion":
        return {"Disorganized": 8.0, "Basic": 3.0, "Full 5S": 0.0}[cfg.five_s]
    if waste == "overprocessing":
        return 10.0 if cfg.standard_level == 0 else 0.0
    if waste == "defects":
        return res.defects * 1.0
    if waste == "inventory":
        addressed = (cfg.pull_replenishment or cfg.fifo_rotation
                     or (cfg.batch_size == 1 and cfg.premade == 0))
        return 0.0 if addressed else res.waste * 0.6
    if waste == "waiting":
        # no point flagging Waiting if capacity is already maxed out
        if cfg.employees >= 6 and cfg.blenders >= 4:
            return 0.0
        return res.abandon_pct * 0.5
    return 0.0


def _profit_by_waste(cfg, allowed):
    """For each unlocked waste, the biggest profit/rush its counter-measure would
    add right now (max over that waste's available options). Drives the coach toward
    the most *profitable* next fix when several are on the table."""
    out = {}
    base = sim.run_simulation(_clone(cfg), base_seed=ANALYSIS_SEED)
    for opt in next_step_options(cfg, allowed=allowed):
        r = sim.run_simulation(opt["mod"], base_seed=ANALYSIS_SEED)
        dp = r.profit - base.profit
        out[opt["waste"]] = max(out.get(opt["waste"], -1e9), dp)
    return out


def coach_mc(cfg, res, diag, allowed, asked):
    """Pick ONE multiple-choice question. When several wastes are actionable, target
    the one whose counter-measure adds the MOST profit right now (so the coach points
    at the biggest-payoff move); fall back to whichever waste is hurting the Lean
    Score most. Within the target waste, prefer a question the student hasn't seen
    yet, and tag the chosen question with `target_waste` so its decision can be
    opened. Falls back to a profit-optimisation prompt when nothing is actionable."""
    allowed = allowed or set(WASTE_KEYS)
    pool = [q for q in _coach_bank(cfg, res)
            if q["relevant"] and (q["waste"] == "any" or q["waste"] in allowed)]
    if not pool:                                  # 'profit' items are always relevant
        pool = [q for q in _coach_bank(cfg, res) if q["waste"] == "any"]

    by_waste = {}
    for q in pool:
        by_waste.setdefault(q["waste"], []).append(q)

    def pick(w):                                  # unseen question for waste w, else first
        chosen = next((q for q in by_waste[w] if q["id"] not in asked), by_waste[w][0])
        chosen = dict(chosen)
        chosen["target_waste"] = None if w == "any" else w
        return chosen

    actionable = {w for w in by_waste if w != "any"}
    # 1) prefer the actionable waste with the biggest profit improvement available
    if actionable:
        profit = _profit_by_waste(cfg, actionable)
        gainful = sorted([w for w in actionable if profit.get(w, 0.0) > 0.5],
                         key=lambda w: -profit[w])
        if gainful:
            fresh = [w for w in gainful
                     if any(q["id"] not in asked for q in by_waste[w])]
            return pick(fresh[0] if fresh else gainful[0])

    # 2) otherwise target whichever waste is hurting the Lean Score most
    dmg = {w: _waste_damage(w, cfg, res) for w in actionable}
    hurting = sorted([w for w, d in dmg.items() if d > 0], key=lambda w: -dmg[w])
    if hurting:
        fresh = [w for w in hurting
                 if any(q["id"] not in asked for q in by_waste[w])]
        return pick(fresh[0] if fresh else hurting[0])

    any_qs = by_waste.get("any") or pool
    chosen = dict(next((q for q in any_qs if q["id"] not in asked), any_qs[0]))
    chosen["target_waste"] = None
    return chosen


# --------------------------------------------------------------------------
# LMS progress report (downloadable HTML + CSV)
# --------------------------------------------------------------------------
def _report_context():
    hist = st.session_state.history
    best = max((h["lean_score"] for h in hist), default=0)
    final = hist[-1]["lean_score"] if hist else 0
    first = hist[0]["lean_score"] if hist else 0
    base = baseline_ref(SC["demand"])
    final_profit = hist[-1]["profit"] if hist else base.profit
    return dict(hist=hist, best=best, final=final, first=first,
                gain=final - first, base=base, final_profit=final_profit,
                improvement=final_profit - base.profit)


def build_report_pdf():
    """A clean, auto-paginating multi-page PDF report (no external libraries). A
    small flowing-text engine tracks a vertical cursor and starts a fresh page
    whenever a block wouldn't fit, so nothing is ever truncated or overlapped."""
    import io as _io
    import textwrap as _tw
    import datetime as _dt
    from matplotlib.backends.backend_pdf import PdfPages
    from matplotlib.lines import Line2D
    from matplotlib.patches import FancyBboxPatch, Rectangle

    ctx = _report_context()
    refl = st.session_state.reflections
    name = st.session_state.student or "(name not entered)"
    today = _dt.date.today().strftime("%B %d, %Y")

    LEFT, RIGHT, TOP, BOT = 0.09, 0.91, 0.90, 0.075
    TEAL, DARK, GREY, LGREY, LINE = ("#2a9d8f", "#264653", "#5f6b6b",
                                     "#9aa0a0", "#e2e6e6")
    S = {"fig": None, "y": TOP, "page": 0}
    buf = _io.BytesIO()
    pdf = PdfPages(buf)

    def rule(y, color=LINE, lw=0.8, x0=LEFT, x1=RIGHT):
        S["fig"].add_artist(Line2D([x0, x1], [y, y], transform=S["fig"].transFigure,
                                   color=color, lw=lw))

    def _finish_page():
        if S["fig"] is None:
            return
        f = S["fig"]
        rule(0.055)
        f.text(LEFT, 0.039, "Juicetification: The Lean Rush", fontsize=7.5, color=LGREY)
        f.text(RIGHT, 0.039, f"Page {S['page']}", fontsize=7.5, color=LGREY,
               ha="right")
        pdf.savefig(f)
        plt.close(f)

    def new_page():
        _finish_page()
        f = plt.figure(figsize=(8.5, 11))
        f.patch.set_facecolor("white")
        S["fig"] = f
        S["page"] += 1
        S["y"] = TOP
        if S["page"] > 1:                        # running header on later pages
            f.text(LEFT, 0.955, "Juicetification: The Lean Rush — Report",
                   fontsize=9.5, color=TEAL, fontweight="bold")
            f.text(RIGHT, 0.955, name, fontsize=8.5, color=GREY, ha="right")
            rule(0.945)
            S["y"] = 0.925
        return f

    def ensure(dy):
        if S["y"] - dy < BOT:
            new_page()

    def para(s, size=9.2, color="#2c2c2c", bold=False, italic=False,
             indent=0.0, after=0.004, lh=None):
        lh = lh or (size / 850.0 + 0.005)
        # wrap width from real font metrics (8.5in page) so text never runs past
        # the right margin, whatever the size / weight / indent.
        charw = (size / 72.0 / 8.5) * (0.63 if bold else 0.57)
        maxchars = max(12, int((RIGHT - LEFT - indent) / charw))
        for line in (_tw.wrap(s, maxchars) or [""]):
            ensure(lh)
            S["fig"].text(LEFT + indent, S["y"], line, fontsize=size, color=color,
                          fontweight="bold" if bold else "normal",
                          style="italic" if italic else "normal")
            S["y"] -= lh
        S["y"] -= after

    def heading(s, gap_before=0.018):
        S["y"] -= gap_before
        ensure(0.04)
        S["fig"].text(LEFT, S["y"], s, fontsize=12.5, color=DARK, fontweight="bold")
        S["y"] -= 0.009
        rule(S["y"], color=TEAL, lw=1.4)
        S["y"] -= 0.017

    def qa_section(title, items, intro=None, round_tag=False):
        heading(title)
        if intro:
            para(intro, size=8.6, color=GREY, italic=True, after=0.009)
        if not items:
            para("None recorded.", size=9, color=LGREY)
            return
        for k, v in items:
            q = v["q"]
            if round_tag and k[:1] == "R" and k.split(" ")[0][1:].isdigit():
                q = f"Round {k.split(' ')[0][1:]} — {q}"
            para(q, size=9.2, color=DARK, bold=True, after=0.002)
            para(v["a"], size=9.2, color="#2c2c2c", indent=0.022, after=0.010)

    # ---------------- PAGE 1: title band, meta, KPIs, tables ----------------
    new_page()
    f = S["fig"]
    f.add_artist(Rectangle((0, 0.917), 1.0, 0.083, transform=f.transFigure,
                           facecolor=TEAL, edgecolor="none", zorder=0))
    f.text(LEFT, 0.947, "Juicetification: The Lean Rush", fontsize=20,
           color="white", fontweight="bold")
    f.text(LEFT, 0.927, "Lean Operations Simulation — Student Report",
           fontsize=10.5, color="#dff3ef")
    S["y"] = 0.892
    para(f"Student:  {name}", size=10.5, color=DARK, bold=True, after=0.002)
    para(f"Scenario #{SC['sid']}    ·    Demand: {SC['demand']}    ·    {today}",
         size=9.5, color=GREY, after=0.011)
    para(SC["briefing"].replace("**", ""), size=8.8, color=GREY, after=0.006)

    # KPI cards
    ensure(0.09)
    kpis = [("Rounds", f"{len(ctx['hist'])}"), ("Best Lean", f"{ctx['best']:.0f}"),
            ("Final Lean", f"{ctx['final']:.0f}"), ("Lean gain", f"{ctx['gain']:+.0f}"),
            ("Profit vs messy", f"${ctx['improvement']:+.0f}")]
    gap = 0.012
    cardw = (RIGHT - LEFT - 4 * gap) / 5.0
    cy = S["y"] - 0.062
    for i, (k, v) in enumerate(kpis):
        cx = LEFT + i * (cardw + gap)
        f.add_artist(FancyBboxPatch((cx, cy), cardw, 0.058,
                     boxstyle="round,pad=0.003,rounding_size=0.010",
                     transform=f.transFigure, facecolor="#f2f8f7",
                     edgecolor=TEAL, lw=1.0, mutation_aspect=0.5))
        f.text(cx + cardw / 2, cy + 0.037, v, fontsize=15, color=DARK,
               fontweight="bold", ha="center", va="center")
        f.text(cx + cardw / 2, cy + 0.014, k, fontsize=7.6, color=GREY,
               ha="center", va="center")
    S["y"] = cy - 0.018

    heading("Round-by-round performance")
    if ctx["hist"]:
        cols = ["Rd", "Lean", "Cycle", "Served", "Wrong", "Waste", "Lost%",
                "Upkeep", "Profit"]
        cells = [[h["round"], f"{h['lean_score']:.0f}", f"{h['avg_cycle']:.0f}s",
                  f"{h['served']:.0f}", f"{h['defects']:.0f}", f"{h['waste']:.0f}",
                  f"{h['abandon_pct']:.0f}%", f"${h['upkeep']:.0f}",
                  f"${h['profit']:.0f}"] for h in ctx["hist"]]
        rowh = 0.025
        th = rowh * (len(cells) + 1)
        ensure(th + 0.02)
        axb = S["y"] - th
        ax = f.add_axes([LEFT, axb, RIGHT - LEFT, th])
        ax.axis("off")
        tbl = ax.table(cellText=cells, colLabels=cols, loc="center",
                       cellLoc="center")
        tbl.auto_set_font_size(False)
        tbl.set_fontsize(8.5)
        tbl.scale(1, 1.25)
        for (r, c), cell in tbl.get_celld().items():
            cell.set_edgecolor("#d9dede")
            if r == 0:
                cell.set_facecolor(TEAL)
                cell.set_text_props(color="white", weight="bold")
            elif r % 2 == 0:
                cell.set_facecolor("#f4f8f7")
        S["y"] = axb - 0.006

    heading("Decisions made each round")
    for h in ctx["hist"]:
        para(f"Round {h['round']}:  {h.get('decisions', '—') or '—'}",
             size=8.8, color="#2c2c2c", after=0.003)

    # ---------------- flowing reflection / knowledge sections ----------------
    coach = [(k, v) for k, v in refl.items() if k.endswith("coach")]
    preds = [(k, v) for k, v in refl.items() if "plan prediction" in k]
    debrief = [(k, v) for k, v in refl.items() if k.startswith("Debrief")]
    quiz = [(k, v) for k, v in refl.items() if k.startswith("Knowledge check")]

    qa_section("Coaching Kata — your obstacle diagnoses", coach,
               "Each round you named the biggest obstacle before deciding.",
               round_tag=True)
    qa_section("Round predictions (PLAN · commit)", preds, round_tag=True)
    qa_section("Debrief reflections", debrief,
               "Your written synthesis across the whole game.")
    qa_section("Knowledge check", quiz,
               "End-of-game multiple-choice check of the core lean concepts.")

    _finish_page()
    pdf.close()
    buf.seek(0)
    return buf.getvalue()


# --------------------------------------------------------------------------
# sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    st.header("🥤 Juicetification: The Lean Rush")
    st.session_state.student = st.text_input(
        "Your name / student ID", value=st.session_state.get("student", ""),
        placeholder="e.g., Jordan Lee — 100xxxxx")
    st.caption(f"Scenario #{SC['sid']}")
    cM1, cM2 = st.columns(2)
    cM1.metric("Round", st.session_state.round)
    best = max((h["lean_score"] for h in st.session_state.history), default=0)
    cM2.metric("Best Lean Score", f"{best:.0f}")

    # ---- RUN button lives here, big and obvious; flashes when ready ----
    _lr = st.session_state.history[-1]["round"] if st.session_state.history else None
    _ck = f"coachmc_{_lr}" if _lr else None
    need_coach = bool(_lr) and st.session_state.get(_ck) is None
    # you must also COMMIT a plan (predict) before you can run the next rush
    _pck = f"plancommit_{st.session_state.round}"
    need_plan = bool(_lr) and st.session_state.get(_pck) is None
    need_run = need_coach or need_plan
    if not need_run:
        st.markdown(
            "<style>@keyframes jrpulse{0%{box-shadow:0 0 0 0 rgba(42,157,143,.7);}"
            "70%{box-shadow:0 0 0 16px rgba(42,157,143,0);}"
            "100%{box-shadow:0 0 0 0 rgba(42,157,143,0);}}"
            'section[data-testid="stSidebar"] button[kind="primary"]'
            "{animation:jrpulse 1.1s infinite;border-radius:8px;}</style>",
            unsafe_allow_html=True)
    run = st.button(f"▶️  DO — run the rush  (Round {st.session_state.round})",
                    type="primary", use_container_width=True, disabled=need_run)
    if need_coach:
        st.caption("🔒 Step 1: **answer the coach** at the top (Act on your result).")
        jr_jump_button("⬆️ Go to the coach's question", height=56)
    elif need_plan:
        st.caption("🔒 Step 2: **make & commit your plan** on the right, then run.")
    else:
        st.caption("✅ Plan committed — press **DO** to run the rush.")

    # PDCA tracker — highlights the phase for the section you're scrolled to
    import streamlit.components.v1 as _components
    _components.html("""
<div style="font-family:sans-serif;text-align:center">
  <div style="font-weight:700;color:#264653;margin-bottom:6px">PDCA · kaizen ↻</div>
  <div id="p-CHECK" class="pchip">🔍 CHECK</div>
  <div style="color:#bbb">↓</div>
  <div id="p-ACT" class="pchip">🥋 ACT</div>
  <div style="color:#bbb">↓</div>
  <div id="p-PLAN" class="pchip">📝 PLAN</div>
  <div style="color:#bbb">↓</div>
  <div id="p-DO" class="pchip">▶️ DO</div>
  <div style="color:#bbb;font-size:11px;margin-top:4px">…loops back to CHECK</div>
</div>
<style>
.pchip{padding:6px 4px;margin:3px 6px;border-radius:7px;background:#eceff1;
 color:#90a4ae;font-weight:700;font-size:13px;transition:.15s}
.pchip.on{background:#2a9d8f;color:#fff;box-shadow:0 0 0 3px rgba(42,157,143,.25)}
</style>
<script>
var P=window.parent,D=P.document;
function jrPhase(){
  var order=['CHECK','ACT','PLAN','DO'];
  var active='CHECK';
  order.forEach(function(k){
    var el=D.getElementById('jr-'+k.toLowerCase());
    if(el && el.getBoundingClientRect().top <= 170){ active=k; }
  });
  order.forEach(function(k){var c=document.getElementById('p-'+k);
    if(c)c.className='pchip'+(k===active?' on':'');});
}
P.addEventListener('scroll',function(){P.requestAnimationFrame(jrPhase);},true);
setInterval(jrPhase,300);jrPhase();
</script>
""", height=260)
    st.divider()

    st.session_state.game_mode = st.radio(
        "Game mode", ["Guided", "Free play"],
        index=0 if st.session_state.game_mode == "Guided" else 1,
        help="Guided walks you through the wastes; Free play unlocks everything.")

    with st.expander("What is 'lean'? (start here)"):
        st.markdown(
            "**Lean** means giving customers what they want with as little wasted "
            "effort as possible. Anything that doesn't add value — walking, "
            "waiting, mistakes, extra stock — is **waste**, and lean is the habit "
            "of removing it.\n\nNo background needed. Each round hands you one "
            "tool, you try it, and you watch the numbers move. Watch three: "
            "**cycle time**, **customers lost**, and **profit**.")

    with st.expander("Scenario settings (instructor)"):
        st.caption("Demand is set by today's random scenario, but you can "
                   "override it here.")
        C["demand"] = st.select_slider("Demand intensity",
                                       ["Light", "Normal", "Slammed"],
                                       value=C["demand"])
        C["reps"] = st.slider("Replications", 3, 20, C["reps"])

    with st.expander("Mini-glossary"):
        st.markdown(
            "- **Cycle time** – total wait, order to drink.\n"
            "- **WIP** – drinks in progress at once (clutter).\n"
            "- **5S** – Sort, Set-in-order, Shine, Standardize, Sustain.\n"
            "- **Standard work** – one agreed best way to do a task.\n"
            "- **Bottleneck** – the slowest step; it caps the whole shop.\n"
            "- **Overproduction** – making more/earlier than needed.")

    student_name = st.session_state.student
    cN, cR = st.columns(2)
    if cN.button("🎲 New scenario", use_container_width=True,
                 help="A fresh random shop — different demand, twist, and layout."):
        _clear_transient_state()
        _init_state(new_seed=_random.randint(0, 10**6))
        st.session_state.scroll_top = True
        st.rerun()
    if cR.button("🔄 Restart", use_container_width=True,
                 help="Same scenario, start the rounds over."):
        sc = st.session_state.scenario
        _clear_transient_state()
        st.session_state.round = 1
        st.session_state.history = []
        st.session_state.last_result = None
        st.session_state.last_cfg = None
        st.session_state.cfg = _baseline_cfg(sc)
        st.session_state.baseline = {}
        st.session_state.tested = []
        st.session_state.staged = []
        st.session_state.reflections = {}
        st.session_state.coach_q = {}
        st.session_state.asked_coach = set()
        st.session_state.order_nonce += 1
        st.session_state.scroll_top = True
        st.rerun()


guided = st.session_state.game_mode == "Guided"
rnd = st.session_state.round
# have the objectives already been met? (last rush's shop, if any)
_lr_res = st.session_state.last_result
_lr_cfg = st.session_state.last_cfg
_completed = (_lr_res is not None and _lr_cfg is not None
              and objectives_status(_lr_cfg, _lr_res)["all_ok"])
if not guided:
    plan = FREE_PLAY
elif _completed:
    plan = DONE_PLAN                      # all 3 objectives met — don't nag
elif rnd in ROUND_PLAN:
    plan = ROUND_PLAN[rnd]
else:
    plan = CONTINUE                       # guided, past the scripted rounds
unlocked = set(plan["unlock"])

if sid:
    st.caption(f"Signed in as {sid}"
               + (" · progress saved automatically" if store.enabled()
                  else " · (progress storage not detected)"))

# One-time orientation, shown only while planning the very first round. It sets
# expectations up front (time, save behaviour, the required/reviewed debrief) so
# students who skip the printed handout still know the ground rules.
if st.session_state.round == 1 and not st.session_state.history:
    _saves = (sid and store.enabled())
    with st.expander("ℹ️  Before you begin — please read", expanded=True):
        st.markdown(
            "- ⏱️ **Plan about 30–45 minutes.** It's best done in one sitting.\n"
            + ("- 💾 **Your progress saves automatically** — you can close the tab and "
               "return to the same link later to pick up where you left off.\n"
               if _saves else
               "- 💾 **Finish in one sitting.** Your work is kept only for this browser "
               "session, so don't leave the tab idle for long or refresh — you may "
               "lose your progress.\n")
            + "- 🎓 **There is a required debrief.** The game ends with short written "
              "reflections and a knowledge check that are **required and reviewed by "
              "your instructor**; your report unlocks only after you finish them. Play "
              "to *learn the ideas*, not just to hit the numbers.\n"
            + "- ▶️ **How each round works:** run the rush → read what went wrong → "
              "answer the coach → change one decision → run again, until you've "
              "addressed all seven wastes with a solid Lean Score and a profit.")

st.markdown(f"🏪 {SC['briefing']}")
st.subheader(plan["title"])
st.info(f"🎯 **Your goal:** {plan['focus']}")
st.caption(f"💡 **Why this matters:** {plan['why']}  ·  Lean idea: {plan['concept']}")
st.caption("🔁 This page is one turn of the **PDCA / kaizen** cycle, read as a "
           "loop: **CHECK** your last rush's result & wastes (top) → **ACT** on it "
           "with the coach to choose your next move → **PLAN** that change in your "
           "decisions → **DO** it with the RUN button. *Act flows straight into the "
           "next Plan — that is kaizen.*")

# ---- which of the 7 waste-decisions are unlocked this round (needed early) ----
WASTE_KEYS = ["overproduction", "transport", "motion", "overprocessing",
              "inventory", "defects", "waiting"]
_sched = {1: set(),
          2: {"overproduction", "transport"},
          3: {"overproduction", "transport", "motion", "overprocessing", "defects"},
          4: set(WASTE_KEYS)}
if not guided or rnd not in ROUND_PLAN:
    dec_unlocked = set(WASTE_KEYS)
    _new_this_round = set()               # nothing is "new" in free play / late rounds
else:
    dec_unlocked = _sched.get(rnd, set(WASTE_KEYS))
    # decisions unlocked THIS round that weren't available last round → flag as new
    _new_this_round = dec_unlocked - _sched.get(rnd - 1, set())
# Which decision expanders open by default. In guided mode we open ONLY the single
# decision the coach points at (its highest-payoff waste, added in the ACT block
# below) and keep the rest collapsed. Free play opens everything.
_focus = set()

# ======================================================================
# CHECK + ACT (top) — after a rush, show the result, then the Coaching Kata
# (Act), so pressing DO and jumping to the top lands on them in PDCA order.
# ======================================================================
_res = st.session_state.last_result
_cfgd = st.session_state.last_cfg
if _res is not None:
    res = _res
    cfg_done = _cfgd
    diag = _diag = sim.seven_wastes_diagnostic(cfg_done, res)
    hist = st.session_state.history
    prev = hist[-2] if len(hist) > 1 else None

    def d(cur, key):
        if not prev:
            return None
        v = cur - prev[key]
        return f"{v:+.0f}" if abs(v) >= 1 else f"{v:+.1f}"

    # ---------- CHECK (all together) ----------
    st.markdown("<div id='jr-check'></div>", unsafe_allow_html=True)
    st.markdown(f"## 🔍 CHECK — your last rush "
                f"(🏆 Lean **{res.lean_score:.0f}/100** · 💵 **\\${res.profit:.0f}**)")
    st.progress(min(1.0, res.lean_score / 100))
    m = st.columns(4)
    m[0].metric("Avg cycle time", f"{res.avg_cycle:.0f}s",
                d(res.avg_cycle, "avg_cycle"), delta_color="inverse")
    m[1].metric("Served / arrived", f"{res.served:.0f}/{res.arrivals:.0f}",
                d(res.served, "served"))
    m[2].metric("Wrong orders", f"{res.defects:.0f}",
                d(res.defects, "defects"), delta_color="inverse")
    m[3].metric("Profit", f"${res.profit:.0f}", d(res.profit, "profit"))
    st.caption(f"📊 **Predictability:** cycle time varied **± {res.avg_cycle_sd:.0f}s** "
               "across the simulated rushes — standard work shrinks this spread "
               "(see the *Variability* tab).")

    # ---------- was your PLAN·commit prediction correct? ----------
    _lastr0 = hist[-1]["round"]
    _pred = st.session_state.get(f"plancommit_{_lastr0}")
    if _pred and prev is not None:
        _dS = res.lean_score - prev["lean_score"]
        _dP = res.profit - prev["profit"]
        _fact = (f"Lean **{_dS:+.0f}**, profit **{_dP:+.0f}\\$**")
        if "BOTH" in _pred:
            _right = _dS > 0 and _dP > 0
        elif "even if profit dips" in _pred:
            _right = _dS > 0
        elif "re-running" in _pred:
            _right = abs(_dS) <= 2 and abs(_dP) <= 5
        else:                                   # "it might backfire" — always a win
            _right = None
        if _right is True:
            st.success(f"🎯 **Your prediction was right!** You predicted *“{_pred}”* "
                       f"— and it happened: {_fact}.")
        elif _right is False:
            st.error(f"🔄 **Your prediction missed.** You predicted *“{_pred}”*, but "
                     f"the rush gave {_fact}. That gap is the most useful thing to "
                     "learn from — why did it differ?")
        else:
            st.info(f"🧪 **You ran an experiment** (*“{_pred}”*) — result: {_fact}. "
                    "Every experiment teaches you something, win or lose.")

    # ---------- progress toward the debrief: the THREE objectives ----------
    _obj = objectives_status(cfg_done, res)
    _done, _total, _items = _obj["done"], _obj["total"], _obj["items"]
    _obj_met = sum([_obj["wastes_ok"], _obj["score_ok"], _obj["profit_ok"]])
    st.markdown(
        f"**🎯 Objectives to complete the simulation ({_obj_met}/3 met)**  \n"
        f"{'✅' if _obj['wastes_ok'] else '⬜'} All 7 wastes addressed — "
        f"**{_done}/{_total}**  \n"
        f"{'✅' if _obj['score_ok'] else '⬜'} Lean Score ≥ {LEAN_TARGET} — "
        f"**{res.lean_score:.0f}**  \n"
        f"{'✅' if _obj['profit_ok'] else '⬜'} Running a profit (> $0) — "
        f"**${res.profit:.0f}**")
    st.progress(_obj_met / 3.0)
    if _obj["all_ok"]:
        st.caption("✅ All objectives met — the debrief is unlocked below.")
    elif not _obj["wastes_ok"]:
        with st.expander("Which wastes are still left?", expanded=True):
            for nm, ok in _items:
                st.markdown(f"{'✅' if ok else '⬜'} {nm}")

    dc1, dc2 = st.columns([1.05, 1])
    with dc1:
        st.markdown("**The 7 wastes** (🟢 ok · 🟡 watch · 🔴 problem)")
        st.pyplot(seven_waste_fig(diag))
    with dc2:
        st.markdown("**Your 5S** (5 of these fix 5 of the wastes)")
        st.pyplot(five_s_fig(cfg_done))
    _show = [x for x in diag if (not dec_unlocked) or x["waste"].lower() in dec_unlocked]
    if _show:
        st.markdown("**What's happening in the wastes you can act on now:**")
        for x in _show:
            st.markdown(f"{RAG[x['flag']]} **{x['waste']}** — {x['detail']}  "
                        f"*→ fix in the decision: {x['concept']}.*")

    with st.expander("📂 More detail — pick a tab (5S, charts, costs, progress)"):
        t_5s, t_prob, t_var, t_cost, t_prog = st.tabs(
            ["🧹 5S detail", "👀 Problem visuals", "📊 Variability",
             "💵 Costs & ROI", "📈 Progress"])
        with t_5s:
            for name, done, decision, doing in five_s_status(cfg_done):
                st.markdown(f"{'✅' if done else '⬜'} **{name}** — {doing}  \n"
                            f"&nbsp;&nbsp;&nbsp;*decision: {decision}*")
        with t_var:
            st.markdown("**Managing variability — the spread, not just the average.**")
            st.pyplot(cycle_hist(res.all_cycle_times))
            reps = res.reps
            worst = max(reps, key=lambda r: r["abandoned"] / max(1, r["arrivals"]))
            best = min(reps, key=lambda r: r["abandoned"] / max(1, r["arrivals"]))
            wpct = 100 * worst["abandoned"] / max(1, worst["arrivals"])
            bpct = 100 * best["abandoned"] / max(1, best["arrivals"])
            cvv = st.columns(3)
            cvv[0].metric("Average cycle time", f"{res.avg_cycle:.0f}s")
            cvv[1].metric("Spread (±1 SD)", f"± {res.avg_cycle_sd:.0f}s")
            cvv[2].metric("Worst 'bad day'", f"{wpct:.0f}% left",
                          f"vs {bpct:.0f}% best day", delta_color="off")
            st.info("Raising **standard work** makes each drink a more consistent "
                    "time — the histogram narrows and the gap between good and bad "
                    "days shrinks. Predictability is itself a lean win.")
        with t_prob:
            order_done = cfg_layout_order(cfg_done)
            st.caption("🕒 Shows the shop **as you ran it this round**; your pending "
                       "edits apply next rush.")
            st.markdown("**How your drink flowed**")
            st.pyplot(flow_fig(order_done))
            st.markdown("**Where inventory piled up** — 🔵 prep · 🟠 WIP · 🔴 made-"
                        "ahead · dots = customers waiting.")
            st.pyplot(inventory_map_fig(order_done, res, cfg_done))
            v1, v2 = st.columns(2)
            tl = res.timeline
            with v1:
                st.markdown("**Congestion through the rush**")
                wdf = pd.DataFrame({"in shop": tl["wip"]},
                                   index=[round(x, 1) for x in tl["min"]])
                wdf.index.name = "minute"; st.line_chart(wdf)
            with v2:
                st.markdown("**Served vs arrived vs lost**")
                fdf = pd.DataFrame({"arrived": tl["arrived"], "served": tl["served"],
                                    "walked out": tl["walked_out"]},
                                   index=[round(x, 1) for x in tl["min"]])
                fdf.index.name = "minute"; st.line_chart(fdf)
        with t_cost:
            base = baseline_ref(cfg_done.demand_level)
            dprofit = res.profit - base.profit
            st.caption(f"Lean upkeep costs **${res.upkeep:.0f}/rush**.")
            cc = st.columns(3)
            cc[0].metric("Profit now", f"${res.profit:.0f}")
            cc[1].metric("Messy-shop profit", f"${base.profit:.0f}")
            cc[2].metric("Your improvement", f"${dprofit:+.0f}")
            cb = pd.DataFrame({"$": res.cost_breakdown}).sort_values("$", ascending=False)
            st.bar_chart(cb, horizontal=True)
            st.caption(f"Revenue \\${res.revenue:.0f} − Cost \\${res.total_cost:.0f} "
                       f"= Profit \\${res.profit:.0f}")
        with t_prog:
            if len(hist) >= 2:
                h = pd.DataFrame(hist).set_index("round")
                kk = st.columns(2)
                kk[0].markdown("Lean Score ⬆"); kk[0].line_chart(h[["lean_score"]])
                kk[1].markdown("Profit $ ⬆"); kk[1].line_chart(h[["profit"]])
                tbl = h[["lean_score", "avg_cycle", "served", "defects", "waste",
                         "abandon_pct", "upkeep", "profit"]].round(1)
                tbl.columns = ["Lean", "Cycle", "Served", "Wrong", "Waste",
                               "Lost%", "Upkeep", "Profit"]
                st.dataframe(tbl, use_container_width=True)
            else:
                st.info("Play another round to see your trend.")

    # ---------- ACT (Coaching Kata) ----------
    st.markdown("<div id='jr-act'></div>", unsafe_allow_html=True)
    _lastr = st.session_state.history[-1]["round"]
    if _lastr not in st.session_state.coach_q:
        _q = dict(coach_mc(_cfgd, _res, _diag, dec_unlocked,
                           st.session_state.asked_coach))
        # shuffle the answer order so the correct choice isn't always first
        _pairs = list(enumerate(_q["options"]))
        _random.Random(_lastr * 7 + 3).shuffle(_pairs)
        _q["options"] = [t for _, t in _pairs]
        _q["best"] = next(i for i, (oi, _) in enumerate(_pairs) if oi == _q["best"])
        st.session_state.coach_q[_lastr] = _q
        st.session_state.asked_coach.add(_q["id"])
    _cq = st.session_state.coach_q[_lastr]
    # open the decision expander for the waste the coach is pointing at
    _coach_target = _cq.get("target_waste")
    if _coach_target and _coach_target != "any":
        _focus = _focus | {_coach_target}
    _ckey2 = f"coachmc_{_lastr}"
    _answered = st.session_state.get(_ckey2) is not None
    with st.container(border=True):
        st.markdown(f"### 🥋 ACT — Coaching Kata (Round {_lastr})")
        st.caption("**Act** on what CHECK just showed: the five questions a lean "
                   "coach asks to turn results into your next experiment. Answer #3 "
                   "to unlock the **DO** button in the **sidebar**.")
        st.markdown("**1. Target condition** — where you're headed:  \n"
                    "*A lean, profitable shop — serve nearly everyone, few wrong "
                    "drinks, little waste: a high Lean Score with healthy profit.*")
        st.markdown(f"**2. Actual condition now** — the facts this rush:  \n"
                    f"*Lean Score {_res.lean_score:.0f}/100 · served "
                    f"{_res.served:.0f}/{_res.arrivals:.0f} · {_res.defects:.0f} wrong "
                    f"· {_res.waste:.0f} wasted · {_res.abandon_pct:.0f}% walked out.*")
        st.markdown(
            f"""<div id='jr-coachq' class='jr-ask{' done' if _answered else ''}'>
  <div class='jr-ask-tag'>{'✅ Answered — step 1 complete'
                           if _answered
                           else 'Required · this unlocks the DO button'}</div>
  <div class='jr-ask-h'>3. What obstacle is most in your way?</div>
  <div class='jr-ask-q'>{_mini_md(_cq['q'])}</div>
  <div class='jr-ask-hint'>{'You can change your answer below at any time.'
                            if _answered
                            else '👇 Pick one of the options below — the ▶️ DO '
                                 'button in the sidebar stays locked until you do.'}
  </div>
</div>""", unsafe_allow_html=True)
        _choice = st.radio("Your answer:", _cq["options"], index=None, key=_ckey2,
                           label_visibility="collapsed")
        if _choice is None:
            st.caption("🔒 The **DO** button (sidebar) stays locked until you "
                       "choose — commit to a diagnosis first.")
        else:
            _pk = _cq["options"].index(_choice)
            if _pk == _cq["best"]:
                st.success("✅ Good read of the obstacle — now decide your next "
                           "experiment in **PLAN** below and run it.")
            else:
                st.warning("That may not be the leanest read — think about which "
                           "waste is hurting your score most, then plan a change.")
            # the coach does NOT hand over the specific fix unless asked
            _hkey = f"helped_{_lastr}"
            if st.button("💡 Request additional help (reveal the next logical step)",
                         key=f"helpbtn_{_lastr}"):
                st.session_state[_hkey] = True
            if st.session_state.get(_hkey):
                st.markdown("🧑‍🏫 " + _cq["guidance"])
                st.markdown(f"🔎 **Go and see:** {_cq['look']}.")
                st.markdown(f"🎯 **Suggested next step:** {_cq['focus']}.")
            else:
                st.caption("Try to work out the next step yourself first. Stuck? "
                           "Click **Request additional help** above.")
            st.session_state.reflections[f"R{_lastr} coach"] = {
                "q": _cq["q"], "a": f"chose: {_choice}"
                + ("  ✓ (best)" if _pk == _cq["best"] else "")
                + ("  [asked for help]" if st.session_state.get(_hkey) else "")}


# ==========================================================================
# DESIGN
# ==========================================================================
def layout_editor():
    st.caption("**Drag the stations into the order a drink is made.** The image "
               "below numbers each step ①–⑥ and draws the flow: 🟢 forward arrows "
               "are good, 🔴 backward arrows are wasted walking. Aim for all green.")
    b1, b2 = st.columns(2)
    if b1.button("↩︎ Reset to today's messy order", use_container_width=True):
        C["order"] = list(SC["order"]); st.session_state.order_nonce += 1; st.rerun()
    if b2.button("✨ Auto: perfect flow", use_container_width=True):
        C["order"] = list(IDEAL_ORDER); st.session_state.order_nonce += 1; st.rerun()

    if HAVE_DND:
        try:
            labels = [f"{STATION_EMOJI[s]}  {s}" for s in C["order"]]
            back = {f"{STATION_EMOJI[s]}  {s}": s for s in C["order"]}
            res = sort_items(labels, direction="horizontal",
                             key=f"order_dnd_{st.session_state.order_nonce}")
            new = [back[x] for x in res]
            if new != C["order"]:
                C["order"] = new
                st.rerun()
        except Exception:
            _button_reorder()
    else:
        _button_reorder()

    st.pyplot(flow_fig(C["order"]))
    bt = backtracks(C["order"])
    legend = ("🟢 every arrow points forward — clean flow!" if bt == 0
              else f"🔴 {bt} backward arrow(s) = the drink doubles back = wasted "
                   "walking. Reorder to remove them.")
    st.caption(f"Walking per drink: **{order_distance(C['order'])} steps**. {legend}")


def _button_reorder():
    st.caption("Use ◀ ▶ to move a station along the counter:")
    cols = st.columns(len(C["order"]))
    for i, s in enumerate(C["order"]):
        with cols[i]:
            st.markdown(f"<div style='text-align:center'>{STATION_EMOJI[s]}<br>"
                        f"<b>{STATION_ABBR[s]}</b></div>", unsafe_allow_html=True)
            bl, br = st.columns(2)
            if bl.button("◀", key=f"l{i}", disabled=(i == 0),
                         use_container_width=True):
                C["order"][i - 1], C["order"][i] = C["order"][i], C["order"][i - 1]
                st.rerun()
            if br.button("▶", key=f"r{i}", disabled=(i == len(C["order"]) - 1),
                         use_container_width=True):
                C["order"][i + 1], C["order"][i] = C["order"][i], C["order"][i + 1]
                st.rerun()


def _dec(key, title, five_s_tag, cost_txt):
    _new = key in _new_this_round
    # newly unlocked decisions are flagged 🆕 and opened so students notice them
    exp = _new or key in _focus or (not guided)
    _badge = "🆕 NEW · " if _new else ""
    return st.expander(f"{_badge}{title}   ·   {five_s_tag}   ·   💲 {cost_txt}",
                       expanded=exp)


st.markdown("<div id='jr-plan'></div>", unsafe_allow_html=True)
st.markdown("### 🛠️ PLAN — make your decisions (one per waste)")
st.caption("Each of the **7 wastes** has a counter-measure. Notice **five of them "
           "are exactly the 5 S's**; the last two (Defects, Waiting) need quality "
           "tools and capacity. Cost per rush is shown on each.")

# Call out decisions that just unlocked this round (flagged 🆕 and opened below).
if _new_this_round:
    _NAMES = {"overproduction": "Overproduction", "transport": "Transport",
              "motion": "Motion", "overprocessing": "Overprocessing",
              "inventory": "Inventory", "defects": "Defects", "waiting": "Waiting"}
    _new_labels = [_NAMES[w] for w in WASTE_KEYS if w in _new_this_round]
    st.success("🆕 **New this round:** " + ", ".join(_new_labels)
               + " — the 🆕 decisions below just unlocked.")

# The coach's directive shows here ONLY if the student requested help at the top.
_lr = st.session_state.history[-1]["round"] if st.session_state.history else None
_cq_prev = st.session_state.coach_q.get(_lr) if _lr else None
if _cq_prev and st.session_state.get(f"helped_{_lr}"):
    st.info(f"🎯 **Coach's suggested focus:** {_cq_prev['focus']}.  "
            f"🔎 First look at **{_cq_prev['look']}**.")

if not dec_unlocked:
    st.info("Round 1 is your baseline — just press the flashing **RUN** button in "
            "the **sidebar** (top-left). Decisions unlock next round.")

with st.container():
    # 1. Overproduction  →  5S #1 Sort
    if "overproduction" in dec_unlocked:
        with _dec("overproduction", "🏭 **Overproduction** — making drinks before "
                  "they're ordered", "5S #1 Sort", "free"):
            st.caption("**Sort: keep only what's needed.** Made-ahead drinks go "
                       "stale (wrong orders) or get binned (waste). One-piece flow "
                       "= make each drink only when ordered.")
            C["batch"] = st.number_input("Blend batch size (drinks per cycle)", 1, 6,
                                         C["batch"], help="1 = one at a time.")
            C["premade"] = st.number_input("Pre-made drinks staged at open", 0, 20,
                                           C["premade"])

    # 2. Transport  →  5S #2 Set in order
    if "transport" in dec_unlocked:
        tcost = "~$1" if order_distance(C["order"]) < order_distance(list(SC["order"])) else "free"
        with _dec("transport", "🚚 **Transport** — drinks carried around the shop",
                  "5S #2 Set in order", tcost):
            layout_editor()

    # 3. Motion  →  5S #3 Shine
    if "motion" in dec_unlocked:
        fcost = {"Disorganized": 0, "Basic": 3, "Full 5S": 6}[C["five_s"]]
        with _dec("motion", "🚶 **Motion** — workers hunting for tools & "
                  "ingredients", "5S #3 Shine", f"${fcost}/rush"):
            st.caption("**Shine: clean & label.** A tidy, labeled station means no "
                       "searching. Higher levels cost more upkeep.")
            _fs = ["Disorganized", "Basic", "Full 5S"]
            C["five_s"] = st.selectbox(
                "Clean & label level", _fs, index=_fs.index(C["five_s"]),
                label_visibility="collapsed")
            st.caption(f"Upkeep now: **${fcost}/rush**.")

    # 4. Overprocessing  →  5S #4 Standardize
    if "overprocessing" in dec_unlocked:
        sl = sim.STANDARD_LEVELS[C["standard_level"]]
        with _dec("overprocessing", "🔧 **Overprocessing** — every drink made a "
                  "different, longer way", "5S #4 Standardize", f"${sl['cost']:.0f}/rush"):
            st.caption("**Standardize: one agreed best method.** Cheaper tiers give "
                       "most of the benefit; the top tier costs a lot for little "
                       "extra.")
            snames = [f"{i}. {l['name']}" for i, l in enumerate(sim.STANDARD_LEVELS)]
            spick = st.selectbox("Standard work level", snames,
                                 index=C["standard_level"],
                                 label_visibility="collapsed")
            C["standard_level"] = snames.index(spick)
            sl = sim.STANDARD_LEVELS[C["standard_level"]]
            st.caption(f"**{sl['name']}** — {sl['desc']}  ·  ${sl['cost']:.0f}/rush.")

    # 5. Inventory  →  5S #5 Sustain
    if "inventory" in dec_unlocked:
        icost = f"${(3 if C['pull'] else 0) + (1 if C['fifo'] else 0)}/rush" \
            if (C["pull"] or C["fifo"]) else "free"
        with _dec("inventory", "📦 **Inventory** — stock sitting around going stale",
                  "5S #5 Sustain", icost):
            st.caption("Three ways to control inventory: **(a) one-piece flow** "
                       "(batch 1, no pre-made) — free, keeps stock low; **(b) FIFO "
                       "rotation** ($1/rush) — a use-oldest-first rule that keeps "
                       "whatever stock you hold *fresh*, so far less spoils; "
                       "**(c) pull replenishment** ($3/rush) — kanban that restocks "
                       "only what's used. Start with (a); add (b) or (c) only if "
                       "stock is still a problem — don't pay for what you don't need.")
            C["fifo"] = st.toggle("FIFO rotation (use oldest stock first)",
                                  value=C["fifo"])
            C["pull"] = st.toggle("Pull replenishment (kanban)", value=C["pull"])

    # 6. Defects  →  quality tools (visual signals)
    if "defects" in dec_unlocked:
        vl = sim.VISUAL_LEVELS[C["visual_level"]]
        with _dec("defects", "❌ **Defects** — wrong drinks that must be remade",
                  "Quality tool: visual signals", f"${vl['cost']:.0f}/rush"):
            st.caption("Make orders **visible** so they aren't mixed up. (Standard "
                       "recipes above also cut defects.) Cheaper tiers give most of "
                       "the benefit.")
            vnames = [f"{i}. {l['name']}" for i, l in enumerate(sim.VISUAL_LEVELS)]
            vpick = st.selectbox("Visual signal level", vnames,
                                 index=C["visual_level"],
                                 label_visibility="collapsed")
            C["visual_level"] = vnames.index(vpick)
            vl = sim.VISUAL_LEVELS[C["visual_level"]]
            st.caption(f"**{vl['name']}** — {vl['desc']}  ·  ${vl['cost']:.0f}/rush.")

    # 7. Waiting  →  capacity at the bottleneck
    if "waiting" in dec_unlocked:
        wage = sim.COSTS["employee_per_min"] * sim.HORIZON_S / 60.0
        wcost = C["employees"] * wage + C["blenders"] * sim.COSTS["blender_per_rush"]
        with _dec("waiting", "⏳ **Waiting** — customers & orders stuck in a queue",
                  "Capacity at the bottleneck", f"${wcost:.0f}/rush"):
            st.caption("Add people/equipment **only at the station that's backed "
                       "up** — capacity costs money every rush. Test it first!")
            C["mode"] = st.radio("Staffing model",
                                 ["Whole-order", "Specialized stations"],
                                 index=0 if C["mode"] == "Whole-order" else 1)
            if C["mode"] == "Whole-order":
                C["employees"] = st.number_input("Baristas", 1, 6, C["employees"])
            else:
                scg = st.columns(3)
                C["spec_prep"] = scg[0].number_input("Prep", 0, 5, C["spec_prep"])
                C["spec_blend"] = scg[1].number_input("Blend", 0, 5, C["spec_blend"])
                C["spec_finish"] = scg[2].number_input("Finish", 0, 5, C["spec_finish"])
                C["employees"] = max(1, C["spec_prep"] + C["spec_blend"]
                                     + C["spec_finish"])
                st.caption(f"Total baristas: **{C['employees']}**")
            C["blenders"] = st.number_input("🌀 Blenders ($12/rush each)", 1, 4,
                                            C["blenders"])

    # always show the workflow picture + the derived 5S board so the two
    # frameworks stay front-and-center
    if "transport" not in dec_unlocked:
        st.caption(f"Current drink path: {order_distance(C['order'])} steps.")
        st.pyplot(flow_fig(C["order"]))
    if dec_unlocked:
        st.markdown("**Your 5S progress** (the five S's are five of the seven "
                    "waste fixes above):")
        render_5s(cfg_from_state(C))

cfg = cfg_from_state(C)

# ---- PLAN · rehearse + profitability + commit (kept together with decisions) ----
if st.session_state.last_result is not None and dec_unlocked:
    _resL = st.session_state.last_result
    _cfgL = st.session_state.last_cfg
    with st.container(border=True):
        st.markdown("### 📝 PLAN · rehearse — preview the profit of your options")
        st.caption("Your decisions above are the only place changes are made — this "
                   "just previews them. Nothing here commits or advances the round.")

        def _plan_sig(c):
            return (tuple(cfg_layout_order(c)), c.five_s, c.standard_level,
                    c.visual_level, c.pull_replenishment, c.fifo_rotation,
                    c.batch_size, c.premade, c.employees, c.blenders,
                    c.assignment_mode)

        # ---- dry-run: auto-computed whenever the plan changes (cached) ----
        chg = plan_changes(_cfgL, cfg)
        if chg:
            st.markdown("**Your plan changes vs the last rush:** " + "; ".join(chg))
            sig = _plan_sig(cfg)
            cache = st.session_state.get("dryrun_cache")
            if not cache or cache[0] != sig:
                with st.spinner("Previewing your plan…"):
                    _bd = sim.run_simulation(_clone(_cfgL), base_seed=ANALYSIS_SEED)
                    _pd = sim.run_simulation(_clone(cfg), base_seed=ANALYSIS_SEED)
                cache = (sig, dict(name="; ".join(chg)[:90], added_cost=0,
                                   d_profit=_pd.profit - _bd.profit,
                                   d_score=_pd.lean_score - _bd.lean_score,
                                   d_served=_pd.served - _bd.served))
                st.session_state.dryrun_cache = cache
                st.session_state.tested = [c for c in st.session_state.tested
                                           if c.get("added_cost") != 0] + [cache[1]]
            _t = cache[1]
            good = _t["d_profit"]
            st.markdown(f"**Dry-run preview:** profit **{good:+.0f}\\$**, served "
                        f"{_t['d_served']:+.0f}, Lean **{_t['d_score']:+.0f}** "
                        "*vs the last rush.*")
            if good > 3:
                st.success("👍 Looks worth it — commit your plan below.")
            elif good >= -1:
                st.info("😐 Barely moves profit — is it aimed at the coach's obstacle?")
            else:
                st.warning("👎 Profit would drop — a change may cost more than it "
                           "returns. Adjust a decision above.")
        else:
            st.caption("No changes yet — adjust a decision above (the coach said "
                       "where to look) and this will preview its effect automatically.")

        # ---- profitability test — re-run anytime, tests your CURRENT plan ----
        with st.expander("🔬 Test the profit impact of each change *(optional)*",
                         expanded=False):
            st.caption("Tests the levers **unlocked this round** against your "
                       "**current plan** — change a decision and run it again to "
                       "re-test.")
            if st.button("🔬 Run / re-run the test", key=f"roibtn_{rnd}"):
                with st.spinner("Testing each available change…"):
                    _opts = next_step_options(cfg, allowed=dec_unlocked)
                    st.session_state["roirows"] = (
                        _plan_sig(cfg),
                        [test_one_option(cfg, o) for o in _opts])
            _cache = st.session_state.get("roirows")
            _rows = _cache[1] if _cache else None
            if _rows and _cache[0] == _plan_sig(cfg):
                for r in sorted(_rows, key=lambda x: -x["d_profit"]):
                    st.markdown(f"• **{r['name']}** — cost **\\${r['added_cost']:.0f}"
                                f"/rush** → profit **{r['d_profit']:+.0f}\\$**, "
                                f"served **{r['d_served']:+.0f}**, Lean "
                                f"**{r['d_score']:+.0f}**")
                st.pyplot(impact_effort_chart(_rows))
            elif _rows:
                st.info("Your plan changed since the last test — click **Run / "
                        "re-run the test** to refresh.")
            else:
                st.caption("Click **Run / re-run the test** to see the profit impact "
                           "of each available change on your current plan.")

    # ---- REQUIRED: commit your plan before you can DO ----
    with st.container(border=True):
        st.markdown("### 🎯 PLAN · commit — lock in your experiment *(required)*")
        st.markdown("Before you run: **what do you predict your plan will do this "
                    "round?** (Toyota Kata step 4–5: name your experiment & your "
                    "prediction.)")
        _pc = st.radio("Your prediction:", [
            "It will improve BOTH my Lean Score and profit",
            "It will improve the Lean Score, even if profit dips",
            "It's an experiment — it might backfire (and that's OK to learn)",
            "I'm re-running the same plan to confirm the result"],
            index=None, key=f"plancommit_{rnd}", label_visibility="collapsed")
        if _pc is None:
            st.caption("🔒 Commit a prediction to unlock the **DO** button.")
        else:
            st.session_state.reflections[f"R{rnd} plan prediction"] = {
                "q": "Prediction before running", "a": _pc}
            st.success("Locked in — press ▶️ **DO** in the sidebar. Next round's "
                       "CHECK will tell you if you were right.")

st.markdown("<div id='jr-do'></div>", unsafe_allow_html=True)
if need_coach:
    st.warning("✍️ **Answer the coach's question at the top** to unlock the DO "
               "button — diagnosing before acting is the whole skill.")
    _wj, _ = st.columns([1, 2])
    with _wj:
        jr_jump_button("⬆️ Take me to the coach's question")


# ==========================================================================
# run + results
# ==========================================================================
def summarize(res, cfg):
    # capture the student's decisions this round too, for the LMS report
    decisions = []
    if backtracks(cfg_layout_order(cfg)) == 0:
        decisions.append("ordered flow")
    if cfg.five_s != "Disorganized":
        decisions.append(f"5S:{cfg.five_s}")
    if cfg.standard_level > 0:
        decisions.append(f"std:{sim.STANDARD_LEVELS[cfg.standard_level]['name']}")
    if cfg.visual_level > 0:
        decisions.append(f"visual:{sim.VISUAL_LEVELS[cfg.visual_level]['name']}")
    if cfg.pull_replenishment:
        decisions.append("pull")
    if cfg.fifo_rotation:
        decisions.append("fifo")
    if cfg.batch_size > 1:
        decisions.append(f"batch×{cfg.batch_size}")
    if cfg.premade > 0:
        decisions.append(f"premade×{cfg.premade}")
    decisions.append(f"{cfg.employees} staff/{cfg.blenders} blndr")
    return dict(round=st.session_state.round, lean_score=res.lean_score,
                avg_cycle=res.avg_cycle, served=res.served,
                arrivals=res.arrivals, defects=res.defects, waste=res.waste,
                abandon_pct=res.abandon_pct, avg_wip=res.avg_wip,
                walk_units=res.walk_units, profit=res.profit, upkeep=res.upkeep,
                decisions=", ".join(decisions))


if run:
    with st.spinner("Simulating the rush…"):
        res = sim.run_simulation(cfg, base_seed=1000 + rnd)
    st.session_state.last_result = res
    st.session_state.last_cfg = copy.deepcopy(cfg)
    # JSON-able snapshot of exactly what was run + its seed, so a resumed session
    # can rebuild last_result deterministically (see the rebuild block below).
    st.session_state.last_cdict = dict(C)
    st.session_state.last_seed = 1000 + rnd
    st.session_state.history.append(summarize(res, cfg))
    st.session_state.round += 1
    st.session_state.tested = []
    st.session_state.staged = []
    st.session_state.scroll_top = True     # jump to top so results are seen first
    _autosave()                            # persist the finished rush / new round
    st.rerun()

res = st.session_state.last_result
cfg_done = st.session_state.last_cfg

if res is not None:
    hist = st.session_state.history
    # the core is complete ONLY when all THREE objectives are met: every waste
    # addressed, Lean Score high enough, and the shop running a profit. (The full
    # checklist with what's left is shown up in the CHECK panel.)
    _obj_done = objectives_status(cfg_done, res)
    _goal_reached = _obj_done["all_ok"]
    _was_reached = st.session_state.get("goal_reached_once", False)
    if _goal_reached:
        st.session_state.goal_reached_once = True
    else:
        st.session_state.debrief_ready = False

    # ======================================================================
    # 🎓 DEBRIEF — unlocks once every waste has a sensible decision. Then the
    # student may switch to Free play to keep experimenting.
    # ======================================================================
    if _goal_reached:
        st.divider()
        with st.container(border=True):
            if not _was_reached:
                st.success(
                    "🎉 **Objectives met — the core simulation is complete!** All 7 "
                    f"wastes addressed, Lean Score **{res.lean_score:.0f}**, and a "
                    f"healthy profit of **${res.profit:.0f}**. Here's your detailed "
                    "debrief. **Free play** is now unlocked in the sidebar if you "
                    "want to keep experimenting.")
            # persist a completion record for the Director (once; no-op when
            # storage is unconfigured)
            if not st.session_state.get("_completion_recorded"):
                _code = "LR-" + hashlib.sha256(
                    f"{game or ''}|{sid or ''}|{SC['sid']}".encode()
                ).hexdigest()[:8].upper()
                store.record_completion(game, sid, completion_code=_code,
                                        score=round(res.profit, 1))
                st.session_state["_completion_recorded"] = True
                _autosave()
            st.markdown("## 🎓 Debrief — make sense of the whole game")
            st.caption("Research on simulations is blunt: most of the learning "
                       "happens *here*, in the reflection — not in the playing. "
                       "Answer in your own words; your answers go on your report.")

            # computed synthesis to anchor the reflection
            hh = pd.DataFrame(hist)
            jumps = hh["lean_score"].diff()
            if len(jumps) > 1 and jumps[1:].notna().any():
                bi = jumps[1:].idxmax()
                big_round = int(hh.loc[bi, "round"])
                big_delta = jumps[bi]
                big_dec = hh.loc[bi, "decisions"]
            else:
                big_round, big_delta, big_dec = None, 0, ""
            first_s, last_s = hh["lean_score"].iloc[0], hh["lean_score"].iloc[-1]
            first_p, last_p = hh["profit"].iloc[0], hh["profit"].iloc[-1]
            cS = st.columns(3)
            cS[0].metric("Lean Score", f"{last_s:.0f}", f"{last_s-first_s:+.0f} vs start")
            cS[1].metric("Profit", f"${last_p:.0f}", f"${last_p-first_p:+.0f} vs start")
            cS[2].metric("Rounds of kaizen", f"{len(hist)}")
            k1, k2 = st.columns(2)
            k1.markdown("Lean Score across rounds"); k1.line_chart(hh.set_index("round")[["lean_score"]])
            k2.markdown("Profit across rounds"); k2.line_chart(hh.set_index("round")[["profit"]])
            if big_round:
                st.info(f"📈 Your biggest single-round jump was **+{big_delta:.0f} "
                        f"Lean points in Round {big_round}**, when you changed: "
                        f"*{big_dec}*.")

            # ---- detailed per-waste summary: how you tackled each of the 7 ----
            st.markdown("### 📋 How you tackled each of the 7 wastes")
            _dord = cfg_layout_order(cfg_done)
            _decmap = {
                "Transport": (f"line = {order_distance(_dord)} steps"
                              + (", in order ✓" if backtracks(_dord) == 0
                                 else f", {backtracks(_dord)} backtrack(s)")),
                "Overproduction": (f"batch {cfg_done.batch_size}, pre-made "
                                   f"{cfg_done.premade}"),
                "Motion": f"5S: {cfg_done.five_s}",
                "Overprocessing": ("standard work: "
                                   f"{sim.STANDARD_LEVELS[cfg_done.standard_level]['name']}"),
                "Inventory": ", ".join(
                    [t for t, on in (("one-piece flow",
                                      cfg_done.batch_size == 1 and cfg_done.premade == 0),
                                     ("pull", cfg_done.pull_replenishment),
                                     ("FIFO", cfg_done.fifo_rotation)) if on]
                ) or "none yet",
                "Defects": f"visual: {sim.VISUAL_LEVELS[cfg_done.visual_level]['name']}",
                "Waiting": f"{cfg_done.employees} staff / {cfg_done.blenders} blenders",
            }
            _lean_map = {"Transport": "5S Set-in-order", "Overproduction": "5S Sort",
                         "Motion": "5S Shine", "Overprocessing": "5S Standardize",
                         "Inventory": "5S Sustain", "Defects": "Visual signals",
                         "Waiting": "Capacity"}
            st.dataframe(pd.DataFrame([{
                "Waste": x["waste"],
                "Lean tool": _lean_map.get(x["waste"], ""),
                "What you did": _decmap.get(x["waste"], ""),
                "Result": RAG[x["flag"]],
            } for x in diag]), hide_index=True, use_container_width=True)
            st.caption("🟢 solved · 🟡 improving · 🔴 still a problem. Five of the "
                       "seven wastes are fixed by the 5 S's; Defects and Waiting need "
                       "quality tools and capacity.")

            # ---- your lean journey narrative ----
            _reds = sum(1 for x in diag if x["flag"] == "red")
            _greens = sum(1 for x in diag if x["flag"] == "green")
            st.markdown("### 🧭 Your lean journey")
            st.markdown(
                f"You inherited a shop scoring **{first_s:.0f}** with heavy waste. "
                f"Over **{len(hist)} rounds of kaizen** you raised it to "
                f"**{last_s:.0f}** and turned profit from **\\${first_p:.0f}** to "
                f"**\\${last_p:.0f}**. You now have **{_greens}/7 wastes fully "
                f"under control**" + (f" ({_reds} still red)" if _reds else "")
                + ". That is exactly how real lean works — not one big fix, but "
                "many small, evidence-based improvements, repeated.")

            def _dbf(qid, prompt, ph):
                a = st.text_area(prompt, key=f"debrief_{qid}", height=68,
                                 placeholder=ph)
                if a.strip():
                    st.session_state.reflections[f"Debrief · {qid}"] = {
                        "q": prompt, "a": a}
                    return True
                st.session_state.reflections.pop(f"Debrief · {qid}", None)
                return False

            _answers = [
                _dbf("biggest_lever",
                     "1. Which single change moved your Lean Score the most — and "
                     "*why* did that one do so much?",
                     "e.g., putting the stations in order removed all the backtracking…"),
                _dbf("not_worth_it",
                     "2. Did any change cost more than it returned? Which, and how "
                     "did you know it wasn't worth it?",
                     "e.g., the top visual-signal tier — Δ profit was negative in test…"),
                _dbf("prediction",
                     "3. When you dry-ran your plan in ACT, were your predictions "
                     "usually right? What did a *wrong* prediction teach you?",
                     "e.g., I thought a 2nd blender would help but the bottleneck was…"),
                _dbf("transfer",
                     "4. Transfer: pick a real process (a café, clinic, office, your "
                     "email). Which 2 of the 7 wastes does it suffer from, and what's "
                     "the cheapest first countermeasure?",
                     "e.g., my clinic's check-in has Waiting and Motion because…"),
            ]
            _refl_done = sum(_answers)
            if _refl_done < 4:
                st.caption(f"{_refl_done}/4 written reflections answered.")

            # ---- knowledge check (MCQ) — required before the report unlocks ----
            st.divider()
            st.markdown("### 🧠 Knowledge check")
            st.caption("Answer all of these to show what you took away — they, and "
                       "the reflections above, must be complete before your report "
                       "unlocks. Your answers appear on the report.")
            _quiz_correct = _quiz_answered = 0
            for _qi, _qz in enumerate(DEBRIEF_QUIZ):
                _opts = list(_qz["options"])
                _random.Random(f"{SC['sid']}-quiz-{_qi}").shuffle(_opts)
                _sel = st.radio(f"**{_qi + 1}. {_qz['q']}**", _opts, index=None,
                                key=f"dquiz_{_qi}")
                if _sel is not None:
                    _quiz_answered += 1
                    _ok = _sel == _qz["answer"]
                    _quiz_correct += int(_ok)
                    (st.success if _ok else st.error)(
                        ("✓ Correct. " if _ok else "✗ Not quite. ") + _qz["explain"])
                    st.session_state.reflections[f"Knowledge check · Q{_qi + 1}"] = {
                        "q": _qz["q"],
                        "a": f"{_sel}  [{'correct' if _ok else 'incorrect'}]"}
                else:
                    st.session_state.reflections.pop(
                        f"Knowledge check · Q{_qi + 1}", None)
            _quiz_done = _quiz_answered >= len(DEBRIEF_QUIZ)
            if _quiz_done:
                st.info(f"Knowledge check: **{_quiz_correct}/{len(DEBRIEF_QUIZ)}** "
                        "correct.")
            else:
                st.caption(f"{_quiz_answered}/{len(DEBRIEF_QUIZ)} knowledge-check "
                           "questions answered.")

            st.session_state.debrief_ready = bool(_refl_done >= 4 and _quiz_done)
            if st.session_state.debrief_ready:
                st.success("✅ Debrief complete — add your name in the sidebar and "
                           "download your PDF report below. 👏")
            else:
                st.warning("Finish all four reflections **and** the knowledge check "
                           "to unlock the report download.")

            # ---- THE REVEAL: what was actually worth doing (held until now) ----
            st.divider()
            st.markdown("### 🪜 What was worth doing? — *revealed*")
            st.caption("We held this back on purpose: the goal was for you to "
                       "*discover* it. Here's how much each of **your** improvements "
                       "was really adding to your final shop's profit — its value "
                       "against its cost.")
            with st.spinner("Analysing your decisions…"):
                roi = debrief_roi(cfg_done, SC)
            if roi:
                st.pyplot(impact_effort_chart(roi))
                roi_sorted = sorted(roi, key=lambda r: -r["d_profit"])
                st.dataframe(pd.DataFrame([{
                    "Your decision": r["short"],
                    "Cost $/rush": f"{r['added_cost']:.0f}",
                    "Profit it added": f"${r['d_profit']:+.0f}",
                    "Lean pts added": f"{r['d_score']:+.0f}",
                } for r in roi_sorted]), hide_index=True, use_container_width=True)
                best = roi_sorted[0]
                st.info(f"🏆 Your highest-return decision was **{best['short']}** "
                        f"(added \\${best['d_profit']:+.0f} for \\${best['added_cost']:.0f}"
                        "/rush). Notice the cheapest organizing changes usually gave "
                        "the most **per dollar** — that is the answer to *what to do "
                        "first*.")
            else:
                st.caption("You didn't change much from the messy starting shop, so "
                           "there's little to compare. Try another scenario and act "
                           "on the coach's advice to see the returns build up.")
            st.markdown("**The general rule your game just demonstrated — the lean "
                        "priority ladder:**")
            st.dataframe(LADDER, hide_index=True, use_container_width=True)


with st.expander("📄 Progress report — download for your LMS", expanded=False):
    st.markdown("Generate a report of your scenario, decisions, scores, and "
                "reflections to submit to your course site.")
    if not st.session_state.student:
        st.caption("Tip: enter your name / student ID in the sidebar so it appears "
                   "on the report.")
    if not st.session_state.history:
        st.info("Play at least one round first, then come back to download.")
    elif not st.session_state.get("debrief_ready"):
        st.info("📝 The report unlocks once you finish the game and complete the "
                "**debrief** — all four written reflections **and** the knowledge "
                "check. Scroll up to the debrief to finish them.")
    else:
        safe = (st.session_state.student or "student").replace(" ", "_")
        st.download_button("⬇️  Download PDF report",
                           data=build_report_pdf(),
                           file_name=f"justification_{safe}_sc{SC['sid']}.pdf",
                           mime="application/pdf", use_container_width=True,
                           type="primary")
        st.caption("A ready-to-submit PDF with your scenario, round-by-round "
                   "results, decisions, tested options, reflections, and knowledge "
                   "check.")


# ==========================================================================
# At the START of each round (after a rush) snap the page back to the top.
# Injected LAST so the DOM is fully laid out when the scroll fires.
# ==========================================================================
if st.session_state.get("scroll_top"):
    st.session_state.scroll_top = False
    # Embed a per-navigation token so the injected HTML is UNIQUE every time.
    # Identical component HTML lets Streamlit keep the existing iframe (the script
    # would not re-run); a changing token forces a remount so the scroll re-fires
    # on every navigation, not just the first.
    _nav_tok = st.session_state.get("_nav_seq", 0) + 1
    st.session_state["_nav_seq"] = _nav_tok
    import streamlit.components.v1 as _components2
    _components2.html(
        "<script>"
        f"var JR_NAV={_nav_tok};"        # unique per navigation -> forces remount
        "function jrTop(){try{var d=window.parent.document;"
        "var sels=['[data-testid=\"stMain\"]','section.main','.main',"
        "'[data-testid=\"stAppViewContainer\"]'];"
        "sels.forEach(function(s){var e=d.querySelector(s);"
        "if(e){e.scrollTop=0;if(e.scrollTo)e.scrollTo(0,0);}});"
        "if(d.scrollingElement)d.scrollingElement.scrollTop=0;"
        "d.documentElement.scrollTop=0;d.body.scrollTop=0;"
        "window.parent.scrollTo(0,0);}catch(x){}}"
        "for(var i=0;i<15;i++){setTimeout(jrTop,i*90);}"
        "</script>", height=0)


# ---- autosave: persist progress on any run where the snapshot changed --------
# (covers coach answers, plan commits, reflections and knowledge-check answers;
#  a signature guard means idle reruns don't re-upload). No-op when unconfigured.
_autosave()

