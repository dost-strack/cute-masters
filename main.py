import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone

import aiosqlite
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DATABASE_PATH", "data/giveaways.sqlite3")
logging.basicConfig(level=logging.INFO)
dp = Dispatcher()


class CreateGiveaway(StatesGroup):
    title = State()
    winners = State()
    duration = State()


async def db():
    os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    return conn


async def init_db():
    async with await db() as conn:
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS giveaways (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            owner_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            winners_count INTEGER NOT NULL,
            ends_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            message_chat_id INTEGER,
            message_id INTEGER
        )""")
        await conn.execute("""
        CREATE TABLE IF NOT EXISTS participants (
            giveaway_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            username TEXT,
            full_name TEXT,
            joined_at TEXT NOT NULL,
            PRIMARY KEY (giveaway_id, user_id)
        )""")
        await conn.commit()


def join_keyboard(gid: int):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎉 Участвовать", callback_data=f"join:{gid}")],
        [InlineKeyboardButton(text="👥 Участники", callback_data=f"count:{gid}")]
    ])


async def publish_giveaway(bot: Bot, gid: int):
    async with await db() as conn:
        cur = await conn.execute("SELECT * FROM giveaways WHERE id=?", (gid,))
        g = await cur.fetchone()
        cur = await conn.execute("SELECT COUNT(*) AS n FROM participants WHERE giveaway_id=?", (gid,))
        count = (await cur.fetchone())["n"]
    if not g:
        return
    text = (
        f"🎁 <b>РОЗЫГРЫШ</b>\n\n{g['title']}\n\n"
        f"🏆 Победителей: <b>{g['winners_count']}</b>\n"
        f"👥 Участников: <b>{count}</b>\n"
        f"⏳ Завершение: <b>{g['ends_at'][:16].replace('T', ' ')}</b> UTC\n\n"
        "Нажми кнопку ниже, чтобы принять участие!"
    )
    if g["message_chat_id"] and g["message_id"]:
        try:
            await bot.edit_message_text(text, g["message_chat_id"], g["message_id"], reply_markup=join_keyboard(gid))
        except Exception:
            pass


@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        "Привет! Я бот для проведения розыгрышей 🎉\n\n"
        "Команды:\n/create — создать розыгрыш\n/my — мои розыгрыши\n/help — помощь\n\n"
        "Создай конкурс за несколько шагов."
    )


@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "🎁 <b>Как провести розыгрыш</b>\n"
        "1. Отправь /create и укажи приз или описание.\n"
        "2. Укажи количество победителей.\n"
        "3. Укажи длительность в часах.\n"
        "4. Опубликуй розыгрыш и поделись им.\n\n"
        "Участие доступно каждому пользователю Telegram. Победители выбираются случайно."
    )


@dp.message(Command("create"))
async def create(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(CreateGiveaway.title)
    await message.answer("Напиши название или описание приза (до 700 символов):")


@dp.message(CreateGiveaway.title)
async def get_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title or len(title) > 700:
        await message.answer("Нужно отправить текст от 1 до 700 символов. Попробуй ещё раз:")
        return
    await state.update_data(title=title)
    await state.set_state(CreateGiveaway.winners)
    await message.answer("Сколько будет победителей? Введи число от 1 до 100:")


@dp.message(CreateGiveaway.winners)
async def get_winners(message: Message, state: FSMContext):
    try:
        n = int(message.text or "")
        if not 1 <= n <= 100:
            raise ValueError
    except ValueError:
        await message.answer("Введи целое число от 1 до 100:")
        return
    await state.update_data(winners=n)
    await state.set_state(CreateGiveaway.duration)
    await message.answer("Через сколько часов завершить розыгрыш? Введи число от 1 до 720:")


@dp.message(CreateGiveaway.duration)
async def get_duration(message: Message, state: FSMContext, bot: Bot):
    try:
        hours = int(message.text or "")
        if not 1 <= hours <= 720:
            raise ValueError
    except ValueError:
        await message.answer("Введи целое число от 1 до 720 часов:")
        return
    data = await state.get_data()
    end = datetime.now(timezone.utc) + timedelta(hours=hours)
    async with await db() as conn:
        cur = await conn.execute(
            "INSERT INTO giveaways(owner_id,title,winners_count,ends_at) VALUES(?,?,?,?)",
            (message.from_user.id, data["title"], data["winners"], end.isoformat())
        )
        gid = cur.lastrowid
        await conn.commit()
    await state.clear()
    sent = await message.answer(
        f"🎁 <b>РОЗЫГРЫШ</b>\n\n{data['title']}\n\n"
        f"🏆 Победителей: <b>{data['winners']}</b>\n"
        f"⏳ Завершение: <b>{end.strftime('%Y-%m-%d %H:%M')} UTC</b>\n\n"
        "Нажми кнопку ниже, чтобы принять участие!",
        reply_markup=join_keyboard(gid)
    )
    async with await db() as conn:
        await conn.execute("UPDATE giveaways SET message_chat_id=?, message_id=? WHERE id=?",
                           (sent.chat.id, sent.message_id, gid))
        await conn.commit()
    await message.answer("Готово! Перешли сообщение с розыгрышем в свой канал или чат.")


@dp.callback_query(F.data.startswith("join:"))
async def join(call: CallbackQuery, bot: Bot):
    gid = int(call.data.split(":")[1])
    user = call.from_user
    async with await db() as conn:
        cur = await conn.execute("SELECT * FROM giveaways WHERE id=?", (gid,))
        g = await cur.fetchone()
        if not g or g["status"] != "active" or datetime.fromisoformat(g["ends_at"]) <= datetime.now(timezone.utc):
            await call.answer("Этот розыгрыш уже завершён.", show_alert=True)
            return
        try:
            await conn.execute(
                "INSERT INTO participants(giveaway_id,user_id,username,full_name,joined_at) VALUES(?,?,?,?,?)",
                (gid, user.id, user.username, user.full_name, datetime.now(timezone.utc).isoformat())
            )
            await conn.commit()
            await call.answer("Ты участвуешь! Удачи 🍀")
        except aiosqlite.IntegrityError:
            await call.answer("Ты уже участвуешь в этом розыгрыше.", show_alert=True)
    await publish_giveaway(bot, gid)


@dp.callback_query(F.data.startswith("count:"))
async def count(call: CallbackQuery):
    gid = int(call.data.split(":")[1])
    async with await db() as conn:
        cur = await conn.execute("SELECT COUNT(*) AS n FROM participants WHERE giveaway_id=?", (gid,))
        n = (await cur.fetchone())["n"]
    await call.answer(f"Участников: {n}", show_alert=True)


@dp.message(Command("my"))
async def my_giveaways(message: Message):
    async with await db() as conn:
        cur = await conn.execute(
            "SELECT id,title,ends_at,status FROM giveaways WHERE owner_id=? ORDER BY id DESC LIMIT 20",
            (message.from_user.id,)
        )
        rows = await cur.fetchall()
    if not rows:
        await message.answer("У тебя пока нет розыгрышей. Создай первый: /create")
        return
    lines = ["<b>Твои розыгрыши:</b>"]
    for g in rows:
        lines.append(f"#{g['id']} — {g['title'][:60]} | {g['status']} | до {g['ends_at'][:16]}")
    await message.answer("\n".join(lines))


async def finish_due_giveaways(bot: Bot):
    now = datetime.now(timezone.utc)
    async with await db() as conn:
        cur = await conn.execute("SELECT * FROM giveaways WHERE status='active' AND ends_at<=?", (now.isoformat(),))
        due = await cur.fetchall()
    for g in due:
        async with await db() as conn:
            cur = await conn.execute(
                "SELECT user_id,username,full_name FROM participants WHERE giveaway_id=? ORDER BY RANDOM() LIMIT ?",
                (g["id"], g["winners_count"])
            )
            winners = await cur.fetchall()
            await conn.execute("UPDATE giveaways SET status='finished' WHERE id=?", (g["id"],))
            await conn.commit()
        if winners:
            names = [f"• {('@' + w['username']) if w['username'] else w['full_name']} (ID: {w['user_id']})" for w in winners]
            result = "🏆 <b>Розыгрыш завершён!</b>\n\n" + g["title"] + "\n\n<b>Победители:</b>\n" + "\n".join(names)
        else:
            result = "Розыгрыш завершён, но участников не было."
        try:
            await bot.send_message(g["owner_id"], result)
        except Exception:
            logging.warning("Could not notify owner %s", g["owner_id"])
        if g["message_chat_id"] and g["message_id"]:
            try:
                await bot.send_message(g["message_chat_id"], result, reply_to_message_id=g["message_id"])
            except Exception:
                pass


async def scheduler(bot: Bot):
    while True:
        try:
            await finish_due_giveaways(bot)
        except Exception:
            logging.exception("Scheduler error")
        await asyncio.sleep(15)


async def main():
    if not TOKEN or TOKEN == "123456:replace_me":
        raise RuntimeError("Set BOT_TOKEN in .env. Get it from @BotFather.")
    await init_db()
    bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    asyncio.create_task(scheduler(bot))
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
