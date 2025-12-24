# server_full.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
import json, uuid, time, random, asyncio
import httpx

app = FastAPI()

# =========================
# Storage (قابل لآلاف Agents)
# =========================
agents = {}     # agent_id -> info
clients = {}    # session_id -> client websocket


# =========================
# HTTP root (مهم لـ Railway)
# =========================
@app.get("/")
async def root():
    return PlainTextResponse("OK")


# =========================
# GeoIP enrichment
# =========================
async def enrich_agent(agent_id):
    ip = agents[agent_id]["ip"]
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            r = await c.get(f"http://ip-api.com/json/{ip}")
            j = r.json()
            agents[agent_id].update({
                "country": j.get("countryCode", "??"),
                "city": j.get("city", "Unknown")
            })
    except:
        agents[agent_id].update({
            "country": "??",
            "city": "Unknown"
        })


# =========================
# API: list agents
# =========================
@app.get("/api/agents")
async def list_agents():
    now = time.time()
    out = []
    for aid, info in agents.items():
        out.append({
            "agent_id": aid,
            "ip": info["ip"],
            "country": info.get("country", "??"),
            "city": info.get("city", "Unknown"),
            "status": "online",
            "connected_at": info["connected_at"],
            "latency": info.get("latency", None)
        })
    return out


# =========================
# API: random agent
# =========================
@app.get("/api/agent/random")
async def pick_random_agent():
    if not agents:
        return {"error": "no agents"}
    return {"agent_id": random.choice(list(agents.keys()))}


# =========================
# API: best agent (latency)
# =========================
@app.get("/api/agent/best")
async def pick_best_agent():
    if not agents:
        return {"error": "no agents"}
    best = sorted(
        agents.items(),
        key=lambda x: x[1].get("latency", 9999)
    )[0][0]
    return {"agent_id": best}


# =========================
# WebSocket: Agent
# =========================
@app.websocket("/ws/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()

    agents[agent_id] = {
        "ws": ws,
        "ip": ws.client.host,
        "connected_at": int(time.time()),
        "latency": random.randint(20, 400)  # مؤقت (يمكن تحسينه لاحقًا)
    }

    asyncio.create_task(enrich_agent(agent_id))
    print(f"[SERVER] Agent {agent_id} connected from {ws.client.host}")

    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)

            sid = data.get("sid")
            if sid and sid in clients:
                await clients[sid].send_text(msg)

    except WebSocketDisconnect:
        print(f"[SERVER] Agent disconnected: {agent_id}")
        agents.pop(agent_id, None)


# =========================
# WebSocket: TCP Client
# =========================
@app.websocket("/tcp/{agent_id}")
async def tcp_client(ws: WebSocket, agent_id: str):
    await ws.accept()

    if agent_id not in agents:
        await ws.close()
        return

    agent_ws = agents[agent_id]["ws"]
    sid = str(uuid.uuid4())
    clients[sid] = ws

    try:
        first = json.loads(await ws.receive_text())

        await agent_ws.send_text(json.dumps({
            "type": "tcp_open",
            "sid": sid,
            "host": first["host"],
            "port": first["port"]
        }))

        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)
            data["sid"] = sid
            await agent_ws.send_text(json.dumps(data))

    except WebSocketDisconnect:
        await agent_ws.send_text(json.dumps({
            "type": "tcp_close",
            "sid": sid
        }))
        clients.pop(sid, None)
# server_tcp_relay_full_with_ips.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import PlainTextResponse
import json, uuid, time

app = FastAPI()

# =========================
# Storage
# =========================
agents = {}     # agent_id -> {ws, ip, connected_at}
clients = {}    # session_id -> client websocket


# =========================
# HTTP root (مهم لـ Railway)
# =========================
@app.get("/")
async def root():
    return PlainTextResponse("OK")


# =========================
# API: عرض الآيبيات المتصلة
# =========================
@app.get("/api/agents")
async def list_agents():
    return [
        {
            "agent_id": aid,
            "ip": info["ip"],
            "connected_at": info["connected_at"]
        }
        for aid, info in agents.items()
    ]


# =========================
# WebSocket: Agent
# =========================
@app.websocket("/ws/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()

    agents[agent_id] = {
        "ws": ws,
        "ip": ws.client.host,
        "connected_at": int(time.time())
    }

    print(f"[SERVER] Agent {agent_id} connected from {ws.client.host}")

    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)

            sid = data.get("sid")
            if sid and sid in clients:
                await clients[sid].send_text(msg)

    except WebSocketDisconnect:
        print(f"[SERVER] Agent disconnected: {agent_id}")
        agents.pop(agent_id, None)


# =========================
# WebSocket: TCP Client
# =========================
@app.websocket("/tcp/{agent_id}")
async def tcp_client(ws: WebSocket, agent_id: str):
    await ws.accept()

    if agent_id not in agents:
        await ws.close()
        return

    agent_ws = agents[agent_id]["ws"]
    session_id = str(uuid.uuid4())
    clients[session_id] = ws

    print(f"[SERVER] TCP session {session_id} via {agent_id}")

    try:
        # أول رسالة = target
        first = json.loads(await ws.receive_text())

        await agent_ws.send_text(json.dumps({
            "type": "tcp_open",
            "sid": session_id,
            "host": first["host"],
            "port": first["port"]
        }))

        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)
            data["sid"] = session_id
            await agent_ws.send_text(json.dumps(data))

    except WebSocketDisconnect:
        await agent_ws.send_text(json.dumps({
            "type": "tcp_close",
            "sid": session_id
        }))
        clients.pop(session_id, None)
        print(f"[SERVER] TCP session closed {session_id}")
