import asyncio, os
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from agents.pipeline import run_pipeline
from tests.security import run_security_tests

# Load environment variables from .env
load_dotenv()

st.set_page_config(page_title="Exp 6 – MCP E-Commerce Pipeline", layout="wide")
st.title("Multi-Agent E-Commerce Pipeline with Real MCP")

with st.sidebar:
    use_llm = st.toggle("LLM Planner (Groq)", True)
    flaky = st.toggle("Inject tool failure (source B)", False)

t_run, t_tools, t_trace, t_met, t_sec, t_obs = st.tabs(
    ["Run", "MCP Tools", "Trace & Logs", "Metrics", "Security Tests", "Observation Table"])

with t_run:
    q = st.text_area("Query", "Find laptops under ₹70,000 with at least 16 GB RAM, 512 GB storage and rating above 4.2.")
    if st.button("Run pipeline", type="primary"):
        with st.spinner("Starting MCP server and running agents..."):
            st.session_state["r"] = asyncio.run(run_pipeline(q, use_llm, flaky))
    if "r" in st.session_state:
        s, log, m, tools = st.session_state["r"]
        d = s.d
        c1, c2 = st.columns(2)
        c1.subheader("Requirements (Planner)")
        c1.json(d["requirements"])
        c2.subheader("Plan (Router)")
        c2.dataframe(pd.DataFrame(d["plan"] or []), hide_index=True)
        st.subheader("Search conflicts resolved")
        if d["conflicts"]: 
            st.dataframe(pd.DataFrame(d["conflicts"]), hide_index=True)
        else: 
            st.write("None")
        st.subheader("Ranked products")
        if d["ranking"]:
            st.dataframe(pd.DataFrame(d["ranking"])[["name", "brand", "price", "ram", "storage", "rating", "score", "reason"]], hide_index=True)
        else: 
            st.warning("No products matched.")
        st.write("**Validation:**", d["validation"])
        st.write("**Supervisor status:**", d["status"])
        if d["errors"]: 
            st.error(d["errors"])
        if d["status"] == "awaiting_human_approval":
            st.subheader("Human approval")
            a, b = st.columns(2)
            if a.button("✅ Approve"):
                s.write("Human", "human_approval", "approved")
                s.write("Human", "final_recommendation", d["ranking"][0])
            if b.button("❌ Reject"): 
                s.write("Human", "human_approval", "rejected")
        if d["human_approval"] == "approved":
            top = d["final_recommendation"]
            st.success(f"Final recommendation: {top['name']} (score {top['score']}) – {top['reason']}")
        elif d["human_approval"] == "rejected": 
            st.warning("Rejected by human. Re-run for another analysis.")

if "r" in st.session_state:
    s, log, m, tools = st.session_state["r"]
    with t_tools:
        st.caption("Discovered via MCP list_tools")
        for t in tools:
            with st.expander(t["name"]): 
                st.write(t["description"])
                st.json(t["schema"])
    with t_trace:
        st.subheader("Execution trace")
        st.dataframe(pd.DataFrame(log.trace), hide_index=True)
        st.subheader("Logs")
        st.dataframe(pd.DataFrame(log.logs), hide_index=True)
        st.subheader("Agent messages")
        st.dataframe(pd.DataFrame(s.d["messages"]), hide_index=True)
    with t_met:
        c = st.columns(5)
        c[0].metric("Sequential (s)", round(m.seq, 2))
        c[1].metric("Parallel (s)", round(m.par, 2))
        c[2].metric("Speedup", m.speedup())
        c[3].metric("Tool calls", m.tool_calls)
        c[4].metric("Cost units", m.cost())
        st.bar_chart(pd.DataFrame({"time (s)": [m.seq, m.par]}, index=["Sequential", "Parallel"]))
        st.caption("Cost = agent calls ×1 + tool calls ×2 + retries ×3")

with t_sec:
    if st.button("Run security tests"):
        with st.spinner("Running..."):
            st.session_state["sec"] = asyncio.run(run_security_tests(use_llm))
    if "sec" in st.session_state: 
        st.dataframe(pd.DataFrame(st.session_state["sec"]), hide_index=True)

with t_obs:
    if "r" in st.session_state:
        s, log, m, tools = st.session_state["r"]
        sec = st.session_state.get("sec")
        sec_txt = "Not run" if not sec else ("All passed" if all(x["result"] == "PASS" for x in sec) else "Some failed")
        fin = s.d["final_recommendation"]
        rows = [
            ("User Query",                s.d["user_query"]),
            ("Number of Agents Executed", str(m.agent_calls)),
            ("Sequential Execution Time", f"{m.seq:.2f} s"),
            ("Parallel Execution Time",   f"{m.par:.2f} s"),
            ("Speedup",                   str(m.speedup())),
            ("Number of Tool Calls",      str(m.tool_calls)),
            ("Number of Retries",         str(m.retries)),
            ("Cost Units",                str(m.cost())),
            ("Human Approval",            s.d["human_approval"]),
            ("Security Test Result",      sec_txt),
            ("Final Recommendation",      fin["name"] if fin else "Pending"),
        ]
        st.table(pd.DataFrame(rows, columns=["Parameter", "Observation"]))