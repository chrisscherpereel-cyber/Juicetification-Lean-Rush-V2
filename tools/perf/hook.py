"""Accurate per-rerun server cost: time only the script execution (exec of the
compiled app incl. Streamlit element serialization), not AppTest's AST/compile
or its protobuf parsing. CPU = thread_time of the script thread."""
import time
import streamlit.runtime.scriptrunner.script_runner as sr
import streamlit.runtime.scriptrunner.exec_code as ec
LAST={"cpu":0.0,"wall":0.0}
_orig=ec.exec_func_with_error_handling
def timed(func, ctx):
    c=time.thread_time(); w=time.perf_counter()
    try: return _orig(func, ctx)
    finally:
        LAST["cpu"]=time.thread_time()-c; LAST["wall"]=time.perf_counter()-w
ec.exec_func_with_error_handling=timed
sr.exec_func_with_error_handling=timed

import os, cProfile, pstats
PROF={"on":False,"stats":None}
_t2=timed
def timed_prof(func, ctx):
    if not PROF["on"]: return _t2(func, ctx)
    pr=cProfile.Profile(); pr.enable()
    try: return _t2(func, ctx)
    finally:
        pr.disable(); PROF["stats"]=pr
ec.exec_func_with_error_handling=timed_prof
sr.exec_func_with_error_handling=timed_prof
def show(label, n=30, pat=None):
    print("=====",label)
    s=pstats.Stats(PROF["stats"]); s.sort_stats("cumulative")
    s.print_stats(pat or "", n) if pat else s.print_stats(n)
