import time
from contextlib import contextmanager

class Logger:
    def __init__(s): 
        s.logs, s.trace = [], []
    def log(s, level, agent, msg, **kw):
        s.logs.append({"time": time.strftime("%H:%M:%S"), "level": level, "agent": agent, "msg": msg, **kw})
    @contextmanager
    def span(s, agent, task, tool=None):
        rec = {"agent": agent, "task": task, "tool": tool, "status": "running", "retry": 0, "error": "", "ms": 0}
        t0 = time.perf_counter()
        s.trace.append(rec)
        try:
            yield rec
            rec["status"] = "success"
        except Exception as e:
            rec["status"] = "failed"
            rec["error"] = str(e)
            raise
        finally:
            rec["ms"] = round((time.perf_counter() - t0) * 1000, 1)

class Metrics:
    def __init__(s): 
        s.agent_calls = s.tool_calls = s.retries = 0
        s.seq = s.par = 0.0
    def cost(s): 
        return s.agent_calls + 2 * s.tool_calls + 3 * s.retries
    def speedup(s): 
        return round(s.seq / s.par, 2) if s.par else 0