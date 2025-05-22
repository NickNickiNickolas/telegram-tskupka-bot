import asyncio
import logging
from datetime import datetime
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Этапы
AGE_CONFIRM, CATEGORY, CONDITION, CITY, PHONE, PHOTO, SAVE = range(7)

# Админ ID
ADMIN_CHAT_ID = 7902485807  # Замените на ваш ID

# Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open_by_key("1-AzI2bdf_eDc0Lz42FiiVv48wT4IbGwISZHbzIoRhj8").sheet1

# Кнопки
category_buttons = [
    [InlineKeyboardButton("📱 Телефоны", callback_data="Телефоны")],
    [InlineKeyboardButton("💻 Компьютерная техника", callback_data="Компьютерная техника")],
    [InlineKeyboardButton("🛠 Строительные инструменты", callback_data="Строительные инструменты")],
    [InlineKeyboardButton("🎮 Игровые приставки", callback_data="Игровые приставки")],
    [InlineKeyboardButton("🏺 Антиквариат", callback_data="Антиквариат")],
    [InlineKeyboardButton("🔁 Другое", callback_data="Другое")],
]
condition_buttons = [
    [InlineKeyboardButton("Как новое", callback_data="Как новое")],
    [InlineKeyboardButton("С износом", callback_data="С износом")],
    [InlineKeyboardButton("Повреждено", callback_data="Повреждено")],
]

# Старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Мне есть 18 лет", callback_data="yes")],
        [InlineKeyboardButton("Нет 18 лет", callback_data="no")],
    ])

    if update.message:
        await update.message.reply_text("Подтвердите, что вам есть 18:", reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.message.reply_text("Подтвердите, что вам есть 18:", reply_markup=keyboard)

    return AGE_CONFIRM


# Подтверждение возраста
async def age_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "no":
        await query.edit_message_text(
            "Извините, работать можем только с 18+.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Начать заново", callback_data="add_more")]
            ])
        )
        return ConversationHandler.END

    await query.message.reply_text("📦 Что вы хотите продать?", reply_markup=InlineKeyboardMarkup(category_buttons))
    return CATEGORY


async def get_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "Другое":
        await query.message.reply_text("Пожалуйста, опишите, что вы хотите продать:")
        return CATEGORY
    else:
        context.user_data["device"] = query.data
        await query.message.reply_text("👇 Укажите состояние техники", reply_markup=InlineKeyboardMarkup(condition_buttons))
        return CONDITION


async def save_custom_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["device"] = update.message.text
    await update.message.reply_text("👇 Укажите состояние техники", reply_markup=InlineKeyboardMarkup(condition_buttons))
    return CONDITION


async def get_condition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["condition"] = query.data
    await query.message.reply_text("🌆 Введите ваш город:")
    return CITY


async def get_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["city"] = update.message.text
    await update.message.reply_text("📞 Введите номер телефона:")
    return PHONE


async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone_input = update.message.text.strip()

    if not phone_input.isdigit():
        await update.message.reply_text("❗ Пожалуйста, введите номер телефона только цифрами.")
        return PHONE

    context.user_data["phone"] = phone_input

    await update.message.reply_text(
        "📷 Прикрепите фотографию устройства (если есть).",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Нет фото", callback_data="skip_photo")]
        ])
    )
    return PHOTO


async def get_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        photo_file = await update.message.photo[-1].get_file()
        context.user_data["photo"] = photo_file.file_id
    else:
        context.user_data["photo"] = None

    return await save_data(update.message, context)


async def skip_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["photo"] = None
    return await save_data(update.callback_query.message, context)


async def save_data(message_source, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    photo_id = context.user_data.get("photo")
    photo_info = "https://t.me/c/{}/{}".format(ADMIN_CHAT_ID, message_source.message_id) if photo_id else "Не предоставлено"

    row_data = [
        now,
        context.user_data.get("device"),
        context.user_data.get("condition"),
        context.user_data.get("city"),
        context.user_data.get("phone"),
        "Новая заявка",
        photo_info,
    ]
    sheet.append_row(row_data)
    row_number = len(sheet.get_all_values())

    text = (
        f"📥 Новая заявка:\n"
        f"📅 Дата: {now}\n"
        f"📦 Устройство: {context.user_data.get('device')}\n"
        f"🔧 Состояние: {context.user_data.get('condition')}\n"
        f"🏙 Город: {context.user_data.get('city')}\n"
        f"📞 Телефон: {context.user_data.get('phone')}\n"
        f"📌 Статус: Новая заявка"
    )

    status_buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Выкуп завершён", callback_data=f"status_done_{row_number}"),
            InlineKeyboardButton("❌ Не актуально", callback_data=f"status_cancel_{row_number}"),
        ]
    ])

    if photo_id:
        await context.bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=photo_id,
            caption=text,
            reply_markup=status_buttons,
        )
    else:
        await context.bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=text,
            reply_markup=status_buttons,
        )

    await message_source.reply_text(
        "🎉 Спасибо! Ваша заявка отправлена.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Отправить ещё", callback_data="add_more")]
        ])
    )
    return ConversationHandler.END


async def update_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if str(query.message.chat_id) != str(ADMIN_CHAT_ID):
        await query.message.reply_text("⛔ Только администратор может менять статус.")
        return

    data = query.data.split("_")
    status = "Выкуп завершен" if data[1] == "done" else "Не актуально"
    row = int(data[2])
    sheet.update_cell(row, 6, status)
    await query.edit_message_reply_markup(reply_markup=None)
    await query.message.reply_text(f"✅ Статус обновлён: {status}")


async def add_more(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await start(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END


if __name__ == '__main__':
    import asyncio
    asyncio.run(application.run_polling())    
    application = ApplicationBuilder().token("8079851046:AAGnyFflGYanv1kMGylzYbgyqlOokSlAYSs").build()

    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("start", start),
            CallbackQueryHandler(add_more, pattern="^add_more$"),
        ],
        states={
            AGE_CONFIRM: [CallbackQueryHandler(age_confirm)],
            CATEGORY: [
                CallbackQueryHandler(get_device),
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_custom_device),
            ],
            CONDITION: [CallbackQueryHandler(get_condition)],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_city)],
            PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
            PHOTO: [
                MessageHandler(filters.PHOTO, get_photo),
                CallbackQueryHandler(skip_photo, pattern="^skip_photo$"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(update_status, pattern="^status_(done|cancel)_\\d+$"))
    if __name__ == "__main__":
    asyncio.run(application.run_polling())
