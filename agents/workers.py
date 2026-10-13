import asyncio, time

async def search_agent(st, log, m, cli, flaky):
    m.agent_calls += 1
    with log.span("Search", "search 3 sources"):
        cat, srcs = st.d["requirements"]["category"], ["A", "B", "C"]
        t = time.perf_counter()
        for s in srcs: 
            await cli.call("Search", "search_products", {"source": s, "category": cat}, count=False)
        m.seq = time.perf_counter() - t
        
        t = time.perf_counter()
        res = await asyncio.gather(*[cli.call("Search", "search_products", {"source": s, "category": cat},
                                              flaky=(flaky and s == "B")) for s in srcs], return_exceptions=True)
        m.par = time.perf_counter() - t
        
        by = {}
        for s, r in zip(srcs, res):
            if isinstance(r, Exception): 
                st.error(f"source {s} failed: {r}")
                log.log("ERROR", "Search", f"source {s} failed")
            else: by[s] = r
            
        TRUST, seen, merged, conflicts = ["A", "C", "B"], {}, [], []
        for s in TRUST:
            for p in by.get(s, []):
                seen.setdefault(p["name"], []).append((s, p))
                
        for name, lst in seen.items():
            best = dict(lst[0][1])
            best["source"] = lst[0][0]
            ratings = {s: p["rating"] for s, p in lst}
            if len(set(ratings.values())) > 1:
                conflicts.append({"product": name, "ratings": ratings, "resolved": best["rating"],
                                  "rule": f"trusted-source priority (source {lst[0][0]})"})
            merged.append(best)
            
        st.write("Search", "search_results", merged)
        st.write("Search", "conflicts", conflicts)
        st.msg("Search", "Filter", f"{len(merged)} products, {len(conflicts)} rating conflicts resolved")

def _args(st):
    r = st.d["requirements"]
    return {k: r[k] for k in ("max_price", "min_ram", "min_storage", "min_rating")}

async def filter_agent(st, log, m, cli):
    m.agent_calls += 1
    with log.span("Filter", "apply constraints"):
        out = await cli.call("Filter", "filter_products", {"products": st.d["search_results"], **_args(st)})
        st.write("Filter", "filtered_results", out)
        st.msg("Filter", "Comparison", f"{len(out)} passed")

async def comparison_agent(st, log, m, cli):
    m.agent_calls += 1
    with log.span("Comparison", "compare products"):
        st.write("Comparison", "comparison", await cli.call("Comparison", "compare_products",
                                                            {"products": st.d["filtered_results"]}))

async def ranking_agent(st, log, m, cli):
    m.agent_calls += 1
    with log.span("Ranking", "score and sort"):
        out = await cli.call("Ranking", "rank_products", {"products": st.d["filtered_results"], **_args(st)})
        st.write("Ranking", "ranking", out)
        st.msg("Ranking", "Validator", f"{len(out)} ranked")

async def validator_agent(st, log, m, cli):
    m.agent_calls += 1
    with log.span("Validator", "validate ranking"):
        st.write("Validator", "validation",
                 await cli.call("Validator", "validate_recommendation", {"ranked": st.d["ranking"], **_args(st)}))

def supervisor(st, log, m):
    m.agent_calls += 1
    with log.span("Supervisor", "final check"):
        issues = []
        if not st.verify(): issues.append("requirements were tampered with")
        if not st.d["ranking"]: issues.append("no products matched")
        v = st.d["validation"]
        if not v or not v["valid"]: issues.append(f"validation failed: {v['issues'] if v else 'not run'}")
        if st.d["errors"]: issues.append(f"{len(st.d['errors'])} workflow errors")
        ok = not [i for i in issues if "workflow errors" not in i]
        st.write("Supervisor", "status", "awaiting_human_approval" if ok else "escalated")
        if issues: log.log("WARN", "Supervisor", "; ".join(issues))