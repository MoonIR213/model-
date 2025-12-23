from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# agent_id -> agent data
agents = {}

# =======================
# UI
# =======================
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "agents": list(agents.values())}
    )

# =======================
# STATUS
# =======================
@app.get("/status")
async def status():
    return {"status": "Online", "agents": len(agents)}

# =======================
# REGISTER (HTTP)
# =======================
@app.post("/agent/register")
async def register_agent(data: dict):
    agent_id = data["agent_id"]

    agents[agent_id] = {
        "agent_id": agent_id,
        "ip": data.get("ip", "unknown"),
        "country": data.get("country", "N/A"),
        "city": data.get("city", "N/A"),
        "type": data.get("type", "HTTP"),
        "latency": None,
        "status": "online",
        "ws": None
    }
    return {"ok": True}

# =======================
# WEBSOCKET (الحقيقة المطلقة)
# =======================
@app.websocket("/ws/{agent_id}")
async def ws_agent(websocket: WebSocket, agent_id: str):
    await websocket.accept()

    if agent_id not in agents:
        await websocket.close()
        return

    agents[agent_id]["ws"] = websocket
    agents[agent_id]["status"] = "online"
    print(f"[WS CONNECTED] {agent_id}")

    try:
        while True:
            await websocket.receive_text()  # keep alive
    except WebSocketDisconnect:
        print(f"[WS DISCONNECTED] {agent_id}")
        agents[agent_id]["status"] = "offline"
        agents[agent_id]["ws"] = None
