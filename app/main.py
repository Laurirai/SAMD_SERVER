
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

BASE_DIR = Path(__file__).resolve().parent
PROJECT_DIR = BASE_DIR.parent
STATIC_DIR = BASE_DIR / "statics"
DATA_FILE = PROJECT_DIR / "test_session.json"

app.mount("/statics", StaticFiles(directory=STATIC_DIR), name="statics")


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/test-data")
def get_test_data():
    with DATA_FILE.open("r", encoding="utf-8") as file:
        return json.load(file)