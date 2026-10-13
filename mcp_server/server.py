import asyncio, json, os
from mcp.server.mcpserver import MCPServer

mcp = MCPServer("ecommerce-tools")
DATA = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "products.json"), encoding="utf-8"))

def _catalog(src):
    out = []
    for i, p in enumerate(DATA):
        q = dict(p)
        if src == "B" and i % 3 == 0: q["rating"] = round(q["rating"] - 0.3, 1)
        if src == "C" and i % 4 == 0: q["rating"] = round(min(q["rating"] + 0.1, 5), 1)
        out.append(q)
    return out

@mcp.tool()
async def search_products(source: str, category: str) -> str:
    """Search one product source (A, B or C) for a category."""
    await asyncio.sleep(0.6)
    return json.dumps([p for p in _catalog(source) if p["category"] == category])

@mcp.tool()
def filter_products(products: list[dict], max_price: float, min_ram: int,
                    min_storage: int, min_rating: float) -> str:
    """Keep products satisfying all constraints."""
    return json.dumps([p for p in products if p["price"] <= max_price and p["ram"] >= min_ram
                       and p["storage"] >= min_storage and p["rating"] >= min_rating])

@mcp.tool()
def compare_products(products: list[dict]) -> str:
    """Compare products and report the best in each parameter."""
    if not products: return json.dumps({"table": [], "best": {}})
    best = {"price (lowest)": min(products, key=lambda p: p["price"])["name"],
            "ram": max(products, key=lambda p: p["ram"])["name"],
            "storage": max(products, key=lambda p: p["storage"])["name"],
            "rating": max(products, key=lambda p: p["rating"])["name"]}
    return json.dumps({"table": products, "best": best})

@mcp.tool()
def rank_products(products: list[dict], max_price: float, min_ram: int,
                  min_storage: int, min_rating: float) -> str:
    """Transparent weighted scoring: price 30, rating 30, ram 20, storage 20."""
    out = []
    for p in products:
        parts = {"price": round(30 * (1 - p["price"] / max_price), 2),
                 "rating": round(30 * p["rating"] / 5, 2),
                 "ram": round(20 * min(p["ram"] / max(min_ram * 2, 16), 1), 2),
                 "storage": round(20 * min(p["storage"] / max(min_storage * 2, 512), 1), 2)}
        q = dict(p); q["score"] = round(sum(parts.values()), 2); q["breakdown"] = parts
        q["reason"] = (f"₹{p['price']:,} (₹{max_price - p['price']:,.0f} under budget), "
                       f"{p['ram']}GB RAM, {p['storage']}GB, rating {p['rating']}")
        out.append(q)
    return json.dumps(sorted(out, key=lambda x: x["score"], reverse=True))

@mcp.tool()
def validate_recommendation(ranked: list[dict], max_price: float, min_ram: int,
                            min_storage: int, min_rating: float) -> str:
    """Check ranked output against the original requirements."""
    issues = []
    if not ranked: issues.append("empty ranking")
    for p in ranked:
        miss = [k for k in ("name", "price", "ram", "storage", "rating", "score") if k not in p]
        if miss: 
            issues.append(f"{p.get('name','?')}: missing {miss}")
            continue
        if p["price"] > max_price: issues.append(f"{p['name']}: over budget")
        if p["ram"] < min_ram: issues.append(f"{p['name']}: RAM too low")
        if p["storage"] < min_storage: issues.append(f"{p['name']}: storage too low")
        if p["rating"] < min_rating: issues.append(f"{p['name']}: rating too low")
        
    sc = [p.get("score", 0) for p in ranked]
    if sc != sorted(sc, reverse=True): issues.append("ranking not sorted")
    return json.dumps({"valid": not issues, "issues": issues})

if __name__ == "__main__":
    mcp.run(transport="stdio")