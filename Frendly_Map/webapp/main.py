# webapp/main.py
from pathlib import Path
import hashlib
import hmac
import json
from urllib.parse import parse_qsl

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from bot.database import init_db
from webapp.config import settings
from bot.database import get_db_context
from bot.models.webapp_pick import WebAppPick

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
    picker_mode = request.query_params.get("picker") == "1"

    focus_lat = request.query_params.get("focus_lat")
    focus_lng = request.query_params.get("focus_lng")
    focus_name = request.query_params.get("focus_name") or "Точка"
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
        },
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def _validate_telegram_init_data(init_data: str) -> dict:
    if not init_data:
        raise HTTPException(status_code=400, detail="init_data is required")

    pairs = parse_qsl(init_data, keep_blank_values=True)
    data = dict(pairs)
    provided_hash = data.pop("hash", None)
    if not provided_hash:
        raise HTTPException(status_code=400, detail="Missing hash in init_data")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(data.items()))
    secret = hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed_hash = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed_hash, provided_hash):
        raise HTTPException(status_code=403, detail="Invalid Telegram init_data")

    user_raw = data.get("user")
    if not user_raw:
        raise HTTPException(status_code=400, detail="Missing user in init_data")

    try:
        return json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid user payload") from exc


@app.post("/api/webapp/picker/confirm")
async def confirm_picker_point(request: Request):
    payload = await request.json()

    init_data = payload.get("init_data") or ""
    user_payload = _validate_telegram_init_data(init_data)

    user_id = int(user_payload["id"])
    chat_id = int(payload.get("chat_id") or user_id)
    latitude = float(payload["latitude"])
    longitude = float(payload["longitude"])

    with get_db_context() as db:
        db.query(WebAppPick).filter(
            WebAppPick.user_id == user_id,
            WebAppPick.chat_id == chat_id,
            WebAppPick.flow == "add_location",
            WebAppPick.processed.is_(False),
        ).delete()
        db.add(
            WebAppPick(
                user_id=user_id,
                chat_id=chat_id,
                flow="add_location",
                latitude=latitude,
                longitude=longitude,
                processed=False,
            )
        )
        db.commit()

    return {"ok": True}


@app.get("/shop")
async def shop_page():
    return {"message": "Магазин пока закрыт"}


@app.get("/favicon.ico")
async def favicon():
    return Response(status_code=204)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
