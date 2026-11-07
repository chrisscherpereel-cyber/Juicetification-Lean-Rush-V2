"""Streamlit-aware concurrency test.

Each virtual student opens a real WebSocket session against a running
`streamlit run app.py` server and speaks Streamlit's own protocol (BackMsg /
ForwardMsg protobufs) -- exactly what a browser tab sends, minus the rendering.
It reads the widgets the server draws, then clicks / answers them like a
student playing the game:

  page load -> [ DO (run the rush) -> answer coach MC -> commit plan
                -> switch the detail view ] x ROUNDS -> generate report

Latency for every action = time from sending the rerun request to receiving
`script_finished`. Server CPU and RSS are sampled from /proc while it runs.

usage: python tools/perf/loadtest.py PORT N_USERS ROUNDS burst|paced OUT.json SERVER_PID
(normally run through run_level.sh / sweep.sh)
"""
import asyncio, json, random, statistics, sys, time

import websockets
from streamlit.proto.BackMsg_pb2 import BackMsg
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg

PORT, N, ROUNDS, MODE, OUT, PID = (int(sys.argv[1]), int(sys.argv[2]),
                                   int(sys.argv[3]), sys.argv[4], sys.argv[5],
                                   int(sys.argv[6]))
URL = f"ws://127.0.0.1:{PORT}/_stcore/stream"


class Student:
    def __init__(self, i):
        self.i = i
        self.ws = None
        self.page_hash = ""
        self.widgets = {}      # id -> (kind, label, extra, disabled)
        self.state = {}        # persisted widget values: id -> ("string", v)
        self.lat = {}          # action -> [seconds]
        self.errors = []

    async def rerun(self, action, trigger=None, set_string=None):
        if set_string:
            self.state[set_string[0]] = set_string[1]
        bm = BackMsg()
        cs = bm.rerun_script
        cs.query_string = ""
        cs.page_script_hash = self.page_hash
        for wid, val in self.state.items():
            w = cs.widget_states.widgets.add(); w.id = wid; w.string_value = val
        if trigger:
            w = cs.widget_states.widgets.add(); w.id = trigger; w.trigger_value = True
        self.widgets = {}
        t0 = time.perf_counter()
        await self.ws.send(bm.SerializeToString())
        while True:
            raw = await asyncio.wait_for(self.ws.recv(), timeout=600)
            fm = ForwardMsg(); fm.ParseFromString(raw)
            kind = fm.WhichOneof("type")
            if kind == "new_session":
                self.page_hash = fm.new_session.main_script_hash
            elif kind == "delta" and fm.delta.WhichOneof("type") == "new_element":
                el = fm.delta.new_element
                ek = el.WhichOneof("type")
                if ek == "exception":
                    self.errors.append(el.exception.message[:200])
                elif ek in ("button", "radio"):
                    w = getattr(el, ek)
                    extra = list(w.options) if ek == "radio" else None
                    self.widgets[w.id] = (ek, w.label, extra, w.disabled)
            elif kind == "script_finished":
                # a script that calls st.rerun() finishes EARLY_FOR_RERUN and
                # immediately runs again: the action is done only when the
                # final run completes
                if fm.script_finished == ForwardMsg.FINISHED_EARLY_FOR_RERUN:
                    self.widgets = {}
                    continue
                break
        dt = time.perf_counter() - t0
        self.lat.setdefault(action, []).append(dt)
        return dt

    def find(self, kind, label_prefix=None, id_contains=None):
        for wid, (k, lbl, extra, dis) in self.widgets.items():
            if k != kind or dis:
                continue
            if label_prefix and not lbl.startswith(label_prefix):
                continue
            if id_contains and id_contains not in wid:
                continue
            return wid, extra
        return None, None

    async def think(self):
        if MODE == "paced":
            await asyncio.sleep(random.uniform(2.0, 8.0))

    async def play(self, start_evt):
        self.ws = await websockets.connect(URL, subprotocols=["streamlit"],
                                           max_size=None, open_timeout=120,
                                           ping_interval=None)
        await start_evt.wait()
        if MODE == "paced":
            await asyncio.sleep(random.uniform(0, 5.0))
        await self.rerun("page load")
        for r in range(ROUNDS):
            await self.think()
            do, _ = self.find("button", "▶️")
            if not do:
                self.errors.append(f"round {r}: DO not available"); break
            await self.rerun("run a rush", trigger=do)
            await self.think()
            mc, opts = self.find("radio", id_contains="coachmc_")
            if mc:
                await self.rerun("answer coach MC", set_string=(mc, random.choice(opts)))
            pc, opts = self.find("radio", id_contains="plancommit_")
            if pc:
                await self.think()
                await self.rerun("commit plan", set_string=(pc, opts[0]))
            dv, opts = self.find("radio", id_contains="detail_view")
            if dv and len(opts) > 1:
                await self.think()
                await self.rerun("switch detail view", set_string=(dv, random.choice(opts[1:])))
        await self.think()
        gen, _ = self.find("button", id_contains="gen_report_side")
        if gen:
            await self.rerun("generate report", trigger=gen)
        await self.ws.close()


