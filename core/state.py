import json, hashlib, uuid

OWNER = {"requirements": "Planner", "plan": "Router", "search_results": "Search", "conflicts": "Search",
         "filtered_results": "Filter", "comparison": "Comparison", "ranking": "Ranking",
         "validation": "Validator", "status": "Supervisor",
         "human_approval": "Human", "final_recommendation": "Human"}

def _h(x): 
    return hashlib.sha256(json.dumps(x, sort_keys=True).encode()).hexdigest()

class WorkflowState:
    def __init__(s, query, log=None):
        s.log = log
        s._lock = None
        s.d = {"workflow_id": uuid.uuid4().hex[:8], "user_query": query, "requirements": None, "plan": None,
               "messages": [], "search_results": [], "conflicts": [], "filtered_results": [], "comparison": None,
               "ranking": [], "validation": None, "status": "running", "human_approval": "pending",
               "final_recommendation": None, "errors": []}
               
    def write(s, agent, key, val):
        if OWNER.get(key) != agent:
            if s.log: s.log.log("SECURITY", agent, f"DENIED write to '{key}'")
            raise PermissionError(f"{agent} cannot modify '{key}'")
        if key == "requirements":
            if s._lock is not None:
                if s.log: s.log.log("SECURITY", agent, "DENIED: requirements are locked")
                raise PermissionError("requirements are locked")
            s._lock = _h(val)
        s.d[key] = val
        
    def verify(s): 
        return s._lock is None or _h(s.d["requirements"]) == s._lock
        
    def msg(s, frm, to, summary): 
        s.d["messages"].append({"from": frm, "to": to, "summary": summary})
        
    def error(s, m): 
        s.d["errors"].append(m)