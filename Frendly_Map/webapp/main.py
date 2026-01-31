# webapp/main.py
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from .api import map, tag
from bot.database import init_db

app = FastAPI(title="Friendly Map Web App")

# CORS (можно ограничить доменом в продакшене)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Статические файлы и шаблоны
BASE_DIR = Path(__file__).resolve().parent
static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=static_dir)

# Подключаем API
app.include_router(map.router, prefix="/api/map")
app.include_router(tag.router, prefix="/api/tag")

@app.on_event("startup")
async def on_startup():
    init_db()

@app.get("/map")
async def map_page(request: Request):
    """Страница карты Web App"""
    return templates.TemplateResponse("map.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
