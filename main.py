import asyncio, os, time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException, status
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.security import HTTPBasic, HTTPBasicCredentials

app = FastAPI()
templates = Jinja2Templates(directory="templates")
security = HTTPBasic()

ADMIN_PASSWORD = "041420521"

def authenticate(credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.password != ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="كلمة مرور خاطئة",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

agents = {}        
agent_info = {}    
client_links = {}  

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, _ = Depends(authenticate)):
    now = time.time()
    # زيادة مهلة العرض لـ 45 ثانية لتقليل أثر الانقطاع اللحظي
    active_agents = {aid: info for aid, info in agent_info.items() if now - info["last_seen"] < 45}
    return templates.TemplateResponse("index.html", {"request": request, "agents": active_agents, "now": now})

@app.websocket("/ws/agent/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = ws
    agent_info[agent_id] = {"ip": ws.client.host, "last_seen": time.time()}
    try:
        while True:
            # زيادة المهلة لـ 60 ثانية لتجنب الفصل القسري
            data = await asyncio.wait_for(ws.receive_bytes(), timeout=60)
            agent_info[agent_id]["last_seen"] = time.time()
            if len(data) > 16:
                target_id, payload = data[:16], data[16:]
                for c_ws, (a_ws, c_id) in list(client_links.items()):
                    if a_ws == ws and c_id == target_id:
                        await c_ws.send_bytes(payload)
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
