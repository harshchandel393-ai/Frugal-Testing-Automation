
import asyncio
import json
import random

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pathlib import Path

app = FastAPI(title="Frugal Canvas Automation Testbed")

BASE_DIR = Path(__file__).resolve().parent

@app.get("/")
async def home():
    return FileResponse(BASE_DIR / "canvas.html")


@app.websocket("/ws")
async def websocket_stream(websocket: WebSocket):
    await websocket.accept()

    try:
        step = 0

        while True:
            step += 1

            # Controlled drift: target position changes predictably
            drift_pattern = [
                (0, 0),
                (8, 5),
                (-8, -5),
                (8, -5),
                (-8, 5),
                (0, 0)
            ]

            offset_x, offset_y = drift_pattern[(step - 1) % len(drift_pattern)]

            message = {
                "type": "state",
                "status": "active",
                "balance": 100,
                "offset_x": offset_x,
                "offset_y": offset_y,
                "sequence": step
            }

            await websocket.send_text(json.dumps(message))
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        print("Browser disconnected from WebSocket")


@app.post("/validate-state")
async def validate_state(payload: dict):
    balance = payload.get("balance")

    if type(balance) not in (int, float):
        return {
            "accepted": False,
            "error": {
                "code": "INVALID_BALANCE_TYPE",
                "message": "Balance must be numeric."
            }
        }

    if isinstance(balance, float) and not balance.is_integer():
        return {
            "accepted": False,
            "error": {
                "code": "INVALID_BALANCE_PRECISION",
                "message": "Fractional balance is not allowed."
            }
        }

    if abs(balance) > 1_000_000:
        return {
            "accepted": False,
            "error": {
                "code": "BALANCE_OUT_OF_RANGE",
                "message": "Balance exceeds permitted range."
            }
        }

    return {"accepted": True, "balance": balance}
