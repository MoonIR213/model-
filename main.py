import asyncio
import os
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

app = FastAPI()

# إعداد المجلد للقوالب (تأكد من وجود مجلد باسم templates)
templates = Jinja2Templates(directory="templates")

agents = {}        # agent_id -> WebSocket
agent_info = {}    # agent_id -> {ip, last_seen}
client_links = {}  # client_ws -> (agent_ws, client_id_bytes)

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    now = time.time()
    # تنظيف الوكلاء غير النشطين
    active_agents = {aid: info for aid, info in agent_info.items() if now - info["last_seen"] < 30}
    return templates.TemplateResponse("index.html", {"request": request, "agents": active_agents, "now": now})

@app.websocket("/ws/agent/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = ws
    agent_info[agent_id] = {"ip": ws.client.host, "last_seen": time.time()}
    try:
        while True:
            data = await ws.receive_bytes()
            agent_info[agent_id]["last_seen"] = time.time()
            if len(data) > 16:
                target_id = data[:16]
                for c_ws, (a_ws, c_id) in list(client_links.items()):
                    if a_ws == ws and c_id == target_id:
                        await c_ws.send_bytes(data[16:])
    except: pass
    finally:
        agents.pop(agent_id, None)
        agent_info.pop(agent_id, None)

@app.websocket("/ws/client/{agent_id}")
async def ws_client(ws: WebSocket, agent_id: str):
    await ws.accept()
    agent_ws = agents.get(agent_id)
    if not agent_ws:
        await ws.close(); return
    c_id = os.urandom(16)
    client_links[ws] = (agent_ws, c_id)
    try:
        while True:
            payload = await ws.receive_bytes()
            await agent_ws.send_bytes(c_id + payload)
    except: pass
    finally: client_links.pop(ws, None)