def proc_sample(pid):
    with open(f"/proc/{pid}/stat") as f:
        parts = f.read().rsplit(")", 1)[1].split()
    cpu = (int(parts[11]) + int(parts[12])) / 100.0     # utime+stime, clock ticks
    with open(f"/proc/{pid}/status") as f:
        rss = next(int(l.split()[1]) for l in f if l.startswith("VmRSS")) / 1024
    return cpu, rss


async def main():
    cpu0, rss0 = proc_sample(PID)
    peak = [rss0]
    stop = False

    async def sampler():
        while not stop:
            peak[0] = max(peak[0], proc_sample(PID)[1])
            await asyncio.sleep(0.1)

    studs = [Student(i) for i in range(N)]
    evt = asyncio.Event()
    smp = asyncio.create_task(sampler())
    tasks = [asyncio.create_task(s.play(evt)) for s in studs]
    await asyncio.sleep(1.0)
    t0 = time.perf_counter(); evt.set()
    results = await asyncio.gather(*tasks, return_exceptions=True)
    wall = time.perf_counter() - t0
    stop = True; await smp
    cpu1, rss1 = proc_sample(PID)
    lat = {}
    for s in studs:
        for k, v in s.lat.items():
            lat.setdefault(k, []).extend(v)
    allv = [x for v in lat.values() for x in v]
    def pct(v, p):
        v = sorted(v); return v[min(len(v) - 1, int(round(p / 100 * (len(v) - 1))))]
    out = {
        "users": N, "rounds": ROUNDS, "mode": MODE, "wall_s": round(wall, 2),
        "server_cpu_s": round(cpu1 - cpu0, 2),
        "cpu_util_pct": round(100 * (cpu1 - cpu0) / wall, 1),
        "rss_start_mb": round(rss0), "rss_peak_mb": round(peak[0]), "rss_end_mb": round(rss1),
        "actions": len(allv),
        "errors": sum(len(s.errors) for s in studs) + sum(isinstance(r, Exception) for r in results),
        "error_samples": ([e for s in studs for e in s.errors][:3]
                          + [repr(r)[:200] for r in results if isinstance(r, Exception)][:3]),
        "all": {"mean": round(statistics.mean(allv), 3), "p50": round(pct(allv, 50), 3),
                "p95": round(pct(allv, 95), 3), "max": round(max(allv), 3)} if allv else {},
        "by_action": {k: {"n": len(v), "mean": round(statistics.mean(v), 3),
                          "p95": round(pct(v, 95), 3), "max": round(max(v), 3)}
                      for k, v in lat.items()},
    }
    json.dump(out, open(OUT, "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("users", "mode", "wall_s", "cpu_util_pct",
                                         "rss_peak_mb", "errors", "all")}))
    for k, v in out["by_action"].items():
        print(f"   {k:20s} {v}")
    if out["error_samples"]:
        print("   errors:", out["error_samples"])

asyncio.run(main())
