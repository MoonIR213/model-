from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
import uuid
import asyncio
import json

app = FastAPI()
templates = Jinja2Templates(directory="templates")

agents = {}          # agent_id -> websocket
pending = {}         # request_id -> future


@app.get("/")
async def dashboard(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "agents": list(agents.keys())}
    )


@app.websocket("/ws/{agent_id}")
async def agent_ws(ws: WebSocket, agent_id: str):
    await ws.accept()
    agents[agent_id] = ws
    print(f"[AGENT CONNECTED] {agent_id}")

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)

            if msg["type"] == "proxy_response":
                rid = msg["request_id"]
                if rid in pending:
                    pending[rid].set_result(msg)

    except WebSocketDisconnect:
        print(f"[AGENT DISCONNECTED] {agent_id}")
        agents.pop(agent_id, None)


@app.api_route("/proxy/{agent_id}", methods=["GET", "POST"])
async def proxy(agent_id: str, request: Request):
    if agent_id not in agents:
        return {"error": "Agent offline"}

    body = await request.body()
    request_id = str(uuid.uuid4())

    payload = {
        "type": "proxy_request",
        "request_id": request_id,
        "method": request.method,
        "url": str(request.query_params.get("url")),
        "headers": dict(request.headers),
        "body": body.decode(errors="ignore")
    }

    loop = asyncio.get_event_loop()
    future = loop.create_future()
    pending[request_id] = future

    await agents[agent_id].send_text(json.dumps(payload))

    try:
        result = await asyncio.wait_for(future, timeout=60)
    except asyncio.TimeoutError:
        pending.pop(request_id, None)
        return {"error": "Timeout"}

    pending.pop(request_id, None)

    return Response(
        content=result["body"],
        status_code=result["status"],
        headers=result.get("headers", {})
    )
