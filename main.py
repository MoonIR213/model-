from fastapi import FastAPI, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from datetime import datetime
from typing import Dict

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# ======================
# إعدادات الدخول
# ======================
ADMIN_USER = "admin"
ADMIN_PASS = "123456"

def is_logged_in(request: Request) -> bool:
    return request.cookies.get("session") == "active"

# ======================
# تخزين الأجهزة
# ======================
agents: Dict[str, dict] = {}

# ======================
# استخراج IP الحقيقي
# ======================
def get_real_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host

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
        {"request": request}
    )

# ======================
# Login / Logout
# ======================
@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        resp = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
        resp.set_cookie("session", "active", httponly=True)
        return resp
    return HTMLResponse("Access Denied", status_code=401)

@app.get("/logout")
async def logout():
    resp = RedirectResponse("/")
    resp.delete_cookie("session")
    return resp

# ======================
# Register Agent (IP حقيقي)
# ======================
@app.post("/register")
async def register_agent(request: Request, data: dict):
    agent_id = data.get("agent_id")
    if not agent_id:
        return JSONResponse({"error": "agent_id required"}, status_code=400)

    real_ip = get_real_ip(request)

    agents[agent_id] = {
        "agent_id": agent_id,
        "ip": real_ip,
        "hostname": data.get("hostname", ""),
        "last_seen": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "status": "online"
    }

    return {"status": "registered", "ip": real_ip}

# ======================
# تحديث الحالة
# ======================
@app.post("/heartbeat")
async def heartbeat(request: Request, data: dict):
    agent_id = data.get("agent_id")
    if agent_id in agents:
        agents[agent_id]["last_seen"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        agents[agent_id]["status"] = "online"
    return {"status": "ok"}

# ======================
# API عرض الأجهزة (IP حقيقي فقط)
# ======================
@app.get("/api/agents")
async def get_agents():
    return list(agents.values())
