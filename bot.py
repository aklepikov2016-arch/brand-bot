import logging, json, os, datetime as dt
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters, ConversationHandler, CallbackQueryHandler
)

logging.basicConfig(format="%(asctime)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = "8601013378:AAHhpB5b5BfRcXoo2sOCWS9t8ZfJBxHPY6I"
TRAINER_ID = 8172910932  # Впиши сюда свой ID после команды /myid
DATA_FILE = "events_data.json"

ADD_EVENT_TITLE, ADD_EVENT_DATE, ADD_EVENT_TIME, ADD_EVENT_DESC, PICK_PARTICIPANT, PICK_EVENT = range(6)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"events": [], "participants": [], "assignments": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_trainer(uid):
    return TRAINER_ID is not None and uid == TRAINER_ID

def trainer_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Добавить мероприятие"), KeyboardButton("Все мероприятия")],
        [KeyboardButton("Участники"), KeyboardButton("Назначить мероприятие")],
        [KeyboardButton("Удалить мероприятие")]
    ], resize_keyboard=True)

def participant_kb():
    return ReplyKeyboardMarkup([
        [KeyboardButton("Мои мероприятия"), KeyboardButton("Ближайшее")],
        [KeyboardButton("О программе")]
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    name = update.effective_user.first_name
    if not is_trainer(uid):
        data = load_data()
        if uid not in [p["id"] for p in data["participants"]]:
            data["participants"].append({"id": uid, "name": name, "username": update.effective_user.username or ""})
            save_data(data)
    if is_trainer(uid):
        await update.message.reply_text(f"Привет, тренер {name}!\n\nДобавляй мероприятия и назначай участникам.", reply_markup=trainer_kb())
    else:
        await update.message.reply_text(f"Привет, {name}!\n\nЯ твой личный ассистент программы Трансформация бренда.\nБуду напоминать о всех встречах заранее.", reply_markup=participant_kb())

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    await update.message.reply_text(f"Твой Telegram ID: {uid}\n\nСкопируй и вставь в bot.py в строку TRAINER_ID = {uid}")

# --- Добавить мероприятие ---
async def add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update.effective_user.id):
        await update.message.reply_text("Только для тренера.")
        return ConversationHandler.END
    await update.message.reply_text("Введи название мероприятия:\nНапример: Встреча с дизайнером")
    return ADD_EVENT_TITLE

async def add_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["title"] = update.message.text
    await update.message.reply_text("Введи дату (ДД.ММ.ГГГГ):\nНапример: 15.07.2025")
    return ADD_EVENT_DATE

async def add_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dt.datetime.strptime(update.message.text.strip(), "%d.%m.%Y")
        context.user_data["date"] = update.message.text.strip()
        await update.message.reply_text("Введи время (ЧЧ:ММ):\nНапример: 10:00")
        return ADD_EVENT_TIME
    except ValueError:
        await update.message.reply_text("Неверный формат. Введи как ДД.ММ.ГГГГ")
        return ADD_EVENT_DATE

async def add_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dt.datetime.strptime(update.message.text.strip(), "%H:%M")
        context.user_data["time"] = update.message.text.strip()
        await update.message.reply_text("Краткое описание или задание (необязательно).\nИли напиши: пропустить")
        return ADD_EVENT_DESC
    except ValueError:
        await update.message.reply_text("Неверный формат. Введи как ЧЧ:ММ")
        return ADD_EVENT_TIME

async def add_desc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    desc = "" if update.message.text.lower() in ["пропустить", "-", "нет"] else update.message.text
    data = load_data()
    eid = max([e["id"] for e in data["events"]], default=0) + 1
    event = {"id": eid, "title": context.user_data["title"], "date": context.user_data["date"], "time": context.user_data["time"], "desc": desc}
    data["events"].append(event)
    save_data(data)
    await update.message.reply_text(
        f"Мероприятие добавлено!\n\n{event['title']}\n{event['date']} в {event['time']}\n{'Задание: ' + desc if desc else ''}\n\nНазначь его участнику через кнопку Назначить мероприятие",
        reply_markup=trainer_kb()
    )
    return ConversationHandler.END

# --- Список мероприятий ---
async def list_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data["events"]:
        await update.message.reply_text("Мероприятий пока нет.", reply_markup=trainer_kb())
        return
    text = "Все мероприятия:\n\n"
    for e in sorted(data["events"], key=lambda x: dt.datetime.strptime(f"{x['date']} {x['time']}", "%d.%m.%Y %H:%M")):
        n = sum(1 for a in data["assignments"] if a["event_id"] == e["id"])
        text += f"{e['id']}. {e['title']}\n   {e['date']} {e['time']} - участников: {n}\n\n"
    await update.message.reply_text(text, reply_markup=trainer_kb())

# --- Участники ---
async def list_participants(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    if not data["participants"]:
        await update.message.reply_text("Участников пока нет.\nПусть напишут боту /start", reply_markup=trainer_kb())
        return
    text = "Участники программы:\n\n"
    for p in data["participants"]:
        uname = f"@{p['username']}" if p.get("username") else f"ID: {p['id']}"
        n = sum(1 for a in data["assignments"] if a["participant_id"] == p["id"])
        text += f"{p['name']} ({uname}) - мероприятий: {n}\n"
    await update.message.reply_text(text, reply_markup=trainer_kb())

# --- Назначить мероприятие ---
async def assign_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update.effective_user.id):
        return ConversationHandler.END
    data = load_data()
    if not data["events"]:
        await update.message.reply_text("Сначала добавь мероприятия!", reply_markup=trainer_kb())
        return ConversationHandler.END
    if not data["participants"]:
        await update.message.reply_text("Участников нет. Пусть напишут /start", reply_markup=trainer_kb())
        return ConversationHandler.END
    buttons = [[InlineKeyboardButton(f"{p['name']}", callback_data=f"ap_{p['id']}")] for p in data["participants"]]
    await update.message.reply_text("Выбери участника:", reply_markup=InlineKeyboardMarkup(buttons))
    return PICK_PARTICIPANT

async def assign_participant(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = int(query.data.replace("ap_", ""))
    context.user_data["assign_pid"] = pid
    data = load_data()
    p = next((x for x in data["participants"] if x["id"] == pid), None)
    context.user_data["assign_pname"] = p["name"] if p else "Участник"
    buttons = [[InlineKeyboardButton(f"{e['title']} - {e['date']} {e['time']}", callback_data=f"ae_{e['id']}")] for e in sorted(data["events"], key=lambda x: dt.datetime.strptime(f"{x['date']} {x['time']}", "%d.%m.%Y %H:%M"))]
    await query.edit_message_text(f"Выбери мероприятие для {context.user_data['assign_pname']}:", reply_markup=InlineKeyboardMarkup(buttons))
    return PICK_EVENT

async def assign_event(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    eid = int(query.data.replace("ae_", ""))
    data = load_data()
    event = next((e for e in data["events"] if e["id"] == eid), None)
    pid = context.user_data["assign_pid"]
    pname = context.user_data["assign_pname"]
    if any(a["event_id"] == eid and a["participant_id"] == pid for a in data["assignments"]):
        await query.edit_message_text(f"Это мероприятие уже назначено {pname}.")
        return ConversationHandler.END
    data["assignments"].append({"event_id": eid, "participant_id": pid})
    save_data(data)
    try:
        await context.bot.send_message(chat_id=pid, text=f"Тренер добавил тебе новое мероприятие!\n\n{event['title']}\n{event['date']} в {event['time']}\n{'Задание: ' + event['desc'] if event.get('desc') else ''}")
    except Exception as ex:
        logger.error(f"Не удалось уведомить {pid}: {ex}")
    await query.edit_message_text(f"Назначено!\n\n{event['title']} -> {pname}\n{event['date']} в {event['time']}")
    return ConversationHandler.END

# --- Удалить ---
async def delete_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_trainer(update.effective_user.id):
        return
    data = load_data()
    if not data["events"]:
        await update.message.reply_text("Мероприятий нет.", reply_markup=trainer_kb())
        return
    buttons = [[InlineKeyboardButton(f"Удалить: {e['title']} - {e['date']}", callback_data=f"de_{e['id']}")] for e in data["events"]]
    await update.message.reply_text("Выбери что удалить:", reply_markup=InlineKeyboardMarkup(buttons))

async def delete_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    eid = int(query.data.replace("de_", ""))
    data = load_data()
    event = next((e for e in data["events"] if e["id"] == eid), None)
    data["events"] = [e for e in data["events"] if e["id"] != eid]
    data["assignments"] = [a for a in data["assignments"] if a["event_id"] != eid]
    save_data(data)
    await query.edit_message_text(f"Мероприятие удалено: {event['title']}")

# --- Участник: мои мероприятия ---
async def my_events(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = load_data()
    my_ids = [a["event_id"] for a in data["assignments"] if a["participant_id"] == uid]
    events = [e for e in data["events"] if e["id"] in my_ids]
    if not events:
        await update.message.reply_text("Тренер ещё не добавил тебе мероприятий.\nСкоро появятся!", reply_markup=participant_kb())
        return
    now = dt.datetime.now()
    upcoming, past = [], []
    for e in events:
        d = dt.datetime.strptime(f"{e['date']} {e['time']}", "%d.%m.%Y %H:%M")
        (upcoming if d >= now else past).append((d, e))
    upcoming.sort(key=lambda x: x[0])
    text = "Твои мероприятия:\n\n"
    if upcoming:
        text += "Предстоящие:\n"
        for d, e in upcoming:
            days = (d - now).days
            mark = "(сегодня!)" if days == 0 else f"(через {days} дн.)"
            text += f"- {e['title']}\n  {e['date']} {e['time']} {mark}\n"
            if e.get("desc"):
                text += f"  Задание: {e['desc']}\n"
            text += "\n"
    if past:
        text += "Прошедшие:\n"
        for d, e in past[:3]:
            text += f"- {e['title']} - {e['date']}\n"
    await update.message.reply_text(text, reply_markup=participant_kb())

async def nearest(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = load_data()
    my_ids = [a["event_id"] for a in data["assignments"] if a["participant_id"] == uid]
    now = dt.datetime.now()
    upcoming = sorted([(dt.datetime.strptime(f"{e['date']} {e['time']}", "%d.%m.%Y %H:%M"), e) for e in data["events"] if e["id"] in my_ids and dt.datetime.strptime(f"{e['date']} {e['time']}", "%d.%m.%Y %H:%M") >= now], key=lambda x: x[0])
    if not upcoming:
        await update.message.reply_text("Ближайших мероприятий нет!", reply_markup=participant_kb())
        return
    d, e = upcoming[0]
    days = (d - now).days
    when = "сегодня!" if days == 0 else ("завтра" if days == 1 else f"через {days} дней")
    await update.message.reply_text(f"Ближайшее мероприятие:\n\n{e['title']}\n{e['date']} в {e['time']} - {when}\n{'Задание: ' + e['desc'] if e.get('desc') else ''}", reply_markup=participant_kb())

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Трансформация бренда\n\nПрограмма на 1.5 месяца:\n\n"
        "4 встречи с дизайнером\n"
        "3 сессии с психологом\n"
        "33 встречи с капитаном\n"
        "Фотосессия в студии\n"
        "Запись подкаста\n\n"
        "Я напомню тебе о каждом шаге!",
        reply_markup=participant_kb()
    )

# --- Напоминания ---
async def daily_reminders(context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    now = dt.datetime.now()
    for p in data["participants"]:
        pid = p["id"]
        my_ids = [a["event_id"] for a in data["assignments"] if a["participant_id"] == pid]
        reminders = []
        for e in [x for x in data["events"] if x["id"] in my_ids]:
            d = dt.datetime.strptime(f"{e['date']} {e['time']}", "%d.%m.%Y %H:%M")
            days = (d - now).days
            if days == 0: reminders.append(f"СЕГОДНЯ - {e['title']} в {e['time']}")
            elif days == 1: reminders.append(f"Завтра - {e['title']} в {e['time']}")
            elif days == 3: reminders.append(f"Через 3 дня - {e['title']} ({e['date']})")
            elif days == 7: reminders.append(f"Через неделю - {e['title']} ({e['date']})")
        if reminders:
            try:
                await context.bot.send_message(chat_id=pid, text="Доброе утро!\n\n" + "\n".join(reminders))
            except Exception as ex:
                logger.error(f"Ошибка {pid}: {ex}")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = trainer_kb() if is_trainer(update.effective_user.id) else participant_kb()
    await update.message.reply_text("Отменено.", reply_markup=kb)
    return ConversationHandler.END

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    uid = update.effective_user.id
    if is_trainer(uid):
        if text == "Все мероприятия": await list_events(update, context)
        elif text == "Участники": await list_participants(update, context)
        elif text == "Удалить мероприятие": await delete_start(update, context)
        else: await update.message.reply_text("Используй кнопки меню.", reply_markup=trainer_kb())
    else:
        if text == "Мои мероприятия": await my_events(update, context)
        elif text == "Ближайшее": await nearest(update, context)
        elif text == "О программе": await about(update, context)
        else: await update.message.reply_text("Используй кнопки меню.", reply_markup=participant_kb())

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    add_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Добавить мероприятие$"), add_start)],
        states={
            ADD_EVENT_TITLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_title)],
            ADD_EVENT_DATE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_date)],
            ADD_EVENT_TIME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_time)],
            ADD_EVENT_DESC:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_desc)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    assign_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^Назначить мероприятие$"), assign_start)],
        states={
            PICK_PARTICIPANT: [CallbackQueryHandler(assign_participant, pattern="^ap_")],
            PICK_EVENT:       [CallbackQueryHandler(assign_event, pattern="^ae_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(add_conv)
    app.add_handler(assign_conv)
    app.add_handler(CallbackQueryHandler(delete_do, pattern="^de_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.job_queue.run_daily(daily_reminders, time=dt.time(hour=9, minute=0))

    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
