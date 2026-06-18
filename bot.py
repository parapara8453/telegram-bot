import os
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

import os
TOKEN = os.getenv("TOKEN")

CATEGORY1 = ["asia", "white", "black", "japan", "half"]
CATEGORY2 = ["bikini", "kids", "tankini", "underwear", "separate"]

user_state = {}

# スタート
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["投稿する", "閲覧する"]]
    await update.message.reply_text(
        "何をしますか？",
        reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    )

# テキスト処理
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # モード選択
    if text == "投稿する":
        user_state[user_id] = {"mode": "upload"}
        keyboard = [[c] for c in CATEGORY1]
        await update.message.reply_text("カテゴリ1を選んでください", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))

    elif text == "閲覧する":
        user_state[user_id] = {"mode": "view"}
        keyboard = [[c] for c in CATEGORY1]
        await update.message.reply_text("カテゴリ1を選んでください", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))

    elif text in CATEGORY1:
        if user_id not in user_state:
            await update.message.reply_text("/start から始めてください")
            return

        user_state[user_id]["cat1"] = text
        keyboard = [[c] for c in CATEGORY2]
        await update.message.reply_text("カテゴリ2を選んでください", reply_markup=ReplyKeyboardMarkup(keyboard, one_time_keyboard=True))

    elif text in CATEGORY2:
        if user_id not in user_state:
            await update.message.reply_text("/start から始めてください")
            return

        user_state[user_id]["cat2"] = text
        mode = user_state[user_id]["mode"]
        cat1 = user_state[user_id]["cat1"]
        cat2 = text

        folder = f"images/{cat1}/{cat2}"

        if mode == "view":
            if not os.path.exists(folder):
                await update.message.reply_text("画像がありません")
                return

            files = os.listdir(folder)
            if not files:
                await update.message.reply_text("画像がありません")
                return

            for file in files:
                with open(os.path.join(folder, file), "rb") as f:
                    await update.message.reply_photo(f)

        elif mode == "upload":
            await update.message.reply_text("画像を送信してください")

    else:
        await update.message.reply_text("選択肢から選んでください")

# 画像保存
async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in user_state:
        await update.message.reply_text("/start から始めてください")
        return

    if user_state[user_id].get("mode") != "upload":
        await update.message.reply_text("投稿モードでのみアップロードできます")
        return

    if "cat1" not in user_state[user_id] or "cat2" not in user_state[user_id]:
        await update.message.reply_text("カテゴリを選んでください")
        return

    cat1 = user_state[user_id]["cat1"]
    cat2 = user_state[user_id]["cat2"]

    folder = f"images/{cat1}/{cat2}"
    os.makedirs(folder, exist_ok=True)

    photo = update.message.photo[-1]
    file = await photo.get_file()

    filepath = f"{folder}/{photo.file_id}.jpg"
    await file.download_to_drive(filepath)

    await update.message.reply_text("保存しました！")

# メイン
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
app.add_handler(MessageHandler(filters.PHOTO, handle_photo))

print("bot起動中...")
app.run_polling()
