"""Median server CPU per action (in-thread), many repetitions, one process."""
import sys, statistics, hook
from streamlit import config as stcfg
APP=sys.argv[1]; GUS=sys.argv[2]=="on"; REPS=int(sys.argv[3])
stcfg.set_option("browser.gatherUsageStats", GUS)
from streamlit.testing.v1 import AppTest
res={}
def rec(k): res.setdefault(k,[]).append(hook.LAST["cpu"])
for rep in range(REPS):
    at=AppTest.from_file(APP, default_timeout=180); at.query_params["seed"]=str(500+rep); at.run(); rec("page load")
    b=lambda p:[x for x in at.button if (x.label or "").startswith(p)][0]
    for r in range(3):
        b("▶️").click().run(); rec("run a rush")
        at.run(); rec("idle rerun")
        for pre,lbl in (("coachmc_","answer coach MC"),("plancommit_","commit plan")):
            rr=[x for x in at.radio if (x.key or "").startswith(pre)]
            if rr: rr[0].set_value(rr[0].options[0]).run(); rec(lbl)
        dv=[x for x in at.radio if x.key=="detail_view"]
        if dv: dv[0].set_value(dv[0].options[(r%4)+1]).run(); rec("switch detail view")
    [x for x in at.button if x.key=="gen_report_side"][0].click().run(); rec("generate report")
    [x for x in at.button if x.key=="gen_report_side"][0].click().run(); rec("generate report again")
    assert not at.exception, at.exception
for k,v in res.items(): print(f"{k:24s} median {statistics.median(v)*1000:7.1f} ms  mean {statistics.mean(v)*1000:7.1f} ms  n={len(v)}")
