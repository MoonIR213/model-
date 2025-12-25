# =========================
# server.py  (TCP Relay)
# =========================

import asyncio
import json
import time
import base64
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# =========================
# STORAGE
# =========================

agents = {}          # agent_id -> agent websocket
agent_info = {}     # agent_id -> {ip, city, last_seen}
client_links = {}   # client_ws -> agent_ws


# =========================
# ROOT
# =========================

@app.get("/")
async def root():
    return {"status": "OK"}


# =========================
# API
# =========================

@app.get("/api/agents")
async def api_agents():
    now = time.time()
    result = []

    for aid, info in agent_info.items():
        result.append({
            "id": aid,
            "status": "online" if now - info["last_seen"] < 20 else "offline",
            "ip": info.get("ip"),
            "city": info.get("city", "Unknown"),
            "last_seen": info["last_seen"]
        })

    return result


# =========================
# DASHBOARD
# =========================

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "agents": agent_info,
            "now": time.time()
        }
    )


# =========================
# AGENT WEBSOCKET
# =========================

@app.websocket("/ws/agent/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    client_ip = ws.client.host

    agents[agent_id] = ws
    agent_info[agent_id] = {
        "ip": client_ip,
        "city": "Unknown",
        "last_seen": time.time()
    }

    print(f"[AGENT CONNECTED] {agent_id} from {client_ip}")

    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)

            agent_info[agent_id]["last_seen"] = time.time()

            # Forward TCP data to linked client
            for client_ws, agent_ws in list(client_links.items()):
                if agent_ws == ws:
                    await client_ws.send_text(msg)

            # Ping / Pong
            if data.get("type") == "ping":
                await ws.send_text(json.dumps({
                    "type": "pong",
                    "timestamp": time.time()
                }))

    except WebSocketDisconnect:
        print(f"[AGENT DISCONNECTED] {agent_id}")

    finally:
        agents.pop(agent_id, None)
        agent_info.pop(agent_id, None)


# =========================
# CLIENT WEBSOCKET
# =========================

@app.websocket("/ws/client/{agent_id}")
async def ws_client(ws: WebSocket, agent_id: str):
    await ws.accept()

    agent_ws = agents.get(agent_id)
    if not agent_ws:
        await ws.close()
        return

    client_links[ws] = agent_ws
    print(f"[CLIENT CONNECTED] using agent {agent_id}")

    async def client_to_agent():
        try:
            while True:
                msg = await ws.receive_text()
                await agent_ws.send_text(msg)
        except:
            pass

    async def agent_to_client():
        try:
            while True:
                msg = await agent_ws.receive_text()
                await ws.send_text(msg)
        except:
            pass

    try:
        await asyncio.gather(
            client_to_agent(),
            agent_to_client()
        )
    finally:
        client_links.pop(ws, None)
        print("[CLIENT DISCONNECTED]")
