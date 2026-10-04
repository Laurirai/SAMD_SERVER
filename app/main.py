from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request

from app.mqtt import start_mqtt
from app.state import session
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.mqtt import start_mqtt

COMMANDS = {"start", "pause", "continue", "stop"}

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "statics"

@asynccontextmanager
async def lifespan(app: FastAPI):
    mqtt_client = start_mqtt()
    app.state.mqtt_client = mqtt_client

    try:
        yield
    finally:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()


app = FastAPI(lifespan=lifespan)

app.mount("/statics", StaticFiles(directory=STATIC_DIR), name="statics")


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")

@app.get("/api/state")
def get_state(since: int = 0, session_id: int | None = None):
    return session.snapshot(since, session_id)

@app.post("/api/cmd/{command}")
def send_command(command: str, request: Request):
    if command not in COMMANDS:
        raise HTTPException(status_code=404, detail="Unknown command")
    request.app.state.mqtt_client.publish("sleep/cmd", command)
    return {"sent": command}