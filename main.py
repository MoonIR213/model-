# agent_tcp_relay_fixed.py
import asyncio, websockets, json, socket, base64

AGENT_ID = "oran_pc"
SERVER = "wss://web-production-d9bf.up.railway.app/ws/" + AGENT_ID

async def tcp_relay(ws, session_id, host, port):
    loop = asyncio.get_event_loop()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setblocking(False)
    await loop.sock_connect(sock, (host, port))

    async def from_target():
        try:
            while True:
                data = await loop.sock_recv(sock, 4096)
                if not data:
                    break
                await ws.send(json.dumps({
                    "type": "tcp_data",
                    "sid": session_id,
                    "data": base64.b64encode(data).decode("ascii")
                }))
        finally:
            await ws.send(json.dumps({
                "type": "tcp_close",
                "sid": session_id
            }))

    await from_target()
    sock.close()

async def run():
    while True:
        try:
            async with websockets.connect(SERVER, ping_interval=20) as ws:
                print("[AGENT] Connected")

                while True:
                    msg = json.loads(await ws.recv())

                    if msg["type"] == "tcp_open":
                        asyncio.create_task(
                            tcp_relay(
                                ws,
                                msg["sid"],
                                msg["host"],
                                msg["port"]
                            )
                        )

                    elif msg["type"] == "tcp_data":
                        # هذه البيانات قادمة من العميل → الهدف
                        pass

        except Exception as e:
            print("Reconnect in 5s:", e)
            await asyncio.sleep(5)

asyncio.run(run())
