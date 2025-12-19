from fastapi import FastAPI, Request
from datetime import datetime

app = FastAPI(title="Central Remote Server")

clients = {}

@app.get("/")
def root():
    return {"status": "running", "time": str(datetime.now())}

@app.post("/register")
async def register(request: Request):
    data = await request.json()
    cid = data.get("client_id", "unknown")
    clients[cid] = {
        "ip": request.client.host,
        "last_seen": str(datetime.now())
    }
    return {"status": "ok", "client_id": cid}

@app.get("/clients")
def get_clients():
    return clients
