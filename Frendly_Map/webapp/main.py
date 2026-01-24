# webapp/main.py
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

from .api import map, tag

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
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")
templates = Jinja2Templates(directory="webapp/static")

# Подключаем API
app.include_router(map.router, prefix="/api/map")
app.include_router(tag.router, prefix="/api/tag")

@app.get("/map")
async def map_page(request: Request):
    """Страница карты Web App"""
    return templates.TemplateResponse("map.html", {"request": request})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
