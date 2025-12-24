from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import asyncio, time, random, uuid
import httpx

app = FastAPI()

templates = Jinja2Templates(directory="templates")

agents = {}  
# agent_id -> {
#   ip, city, country, last_seen, latency
# }

# ======================
# ROOT (Railway check)
# ======================
@app.get("/")
async def root():
    return PlainTextResponse("OK")

# ======================
# GEO ENRICHMENT
# ======================
async def geo_lookup(ip):
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"http://ip-api.com/json/{ip}")
            j = r.json()
            return {
                "country": j.get("countryCode", "??"),
                "city": j.get("city", "Unknown")
            }
    except:
        return {"country": "??", "city": "Unknown"}

# ======================
# AGENT WS
# ======================
@app.websocket("/ws/agent/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    ip = ws.client.host

    geo = await geo_lookup(ip)

    agents[agent_id] = {
        "ip": ip,
        "city": geo["city"],
        "country": geo["country"],
        "last_seen": time.time(),
        "latency": None
    }

    try:
        while True:
            msg = await ws.receive_json()

            if msg["type"] == "ping":
                agents[agent_id]["last_seen"] = time.time()
                agents[agent_id]["latency"] = msg.get("latency")

    except WebSocketDisconnect:
        agents.pop(agent_id, None)

# ======================
# API: LIST AGENTS
# ======================
@app.get("/api/agents")
async def api_agents():
    now = time.time()
    out = []

    for aid, info in agents.items():
        status = "online" if now - info["last_seen"] < 15 else "offline"
        out.append({
            "id": aid,
            **info,
            "status": status
        })

    return out

# ======================
# API: AUTO SELECT
# ======================
@app.get("/api/select")
async def select_agent(mode: str = "best"):
    online = [
        a for a in agents.values()
        if time.time() - a["last_seen"] < 15 and a["latency"] is not None
    ]

    if not online:
        return JSONResponse({"error": "no agents"}, status_code=404)

    if mode == "random":
        return random.choice(online)

    # best latency
    return sorted(online, key=lambda x: x["latency"])[0]

# ======================
# UI
# ======================
@app.get("/ui", response_class=HTMLResponse)
async def ui(request):
    return templates.TemplateResponse("index.html", {"request": request})
