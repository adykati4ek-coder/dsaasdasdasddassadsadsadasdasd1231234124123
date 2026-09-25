import os
import asyncio
import time
import base64

# загрузка .env (токен бота)
def _load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.isfile(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

from aiohttp import web
from aiohttp import ClientSession

import db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Папка для загруженных изображений: на хостинге /app/data (DATA_DIR), локально — папка проекта.
DATA_DIR = os.getenv("DATA_DIR", BASE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)

IMAGE_EXT = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


async def index(request: web.Request) -> web.Response:
    return web.FileResponse(os.path.join(BASE_DIR, "index.html"))


async def static_file(request: web.Request) -> web.Response:
    name = request.match_info["name"]
    # сперва ищем среди загруженных пользователям файлов, потом в базовой папке
    path = os.path.join(DATA_DIR, name)
    if not os.path.isfile(path):
        path = os.path.join(BASE_DIR, name)
    if not os.path.isfile(path) or not name.replace("/", ""):
        raise web.HTTPNotFound()
    ext = os.path.splitext(path)[1].lower()
    content_type = IMAGE_EXT.get(ext, "application/octet-stream")
    return web.FileResponse(path, headers={"Content-Type": content_type})


def get_user(request: web.Request) -> str:
    return (request.headers.get("X-Tg-User") or "guest").strip() or "guest"


async def api_items(request: web.Request) -> web.Response:
    return web.json_response(db.list_items())


async def api_item(request: web.Request) -> web.Response:
    item = db.get_item(int(request.match_info["id"]))
    if not item:
        raise web.HTTPNotFound()
    return web.json_response(item)


async def _tg_file_url(file_id: str) -> str | None:
    """Возвращает прямую ссылку на файл Telegram (аватарку) или None."""
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        return None
    try:
        async with aiohttp.ClientSession() as s:
            r = await s.get(f"https://api.telegram.org/bot{token}/getFile", params={"file_id": file_id}, timeout=15)
            data = await r.json()
            if data.get("ok"):
                p = data["result"]["file_path"]
                return f"https://api.telegram.org/file/bot{token}/{p}"
    except Exception:
        pass
    return None


async def _tg_avatar(tg_id: str) -> str | None:
    """Достаёт первую аватарку юзера через Telegram API."""
    token = os.getenv("BOT_TOKEN", "")
    if not token:
        return None
    try:
        async with aiohttp.ClientSession() as s:
            r = await s.get(
                f"https://api.telegram.org/bot{token}/getUserProfilePhotos",
                params={"user_id": tg_id, "limit": 1},
                timeout=15,
            )
            data = await r.json()
            if data.get("ok") and data["result"]["photos"]:
                file_id = data["result"]["photos"][0][-1]["file_id"]
                return await _tg_file_url(file_id)
    except Exception:
        pass
    return None


async def api_me(request: web.Request) -> web.Response:
    """Данные текущего юзера по id: ник из БД (бот сохранил при /start)."""
    user = get_user(request)
    # авторитет — сохранённый при /start юзер
    saved = db.get_user_by_id(user) if user != "guest" else None
    if saved and saved.get("username"):
        name = "@" + saved["username"]
    else:
        raw_name = (request.headers.get("X-Tg-Name") or "").strip()
        try:
            name = unquote(raw_name) if raw_name else ""
        except Exception:
            name = raw_name
        if not name or name in ("guest", "@guest"):
            name = saved.get("full_name") or saved.get("username") or user
    photo = ""
    if user != "guest" and user.isdigit():
        photo = await _tg_avatar(user) or ""
    return web.json_response({"id": user, "name": name, "username": (saved.get("username") if saved else ""), "photo": photo})


async def api_favs(request: web.Request) -> web.Response:
    user = get_user(request)
    return web.json_response(db.get_favs(user))


async def api_fav_toggle(request: web.Request) -> web.Response:
    user = get_user(request)
    data = await request.json()
    item_id = int(data.get("item_id", 0))
    return web.json_response(db.toggle_fav(user, item_id))


async def api_sell(request: web.Request) -> web.Response:
    data = await request.json()
    name = (data.get("name") or "").strip()
    price = int(data.get("price") or 0)
    game = data.get("game") or "mm2"
    seller = (data.get("seller") or "").strip()
    desc = (data.get("desc") or "").strip()
    photos = data.get("photos") or []

    if not name or price <= 0 or not photos:
        return web.json_response({"error": "Заполни название, цену и добавь фото"}, status=400)
    # продавец по id юзера; настоящий @ник берём из таблицы users (бот сохранил при /start)
    user_id = get_user(request)
    saved = db.get_user_by_id(user_id) if user_id != "guest" else None
    if saved and saved.get("username"):
        seller = "@" + saved["username"]
    elif saved and saved.get("full_name"):
        seller = saved["full_name"]
    elif user_id and user_id != "guest":
        seller = user_id
    else:
        seller = seller.strip() or "guest"

    img = photos[0]
    if img.startswith("data:image"):
        meta, b64 = img.split(",", 1)
        ext = "png" if "png" in meta else "jpg"
        fname = "item-upload-{}_{}.{}".format(abs(hash(name + seller)) & 0xFFFF, int(time.time()) % 10000, ext)
        data_bytes = base64.b64decode(b64)
        with open(os.path.join(DATA_DIR, fname), "wb") as f:
            f.write(data_bytes)
        img = fname

    new_id = db.add_item(
        name=name,
        price=price,
        game=game,
        seller=seller,
        img=img,
        photos=len(photos),
        desc=desc,
    )
    return web.json_response({"id": new_id, "ok": True, "seller": seller})


def make_app() -> web.Application:
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/api/items", api_items)
    app.router.add_get("/api/items/{id}", api_item)
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/favs", api_favs)
    app.router.add_post("/api/favs/toggle", api_fav_toggle)
    app.router.add_post("/api/sell", api_sell)
    app.router.add_get("/{name:.*}", static_file)
    return app


async def start_bot():
    from bot import run_bot_polling
    await run_bot_polling()


async def main():
    db.init_db()
    app = make_app()
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"Веб-сервер запущен на http://0.0.0.0:{port}")
    asyncio.create_task(start_bot())
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nОстановлено.")
