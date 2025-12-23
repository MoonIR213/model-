from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# =========================
# STORAGE
# =========================
agents = {}  # agent_id -> data

# =========================
# UI
# =========================
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request}
    )

# =========================
# API: LIST AGENTS (🔥 هذا كان ناقص)
# =========================
@app.get("/agents")
async def list_agents():
    return list(agents.values())

# =========================
# REGISTER AGENT
# =========================
@app.post("/agent/register")
async def register_agent(data: dict):
    agent_id = data["agent_id"]

    agents[agent_id] = {
        "agent_id": agent_id,
        "ip": data.get("ip", "unknown"),
        "type": data.get("type", "HTTP"),
        "country": data.get("country", "N/A"),
        "city": data.get("city", "N/A"),
        "latency": None,
        "status": "online"
    }

    return {"ok": True}

# =========================
# WEBSOCKET (الحالة الحقيقية)
# =========================
@app.websocket("/ws/{agent_id}")
async def ws_agent(websocket: WebSocket, agent_id: str):
    await websocket.accept()

    if agent_id not in agents:
        await websocket.close()
        return

    agents[agent_id]["status"] = "online"
    print(f"[CONNECTED] {agent_id}")

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        print(f"[DISCONNECTED] {agent_id}")
        agents[agent_id]["status"] = "offline"
