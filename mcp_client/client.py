import contextlib
import asyncio, json, os, sys
from contextlib import AsyncExitStack, nullcontext
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

SERVER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mcp_server", "server.py")
ALLOW = {"Planner": [], "Router": [], "Search": ["search_products"], "Filter": ["filter_products"],
         "Comparison": ["compare_products"], "Ranking": ["rank_products"],
         "Validator": ["validate_recommendation"], "Supervisor": []}
MAX_RETRY = 2

class MCPClient:
    def __init__(s, log, metrics): 
        s.log, s.m, s.tools = log, metrics, []
        
    async def __aenter__(s):
        s.stack = AsyncExitStack()
        try:
            r, w = await s.stack.enter_async_context(
                stdio_client(StdioServerParameters(
                    command=sys.executable,
                    args=[os.path.normpath(SERVER)],
                    env={**os.environ},
                ))
            )
            s.session = await s.stack.enter_async_context(ClientSession(r, w))
            await s.session.initialize()
            res = await s.session.list_tools()
            s.tools = [{"name": t.name, "description": t.description, "schema": t.input_schema} for t in res.tools]
            s.log.log("INFO", "MCPClient", f"initialized; discovered {[t['name'] for t in s.tools]}")
            return s
        except BaseException:
            with contextlib.suppress(Exception):
                await s.stack.aclose()
            raise
            
    async def __aexit__(s, *a): 
        await s.stack.aclose()

    async def call(s, agent, tool, args, count=True, flaky=False):
        if tool not in ALLOW.get(agent, []):
            s.log.log("SECURITY", agent, f"DENIED unauthorized tool '{tool}'")
            raise PermissionError(f"{agent} is not authorized to use '{tool}'")
        for attempt in range(MAX_RETRY + 1):
            if count: s.m.tool_calls += 1
            try:
                with (s.log.span(agent, f"call {tool}", tool) if count else nullcontext({})) as rec:
                    rec["retry"] = attempt
                    if flaky and attempt == 0: raise RuntimeError("simulated tool failure")
                    res = await asyncio.wait_for(s.session.call_tool(tool, args), timeout=20)
                    
                    # Fix: Handle both SDK versions (is_error for newer SDKs, isError for older ones)
                    if getattr(res, "is_error", False) or getattr(res, "isError", False): 
                        raise RuntimeError(res.content[0].text)
                        
                return json.loads(res.content[0].text)
            except Exception as e:
                if attempt == MAX_RETRY: raise
                if count:
                    s.m.retries += 1
                    s.log.log("WARN", agent, f"{tool} failed ({e}); retry {attempt + 1}/{MAX_RETRY}")