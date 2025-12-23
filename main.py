from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import uuid, time, asyncio

app = FastAPI()
templates = Jinja2Templates(directory="templates")

agents = {}               # agent_id -> {ws, last_seen, info}
pending = {}              # request_id -> Future
OFFLINE_AFTER = 15        # seconds


# =========================
# UI
# =========================
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request
    })


# =========================
# Health
# =========================
@app.get("/health")
def health():
    return {"status": "OK", "message": "Railway Tunnel Server Running"}


# =========================
# Agents list (for UI)
# =========================
@app.get("/agents")
def list_agents():
    now = time.time()
    result = []
    for aid, a in agents.items():
        status = "online" if now - a["last_seen"] < OFFLINE_AFTER else "offline"
        data = a["info"].copy()
        data["agent_id"] = aid
        data["status"] = status
        result.append(data)
    return result


# =========================
# HTTP/HTTPS Tunnel
# =========================
@app.api_route("/proxy/{agent_id}", methods=["GET", "POST", "PUT", "DELETE"])
async def proxy(agent_id: str, request: Request):
    if agent_id not in agents:
        return JSONResponse({"error": "Agent offline"}, 404)

    request_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    pending[request_id] = fut

    payload = {
        "type": "proxy_request",
        "request_id": request_id,
        "method": request.method,
        "url": str(request.query_params.get("url")),
        "headers": dict(request.headers),
        "body": (await request.body()).decode(errors="ignore")
    }

    await agents[agent_id]["ws"].send_json(payload)

    try:
        res = await asyncio.wait_for(fut, timeout=30)
        return JSONResponse(
            content=res["body"],
            status_code=res["status"],
            headers=res["headers"]
        )
    except asyncio.TimeoutError:
        return JSONResponse({"error": "Agent timeout"}, 504)
    finally:
        pending.pop(request_id, None)


# =========================
# WebSocket Agent
# =========================
@app.websocket("/ws/{agent_id}")
async def ws_agent(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = {
        "ws": ws,
        "last_seen": time.time(),
        "info": {}
    }
    print(f"[+] Agent connected: {agent_id}")

    try:
        while True:
            data = await ws.receive_json()

            if data.get("type") == "hello":
                agents[agent_id]["info"] = data
                agents[agent_id]["last_seen"] = time.time()

            elif data.get("type") == "proxy_response":
                rid = data["request_id"]
                if rid in pending:
                    pending[rid].set_result(data)

            else:
                agents[agent_id]["last_seen"] = time.time()

    except WebSocketDisconnect:
        print(f"[-] Agent disconnected: {agent_id}")
        agents.pop(agent_id, None)
