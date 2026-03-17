# webapp/main.py
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from webapp.config import settings
from webapp.database import init_db

from .api import map, tag, webapp

app = FastAPI(title="Friendly Map Web App")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
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
app.include_router(webapp.router, prefix="/api/webapp")


@app.on_event("startup")
async def on_startup():
    init_db()


@app.get("/map")
async def map_page(request: Request):
    picker_mode = request.query_params.get("picker") == "1"

    focus_lat = request.query_params.get("focus_lat")
    focus_lng = request.query_params.get("focus_lng")
    focus_name = request.query_params.get("focus_name") or "Точка"
    picker_chat_id = request.query_params.get("chat_id")
    focus_point = None
    if focus_lat and focus_lng:
        try:
            focus_point = {
                "lat": float(focus_lat),
                "lng": float(focus_lng),
                "name": focus_name,
            }
        except ValueError:
            focus_point = None

    response = templates.TemplateResponse(
        "map.html",
        {
            "request": request,
            "default_lat": settings.DEFAULT_MAP_LAT,
            "default_lng": settings.DEFAULT_MAP_LNG,
            "default_zoom": settings.DEFAULT_MAP_ZOOM,
            "picker_mode": picker_mode,
            "focus_point": focus_point,
            "picker_chat_id": picker_chat_id,
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@app.get("/shop")
async def shop_page():
    return {"message": "Магазин пока закрыт"}


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
