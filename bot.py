import os
import logging

# загрузка .env
def _load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.isfile(env_path):
        for line in open(env_path, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

import db

logger = logging.getLogger(__name__)
router = Router()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# домен мини-аппа (можно переопределить через переменную окружения WEBAPP_URL)
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://bot-1790370212-3509-adykat.bothost.tech/")


def open_app_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text="🛍 Открыть магазин",
            web_app=WebAppInfo(url=WEBAPP_URL),
        )
    ]])


@router.message(Command("start"))
async def cmd_start(message: Message):
    # сохраняем юзера по id — чтобы фронт потом правильно определял продавца
    u = message.from_user
    if u:
        full = " ".join(x for x in [u.first_name, u.last_name] if x)
        db.upsert_user(
            tg_id=str(u.id),
            username=(u.username or ""),
            full_name=full or "",
        )
    await message.answer(
        "Привет! Это магазин mont1g3m's shop 💜\n\n"
        "Жми кнопку ниже, чтобы открыть каталог прямо здесь.",
        reply_markup=open_app_kb(),
    )


@router.message(Command("catalog"))
async def cmd_catalog(message: Message):
    items = db.list_items()
    if not items:
        await message.answer("Каталог пуст.")
        return
    text = "Каталог:\n\n"
    for it in items:
        game = "MM2" if it["game"] == "mm2" else ("Adopt Me" if it["game"] == "adopt" else "Аккаунты")
        text += f"· {it['name']} — {it['price']} ₽ ({game}) `{it['id']}`\n"
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("item"))
async def cmd_item(message: Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Использование: /item ID")
        return
    try:
        item_id = int(args[1])
    except ValueError:
        await message.answer("ID должен быть числом.")
        return
    item = db.get_item(item_id)
    if not item:
        await message.answer("Товар не найден.")
        return
    game = "MM2" if item["game"] == "mm2" else ("Adopt Me" if item["game"] == "adopt" else "Аккаунты")
    text = (
        f"<b>{item['name']}</b>\n"
        f"Цена: {item['price']} ₽\n"
        f"Игра: {game}\n"
        f"Продавец: {item['seller']}\n"
        f"┄┄┄┄┄┄┄┄┄\n"
        f"{item['desc']}"
    )
    img_path = item["img"]
    if img_path and os.path.isfile(os.path.join(BASE_DIR, img_path)):
        from aiogram.types import FSInputFile
        await message.answer_photo(FSInputFile(os.path.join(BASE_DIR, img_path)), caption=text, parse_mode="HTML")
    else:
        await message.answer(text, parse_mode="HTML")


@router.message(Command("sell"))
async def cmd_sell(message: Message):
    await message.answer(
        "Как продать:\n\n"
        "1. Открой мини-апп и перейди в раздел «Продать»\n"
        "2. Заполни название, цену, добавь фото и выбери игру\n"
        "3. Нажми «Опубликовать» — лот появится в каталоге"
    )


async def attach_webhook(app, webhook_base: str, path: str = "/webhook"):
    """Встраивает webhook бота в существующий aiohttp-сервер.

    webhook_base — внешний домен (уже идёт проксирование апдейтов на app),
    path — путь, на котором бот будет принимать апдейты.
    """
    if not BOT_TOKEN:
        logger.warning("BOT_TOKEN не задан — бот не запущен.")
        return None, None
    from aiogram.webhook.aiohttp_server import setup_application
    from aiogram import Bot as _Bot, Dispatcher as _DP

    bot = _Bot(token=BOT_TOKEN)
    dp = _DP()
    dp.include_router(router)

    full = webhook_base.rstrip("/") + path
    setup_application(app, dp, bot=bot)
    # регистрируем webhook у Telegram (убираем старое)
    await bot.delete_webhook()
    await bot.set_webhook(full)
    logger.info("Бот подключён к webhook: %s", full)
    return bot, dp
