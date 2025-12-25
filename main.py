# server.py
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
agents = {}        # agent_id -> WebSocket
agent_info = {}   # agent_id -> info
client_links = {} # client_ws -> agent_ws


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
    out = []
    for aid, info in agent_info.items():
        out.append({
            "id": aid,
            "ip": info["ip"],
            "status": "online" if now - info["last_seen"] < 20 else "offline",
            "last_seen": info["last_seen"]
        })
    return out


# =========================
# DASHBOARD
# =========================
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "agents": agent_info}
    )


# =========================
# AGENT WS
# =========================
@app.websocket("/ws/agent/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    ip = ws.client.host

    agents[agent_id] = ws
    agent_info[agent_id] = {
        "ip": ip,
        "last_seen": time.time()
    }

    print(f"[AGENT] {agent_id} connected from {ip}")

    try:
        while True:
            msg = await ws.receive_text()
            data = json.loads(msg)
            agent_info[agent_id]["last_seen"] = time.time()

            # ping / pong
            if data.get("type") == "ping":
                await ws.send_text(json.dumps({
                    "type": "pong",
                    "ts": time.time()
                }))

            # relay to client
            if data.get("type") == "tcp_data":
                for cws, aws in client_links.items():
                    if aws == ws:
                        await cws.send_text(msg)

    except WebSocketDisconnect:
        print(f"[AGENT] {agent_id} disconnected")

    finally:
        agents.pop(agent_id, None)
        agent_info.pop(agent_id, None)


# =========================
# CLIENT WS (Relay)
# =========================
@app.websocket("/ws/client/{agent_id}")
async def ws_client(ws: WebSocket, agent_id: str):
    await ws.accept()

    agent_ws = agents.get(agent_id)
    if not agent_ws:
        await ws.close()
        return

    client_links[ws] = agent_ws
    print(f"[CLIENT] linked to {agent_id}")

    try:
        while True:
            msg = await ws.receive_text()
            await agent_ws.send_text(msg)

    except WebSocketDisconnect:
        pass

    finally:
        client_links.pop(ws, None)
        print("[CLIENT] disconnected")
