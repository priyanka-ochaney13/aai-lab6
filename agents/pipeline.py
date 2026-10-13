from core.logger import Logger, Metrics
from core.state import WorkflowState
from mcp_client.client import MCPClient
from agents.planner import planner, router
from agents.workers import (search_agent, filter_agent, comparison_agent,
                            ranking_agent, validator_agent, supervisor)

async def run_pipeline(query, use_llm=True, flaky=False):
    log, m = Logger(), Metrics()
    st = WorkflowState(query, log)
    async with MCPClient(log, m) as cli:
        try:
            await planner(st, log, m, use_llm)
            router(st, log, m)
            await search_agent(st, log, m, cli, flaky)
            await filter_agent(st, log, m, cli)
            if st.d["filtered_results"]:
                await comparison_agent(st, log, m, cli)
                await ranking_agent(st, log, m, cli)
                await validator_agent(st, log, m, cli)
        except Exception as e:
            st.error(str(e))
            log.log("ERROR", "Orchestrator", str(e))
        supervisor(st, log, m)
        return st, log, m, cli.tools