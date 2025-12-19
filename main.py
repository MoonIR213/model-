from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from datetime import datetime
import time

app = FastAPI(title="Central Agent Control")

clients = {}
commands = {}
connections = set()

# ------------------- API -------------------

@app.get("/")
def root():
    return {"status": "running", "time": str(datetime.now())}

@app.post("/register")
async def register(req: Request):
    data = await req.json()
    cid = data.get("agent_id") or "unknown"

    clients[cid] = {
        "ip": req.client.host,
        "hostname": data.get("hostname"),
        "local_ip": data.get("local_ip"),
        "started_at": data.get("started_at"),
        "last_seen": str(datetime.now()),
        "status": "online"
    }

    await broadcast()
    return {"registered": cid}

@app.post("/heartbeat")
async def heartbeat(req: Request):
    data = await req.json()
    cid = data.get("agent_id")
    if cid in clients:
        clients[cid]["last_seen"] = str(datetime.now())
        clients[cid]["status"] = "online"
        await broadcast()
    return {"ok": True}

@app.get("/agents")
def get_agents():
    return clients

# ------------------- Commands -------------------

@app.post("/command")
async def send_command(req: Request):
    data = await req.json()
    aid = data["agent_id"]
    cmd = data["command"]

    commands.setdefault(aid, []).append({
        "command": cmd,
        "time": str(datetime.now())
    })
    return {"sent": True}

@app.get("/command/{agent_id}")
def get_command(agent_id: str):
    if agent_id in commands and commands[agent_id]:
        return commands[agent_id].pop(0)
    return {}

# ------------------- WebSocket -------------------

@app.websocket("/ws")
async def ws(ws: WebSocket):
    await ws.accept()
    connections.add(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        connections.remove(ws)

async def broadcast():
    dead = []
    for ws in connections:
        try:
            await ws.send_json(clients)
        except:
            dead.append(ws)
    for ws in dead:
        connections.remove(ws)

# ------------------- Dashboard -------------------

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    return """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Agent Dashboard</title>
<style>
body{background:#0b0f14;color:#e5e7eb;font-family:Arial}
h2{margin:15px}
input{padding:6px;background:#020617;color:white;border:1px solid #334155}
table{width:100%;border-collapse:collapse}
th,td{padding:8px;border-bottom:1px solid #1f2937}
th{background:#111827;cursor:pointer}
tr:hover{background:#1f2937}
.online{color:#22c55e}
.offline{color:#ef4444}
</style>
</head>
<body>

<h2>🖥️ Agent Control Dashboard</h2>
<input id="q" placeholder="Search hostname">

<table>
<thead>
<tr>
<th>ID</th>
<th>Hostname</th>
<th>Local IP</th>
<th>Status</th>
<th>Uptime</th>
<th>Action</th>
</tr>
</thead>
<tbody id="rows"></tbody>
</table>

<script>
let agents = {};

function uptime(start){
 if(!start) return '';
 let s=Math.floor((Date.now()-Date.parse(start))/1000);
 return Math.floor(s/60)+' min';
}

function render(){
 let q=document.getElementById('q').value.toLowerCase();
 let tbody=document.getElementById('rows');
 tbody.innerHTML='';
 Object.keys(agents).forEach(id=>{
  let a=agents[id];
  if(q && !(a.hostname||'').toLowerCase().includes(q)) return;
  let tr=document.createElement('tr');
  tr.innerHTML=`
   <td>${id.slice(0,8)}…</td>
   <td>${a.hostname||''}</td>
   <td>${a.local_ip||''}</td>
   <td class="${a.status}">${a.status}</td>
   <td>${uptime(a.started_at)}</td>
   <td><button onclick="ping('${id}')">Ping</button></td>
  `;
  tbody.appendChild(tr);
 });
}

function ping(id){
 fetch('/command',{method:'POST',headers:{'Content-Type':'application/json'},
 body:JSON.stringify({agent_id:id,command:'ping'})});
}

document.getElementById('q').onkeyup=render;

let ws=new WebSocket((location.protocol==='https:'?'wss':'ws')+'://'+location.host+'/ws');
ws.onmessage=e=>{agents=JSON.parse(e.data);render();}
</script>

</body>
</html>
"""
