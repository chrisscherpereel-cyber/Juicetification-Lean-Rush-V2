"""Per-click wall time when storage is on and Dropbox has realistic latency.
Storage calls are replaced by fakes that sleep (no real network); counts calls."""
import sys, time, statistics, hook
APP=sys.argv[1]; LAT_GET=float(sys.argv[2]); LAT_PUT=float(sys.argv[3])
sys.path.insert(0, APP.rsplit("/",1)[0])
import student_store as store
calls={"load_game_config":0,"save":0,"load":0}
def lgc(code): calls["load_game_config"]+=1; time.sleep(LAT_GET); return {"params": {}, "seed": 4242}
def save(game,sid,state,**k): calls["save"]+=1; time.sleep(LAT_PUT); return True
def load(game,sid): calls["load"]+=1; time.sleep(LAT_GET); return {}
store.ENABLED=True; store.load_game_config=lgc; store.save=save; store.load=load
from streamlit.testing.v1 import AppTest
at=AppTest.from_file(APP, default_timeout=180)
at.query_params["game"]="CLASS1"; at.query_params["sid"]="student01"
at.run()
walls={}
def act(lbl,f):
    f(); walls.setdefault(lbl,[]).append(hook.LAST["wall"])
    assert not at.exception, at.exception
b=lambda p:[x for x in at.button if (x.label or "").startswith(p)][0]
for r in range(3):
    act("run a rush", lambda: b("▶️").click().run())
    for pre in ("coachmc_","plancommit_"):
        rr=[x for x in at.radio if (x.key or "").startswith(pre)]
        if rr: act("answer a question", lambda: rr[0].set_value(rr[0].options[0]).run())
    act("idle rerun", lambda: at.run())
for k,v in walls.items(): print(f"  {k:18s} mean wall {statistics.mean(v):.3f}s  (n={len(v)})")
print("  storage calls:", calls)
