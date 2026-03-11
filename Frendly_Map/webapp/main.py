# webapp/main.py
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from bot.database import init_db
from webapp.config import settings

from .api import map, tag

app = FastAPI(title="Friendly Map Web App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
static_dir = BASE_DIR / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")
templates = Jinja2Templates(directory=static_dir)

app.include_router(map.router, prefix="/api/map")
app.include_router(tag.router, prefix="/api/tag")


@app.on_event("startup")
async def on_startup():
    init_db()


@app.get("/map")
async def map_page(request: Request):
    return templates.TemplateResponse(
        "map.html",
        {
            "request": request,
            "default_lat": settings.DEFAULT_MAP_LAT,
            "default_lng": settings.DEFAULT_MAP_LNG,
            "default_zoom": settings.DEFAULT_MAP_ZOOM,
        },
    )


@app.get("/shop")
async def shop_page():
    return {"message": "Магазин пока закрыт"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
