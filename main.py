from fastapi import FastAPI, Request
from datetime import datetime

app = FastAPI(title="Central Remote Server")

# تخزين الأجهزة
clients = {}

@app.get("/")
def root():
    return {
        "status": "running",
        "time": str(datetime.now())
    }

@app.post("/register")
async def register(request: Request):
    data = await request.json()

    # 🔧 حل مشكلة unknown
    cid = data.get("agent_id") or data.get("client_id") or "unknown"

    clients[cid] = {
        "ip": request.client.host,
        "hostname": data.get("hostname"),
        "local_ip": data.get("local_ip"),
        "started_at": data.get("started_at"),
        "last_seen": str(datetime.now())
    }

    return {
        "status": "registered",
        "agent_id": cid
    }

@app.get("/clients")
def list_clients():
    return clients

@app.post("/heartbeat")
async def heartbeat(request: Request):
    data = await request.json()
    cid = data.get("agent_id")

    if cid in clients:
        clients[cid]["last_seen"] = str(datetime.now())
        clients[cid]["status"] = "online"

    return {"ok": True}
