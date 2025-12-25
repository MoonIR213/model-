import asyncio
import websockets
import struct
import os

SHARED_SECRET = b"SUPER_SECRET_TOKEN_32_BYTES_MAX_"
# ... إعدادات الاتصال ...

async def rotate_proxy(ws):
    # الهيدر: [16B Random ID][OP_ROTATE][Length of Secret][Secret]
    client_id = os.urandom(16)
    header = client_id + struct.pack(">BI", 0x01, len(SHARED_SECRET))
    await ws.send(header + SHARED_SECRET)

async def send_data(ws, client_id, data_bytes):
    # الهيدر: [ID][OP_DATA][Length][Payload]
    header = client_id + struct.pack(">BI", 0x02, len(data_bytes))
    await ws.send(header + data_bytes)
