# mont1g3m's shop — Telegram-миниапп (бэк)

Магазин предметов MM2 / Adopt Me. Фронт — `index.html` (отдаётся сервером), бэк — Python:
**aiohttp** (веб + API) и **aiogram** (бот). Данные в **SQLite**.

## Структура

- `db.py` — слой базы данных (товары, избранное, авто-seed каталога)
- `main.py` — aiohttp-сервер: отдаёт `index.html`, картинки и API
- `bot.py` — бот на aiogram (каталог, карточка товара)
- `index.html` — фронт, тянет данные с `/api/*`
- `requirements.txt`, `.env.example`

## Установка

```bash
pip install -r requirements.txt
```

## Токен бота

1. Создай бота у **@BotFather** и получи токен.
2. Впиши его в переменную окружения `BOT_TOKEN` (или создай `.env` рядом):

```bash
# Windows (PowerShell)
$env:BOT_TOKEN="123456789:AAE..."
# Windows (cmd)
set BOT_TOKEN=123456789:AAE...
```

## Запуск

```bash
python main.py
```

- Сервер стартует на `http://0.0.0.0:8080`
- Бот запускается вместе с ним (если задан `BOT_TOKEN`)

База `shop.db` создастся автоматически пустой. Каталог наполняется реальными объявлениями через раздел «Продать» или бот.

## API

| Метод | Путь | Описание |
|-------|------|----------|
| GET | `/api/items` | список товаров |
| GET | `/api/items/{id}` | товар по id |
| GET | `/api/favs` | избранное юзера (заголовок `X-Tg-User`) |
| POST | `/api/favs/toggle` | `{item_id}` — добавить/убрать из избранного |
| POST | `/api/sell` | создать товар: `{name, price, game, seller, desc, photos[]}` |

Юзер для избранного передаётся в заголовке `X-Tg-User` (id из Telegram WebApp). Вне Telegram — `guest`.

## Команды бота

- `/start` — приветствие
- `/catalog` — список товаров
- `/item <id>` — карточка товара с фото
- `/sell` — как продать

## Мини-апп в Telegram

1. Пропиши Web App-кнопку у бота (через @BotFather) со ссылкой на `https://твой-домен`.
2. Для локальной разработки используй `ngrok http 8080` и подставь полученный https-адрес.