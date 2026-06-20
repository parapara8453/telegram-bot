import json
import os
from flask import Flask
from threading import Thread

from dotenv import load_dotenv

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from supabase import create_client


load_dotenv()

TOKEN = os.getenv("TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not TOKEN:
    raise ValueError("TOKEN が設定されていません")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL が設定されていません")

if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY が設定されていません")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

MEDIA_TYPE, CATEGORY1, CATEGORY2, TITLE, PRICE, MEDIA = range(6)


def load_categories():
    with open("categories.json", "r", encoding="utf-8") as f:
        return json.load(f)


CATEGORIES = load_categories()


def main_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📤 投稿")],
            [KeyboardButton("👀 一覧を見る")],
        ],
        resize_keyboard=True,
    )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "メニューを選択してください。",
        reply_markup=main_menu(),
    )


async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("🎥 動画")],
        [KeyboardButton("🖼 写真")],
    ]

    await update.message.reply_text(
        "投稿する種類を選択してください。",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )

    return MEDIA_TYPE


async def select_media_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🎥 動画":
        context.user_data["media_type"] = "video"
    else:
        context.user_data["media_type"] = "photo"

    keyboard = [[KeyboardButton(k)] for k in CATEGORIES.keys()]

    await update.message.reply_text(
        "場所を選択してください。",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )

    return CATEGORY1


async def select_category1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category1 = update.message.text

    if category1 not in CATEGORIES:
        await update.message.reply_text("一覧から選択してください。")
        return CATEGORY1

    context.user_data["category1"] = category1

    keyboard = [
        [KeyboardButton(v)]
        for v in CATEGORIES[category1]
    ]

    await update.message.reply_text(
        "地域を選択してください。",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
        ),
    )

    return CATEGORY2


async def select_category2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["category2"] = update.message.text

    await update.message.reply_text(
        "タイトルを入力してください。",
        reply_markup=ReplyKeyboardRemove(),
    )

    return TITLE


async def input_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()

    if not title:
        await update.message.reply_text("タイトルを入力してください。")
        return TITLE

    context.user_data["title"] = title

    await update.message.reply_text(
        "価格を入力してください。（2〜99）"
    )

    return PRICE


async def input_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int(update.message.text)

        if price < 2 or price > 99:
            raise ValueError

    except ValueError:
        await update.message.reply_text(
            "2〜99の数字を入力してください。"
        )
        return PRICE

    context.user_data["price"] = price

    if context.user_data["media_type"] == "video":
        text = "動画を送信してください。"
    else:
        text = "写真を送信してください。"

    await update.message.reply_text(text)

    return MEDIA


async def save_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        thumb_id = file_id
        media_type = "photo"

    elif update.message.video:
        file_id = update.message.video.file_id

        if update.message.video.thumbnail:
            thumb_id = update.message.video.thumbnail.file_id
        else:
            thumb_id = file_id

        media_type = "video"

    else:
        await update.message.reply_text(
            "写真または動画を送信してください。"
        )
        return MEDIA

    telegram_id = update.effective_user.id

    user_check = (
        supabase.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .execute()
    )

    if len(user_check.data) == 0:
        supabase.table("users").insert({
            "telegram_id": telegram_id
        }).execute()

    supabase.table("contents").insert({
        "owner_id": telegram_id,
        "media_type": media_type,
        "title": context.user_data["title"],
        "category_1": context.user_data["category1"],
        "category_2": context.user_data["category2"],
        "price": context.user_data["price"],
        "telegram_file_id": file_id,
        "thumbnail_file_id": thumb_id,
    }).execute()

    context.user_data.clear()

    await update.message.reply_text(
        "✅ 投稿が完了しました。",
        reply_markup=main_menu(),
    )

    return ConversationHandler.END


async def show_contents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = (
        supabase.table("contents")
        .select("*")
        .order("created_at", desc=True)
        .limit(10)
        .execute()
    )

    if len(result.data) == 0:
        await update.message.reply_text(
            "まだ投稿がありません。"
        )
        return

    for item in result.data:
        caption = (
            f"📌 {item['title']}\n"
            f"💰 {item['price']} コイン\n"
            f"📂 {item['category_1']} / {item['category_2']}"
        )

        if item["media_type"] == "video":
            await update.message.reply_video(
                video=item["telegram_file_id"],
                caption=caption,
            )
        else:
            await update.message.reply_photo(
                photo=item["telegram_file_id"],
                caption=caption,
            )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "キャンセルしました。",
        reply_markup=main_menu(),
    )

    return ConversationHandler.END

async def welcome_new_member(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    text = """
🎉 ようこそ！

まずは下のコマンドを送信してください。

▶️ /start

━━━━━━━━━━

📤 投稿する

👀 一覧を見る

━━━━━━━━━━

【投稿手順】

1️⃣ 投稿を選択

2️⃣ カテゴリを選択

3️⃣ タイトルを入力

4️⃣ 価格を入力

5️⃣ 画像または動画を送信

━━━━━━━━━━

🎁 動画を投稿するとポイントを獲得できます。

貯めたポイントを使って、
ほかの動画を購入しましょう！
"""

    await update.message.reply_text(text)

app_web = Flask(__name__)

@app_web.route("/")
def home():
    return "Bot is running!"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app_web.run(host="0.0.0.0", port=port)

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            MessageHandler(
                filters.Regex("^📤 投稿$"),
                upload_start,
            )
        ],
        states={
            MEDIA_TYPE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    select_media_type,
                )
            ],
            CATEGORY1: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    select_category1,
                )
            ],
            CATEGORY2: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    select_category2,
                )
            ],
            TITLE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    input_title,
                )
            ],
            PRICE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    input_price,
                )
            ],
            MEDIA: [
                MessageHandler(
                    filters.PHOTO | filters.VIDEO,
                    save_media,
                )
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(
    MessageHandler(
        filters.StatusUpdate.NEW_CHAT_MEMBERS,
        welcome_new_member
    )
)


    app.add_handler(
        MessageHandler(
            filters.Regex("^👀 一覧を見る$"),
            show_contents,
        )
    )

    print("Bot 起動中...")

    app.run_polling()


if __name__ == "__main__":
    Thread(target=run_web).start()
    main()
