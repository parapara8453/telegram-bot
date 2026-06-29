import os
import traceback
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta, timezone

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from keyboards.main import main_menu, admin_menu

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from database import supabase

from telegram.constants import ChatType

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from services.user import get_user

from config import (
    MEDIA_TYPE,
    CATEGORY1,
    CATEGORY2,
    TITLE,
    PRICE,
    MEDIA,
    THUMBNAIL,
    BROWSE,
    SEARCH_TITLE,
    ADD_CATEGORY,
    DELETE_CATEGORY,
    ADD_REGION,
    DELETE_REGION,
    SELECT_PARENT_CATEGORY,
    ADD_SUBCATEGORY,
    SELECT_DELETE_PARENT,
    DELETE_SUBCATEGORY,
    CHANGE_PRICE,
    ADMIN_USER_SEARCH,
    ADMIN_GIVE_COIN,
)

def get_categories():
    result = (
        supabase.table("categories")
        .select("*")
        .order("sort_order")
        .execute()
    )

    return result.data


def get_subcategories(category_name):
    return []


def category_admin_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📋 カテゴリ一覧")],
            [KeyboardButton("➕ カテゴリ追加")],
            [KeyboardButton("➖ カテゴリ削除")],
            [KeyboardButton("📍 地域管理")],
            [KeyboardButton("📁 サブカテゴリ管理")],
            [KeyboardButton("⬅️ 戻る")],
        ],
        resize_keyboard=True,
    )

def subcategory_admin_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("➕ サブカテゴリ追加")],
            [KeyboardButton("➖ サブカテゴリ削除")],
            [KeyboardButton("⬅️ 戻る")],
        ],
        resize_keyboard=True,
    )

def category_menu():
    rows = []

    for category in get_categories():
        rows.append([KeyboardButton(category["name"])])

    rows.append([KeyboardButton("キャンセル")])

    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
    )

# MOVED TO services/user.py
def get_user(telegram_id, username=None):
    result = (
        supabase.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .execute()
    )

    if result.data:
        return result.data[0]

    supabase.table("users").insert({
        "telegram_id": telegram_id,
        "username": username,
        "coin_balance": 0,
    }).execute()

    return (
        supabase.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .single()
        .execute()
    ).data

def calc_reward(media_type, file_size):
    if media_type == "document":
        return 10
    return 20 if file_size >= 100 * 1024 * 1024 else 15


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    if not await require_private_chat(update):
        return

    if context.args and context.args[0] == "welcome":
        await update.message.reply_text(
            "🎉 グループから来ていただきありがとうございます！\n\n"
            "まずは /start を押して利用を開始してください。"
        )

    context.user_data.clear()

    await update.message.reply_text(
        "メニューを選択してください。",
        reply_markup=main_menu(update.effective_user.id),
    )


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_private_chat(update):
        return
    user = get_user(
        update.effective_user.id,
        update.effective_user.username,
    )

    await update.message.reply_text(
        f"🪙 現在の残高: {user['coin_balance']} コイン"
    )




async def show_my_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_private_chat(update):
        return
    user_id = update.effective_user.id
    user = get_user(user_id, update.effective_user.username)

    posts = supabase.table("contents").select("*", count="exact").eq(
        "owner_id", user_id
    ).execute()

    purchases = supabase.table("purchases").select("*", count="exact").eq(
        "buyer_id", user_id
    ).execute()

    text = (
        "👤 マイページ\n\n"
        f"🪙 残高: {user.get('coin_balance', 0)} コイン\n"
        f"📤 投稿数: {posts.count or 0}\n"
        f"🛒 購入数: {purchases.count or 0}\n"
        f"💰 累計売上: {user.get('daily_sales', 0)} コイン"
    )

    await update.message.reply_text(text)

async def show_my_posts(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await require_private_chat(update):
        return

    user_id = update.effective_user.id

    result = (
        supabase.table("contents")
        .select("id,title,price")
        .eq("owner_id", user_id)
        .order("created_at", desc=True)
        .execute()
    )

    if not result.data:
        await update.message.reply_text(
            "投稿はありません。"
        )
        return

    buttons = []

    for item in result.data:
        buttons.append([
            InlineKeyboardButton(
                text=f"📄 {item['title']}（💰{item['price']}）",
                callback_data=f"detail:{item['id']}",
            )
        ])

    await update.message.reply_text(
        "📤 自分の投稿",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

async def show_purchase_history(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await require_private_chat(update):
        return
    user_id = update.effective_user.id

    result = (
        supabase.table("purchases")
        .select("content_id, created_at")
        .eq("buyer_id", user_id)
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )

    if not result.data:
        await update.message.reply_text(
            "購入履歴はありません。"
        )
        return

    buttons = []

    for p in result.data:
        item = (
            supabase.table("contents")
            .select("id, title")
            .eq("id", p["content_id"])
            .single()
            .execute()
        ).data

        buttons.append([
            InlineKeyboardButton(
                text=f"📄 {item['title']}",
                callback_data=f"detail:{item['id']}",
            )
        ])

    await update.message.reply_text(
        "🧾 購入履歴",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def upload_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_private_chat(update):
        return ConversationHandler.END

    keyboard = [
        [KeyboardButton("🎥 動画")],
        [KeyboardButton("📄 ファイル")],
    ]

    await update.message.reply_text(
        "投稿する種類を選択してください。",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return MEDIA_TYPE


async def select_media_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["media_type"] = (
        "video" if update.message.text == "🎥 動画" else "document"
    )

    keyboard = [
        [KeyboardButton(c["name"])]
        for c in get_categories()
    ]

    await update.message.reply_text(
        "カテゴリを選択してください。",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return CATEGORY1


async def select_category1(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category1 = update.message.text

    category_names = [
        c["name"] for c in get_categories()
    ]

    if category1 not in category_names:
        await update.message.reply_text(
            "一覧から選択してください。"
        )
        return CATEGORY1

    category = (
        supabase.table("categories")
        .select("id")
        .eq("name", category1)
        .single()
        .execute()
    )

    context.user_data["category_id"] = category.data["id"]

    regions = (
        supabase.table("regions")
        .select("*")
        .order("name")
        .execute()
    ).data

    keyboard = [
        [KeyboardButton(r["name"])]
        for r in regions
    ]

    await update.message.reply_text(
        "地域を選択してください。",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return CATEGORY2


async def select_category2(update: Update, context: ContextTypes.DEFAULT_TYPE):
    region_name = update.message.text

    region = (
        supabase.table("regions")
        .select("id")
        .eq("name", region_name)
        .single()
        .execute()
    )

    context.user_data["region_id"] = region.data["id"]

    await update.message.reply_text(
        "タイトルを入力してください。",
        reply_markup=ReplyKeyboardRemove(),
    )

    return TITLE


async def input_title(update: Update, context: ContextTypes.DEFAULT_TYPE):
    title = update.message.text.strip()

    if not title:
        await update.message.reply_text(
            "タイトルを入力してください。"
        )
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

    text = (
        "動画を送信してください。"
        if context.user_data["media_type"] == "video"
        else "ファイルを送信してください。"
    )

    await update.message.reply_text(text)

    return MEDIA


async def save_media(update: Update, context: ContextTypes.DEFAULT_TYPE):

    print("===== save_media =====")
    print(update.message)
    print("video =", update.message.video)
    print("document =", update.message.document)
    print("animation =", update.message.animation)
    print("effective_attachment =", update.message.effective_attachment)

    # 通常の動画
    if update.message.video:
        context.user_data["telegram_file_id"] = update.message.video.file_id
        context.user_data["file_size"] = update.message.video.file_size or 0
        context.user_data["media_type"] = "video"

        return await finish_upload(update, context)

    # ファイル
    if update.message.document:
        context.user_data["telegram_file_id"] = update.message.document.file_id
        context.user_data["file_size"] = (
            update.message.document.file_size or 0
        )

        # 動画を「ファイルとして送信」した場合
        if (
            update.message.document.mime_type
            and update.message.document.mime_type.startswith("video/")
        ):
            context.user_data["media_type"] = "video"
        else:
            context.user_data["media_type"] = "document"

        return await finish_upload(update, context)

    await update.message.reply_text(
        "動画またはファイルを送信してください。"
    )
    return MEDIA
        
async def finish_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    user = get_user(telegram_id, update.effective_user.username)

    media_type = context.user_data["media_type"]
    file_size = context.user_data.get("file_size", 0)

    reward = 0
    today = __import__("datetime").date.today()

    last = user.get("last_reward_date")
    updates = {}

    if str(last) != str(today):
        user["daily_photo_reward_count"] = 0
        user["daily_video_reward_count"] = 0
        updates["last_reward_date"] = str(today)

    if media_type == "document":
        count = user.get("daily_photo_reward_count", 0)
        if count < 5:
            reward = 10
            updates["daily_photo_reward_count"] = count + 1
    else:
        count = user.get("daily_video_reward_count", 0)
        if count < 5:
            reward = calc_reward(media_type, file_size)
            updates["daily_video_reward_count"] = count + 1

    updates["coin_balance"] = user.get("coin_balance", 0) + reward

    supabase.table("users").update(updates).eq(
        "telegram_id", telegram_id
    ).execute()

    supabase.table("contents").insert({
        "owner_id": telegram_id,
        "media_type": media_type,
        "title": context.user_data["title"],
        "category_id": context.user_data["category_id"],
        "region_id": context.user_data["region_id"],
        "price": context.user_data["price"],
        "telegram_file_id": context.user_data["telegram_file_id"],
    }).execute()

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "🤖 DMで見る",
                url="https://t.me/develpoing_bot"
            )
        ]
    ])

    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=(
            "🆕 新しい投稿\n\n"
            f"📄 {context.user_data['title']}\n"
            f"💰 {context.user_data['price']} コイン\n\n"
            "👇 詳細・購入はこちら"
        ),
        reply_markup=keyboard,
    )

    context.user_data.clear()

    msg = "✅ 投稿が完了しました。"
    if reward:
      msg += f"\n🎁 {reward}コイン獲得しました。"

    await update.message.reply_text(
        msg,
        reply_markup=main_menu(update.effective_user.id),
    )

    return ConversationHandler.END


async def show_media_list(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    media_type: str,
    title: str,
):
    result = (
        supabase.table("contents")
        .select("*")
        .eq("media_type", media_type)
        .order("created_at", desc=True)
        .limit(PAGE_SIZE)
        .execute()
    )

    if not result.data:
        await update.message.reply_text(f"{title}はありません。")
        return

    buttons = []

    for item in result.data:
        buttons.append([
            InlineKeyboardButton(
                text=f"{item['title']}（💰{item['price']}）",
                callback_data=f"detail:{item['id']}",
            )
        ])

    await update.message.reply_text(
        title,
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_videos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_private_chat(update):
        return

    await show_media_list(update, context, "video", "🎥 動画一覧")

async def show_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_private_chat(update):
        return

    await show_media_list(update, context, "document", "📄 ファイル一覧")

async def show_all_contents(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    page = context.user_data.get("page", 0)

    start = page * PAGE_SIZE
    end = start + PAGE_SIZE - 1

    result = (
        supabase.table("contents")
        .select("*")
        .order("created_at", desc=True)
        .range(start, end)
        .execute()
    )

    if not result.data:
        await update.message.reply_text(
            "投稿がありません。"
        )
        return

    buttons = []

    for item in result.data:
        buttons.append([
            InlineKeyboardButton(
                text=f"{item['title']}（💰{item['price']}）",
                callback_data=f"detail:{item['id']}",
            )
        ])

    nav_buttons = []

    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(
                "◀ 前へ",
                callback_data="page:prev",
            )
        )

    nav_buttons.append(
        InlineKeyboardButton(
            "次へ ▶",
            callback_data="page:next",
        )
    )

    buttons.append(nav_buttons)

    await update.message.reply_text(
        f"🌎 全ての動画（{page + 1}ページ目）",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

async def start_title_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await require_private_chat(update):
        return

    await update.message.reply_text(
        "🔍 タイトルを入力してください。"
    )

    return SEARCH_TITLE

async def search_title(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyword = update.message.text.strip()

    result = (
        supabase.table("contents")
        .select("*")
        .ilike("title", f"%{keyword}%")
        .order("created_at", desc=True)
        .limit(20)
        .execute()
    )

    if not result.data:
        await update.message.reply_text(
            "該当する動画が見つかりませんでした。",
            reply_markup=main_menu(update.effective_user.id),
        )
        return ConversationHandler.END

    buttons = []

    for item in result.data:
        buttons.append([
            InlineKeyboardButton(
                text=f"{item['title']}（💰{item['price']}）",
                callback_data=f"detail:{item['id']}",
            )
        ])

    await update.message.reply_text(
        f"🔍 検索結果：{keyword}",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

    return ConversationHandler.END


async def change_page(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()
    if not await require_private_callback(update):
        return

    page = context.user_data.get("page", 0)

    if query.data == "page:next":
        page += 1
    else:
        page = max(0, page - 1)

    context.user_data["page"] = page

    fake_update = type("obj", (), {})()
    fake_update.message = query.message

    await show_all_contents(
        fake_update,
        context,
    )

async def show_contents(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await require_private_chat(update):
        return
    context.user_data.clear()

    await update.message.reply_text(
        "カテゴリを選択してください。",
        reply_markup=category_menu(),
    )

    return BROWSE


async def browse_category(update: Update, context: ContextTypes.DEFAULT_TYPE):
    category = update.message.text

    if category == "キャンセル":
        await update.message.reply_text(
            "キャンセルしました。",
            reply_markup=main_menu(update.effective_user.id),
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"📂 {category}",
        reply_markup=ReplyKeyboardRemove(),
    )

    category_data = (
        supabase.table("categories")
        .select("id")
        .eq("name", category)
        .single()
        .execute()
    ).data

    result = (
        supabase.table("contents")
        .select("*")
        .eq("category_id", category_data["id"])
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )

    text = f"📂 {category}\n\n"
    
    if len(result.data) == 0:
        await update.message.reply_text(
            "このカテゴリには投稿がありません。",
            reply_markup=main_menu(update.effective_user.id),
        )
        return ConversationHandler.END

    buttons = []
    page_buttons = []

    for i, item in enumerate(result.data, start=1):
        text += (
            f"{i}. {item['title']}\n"
            f"💰{item['price']}コイン "
            f"🛒{item.get('purchase_count', 0)}回\n\n"
        )

        buttons.append(
            InlineKeyboardButton(
                str(i),
                callback_data=f"detail:{item['id']}",
            )
        )

    if len(result.data) == 5:
        page_buttons.append(
            InlineKeyboardButton(
                "▶ 次",
                callback_data=f"page:{category}:2"
            )
        )

    keyboard = [
        buttons,
    ]

    if page_buttons:
        keyboard.append(page_buttons)
    
    await update.message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )

    return ConversationHandler.END

async def browse_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not await require_private_callback(update):
        return

    _, category, page = query.data.split(":")
    page = int(page)

    category_data = (
        supabase.table("categories")
        .select("id")
        .eq("name", category)
        .single()
        .execute()
    ).data

    result = (
        supabase.table("contents")
        .select("*")
        .eq("category_id", category_data["id"])
        .order("created_at", desc=True)
        .range((page-1)*5, page*5-1)
        .execute()
    )

    text = f"📁 {category}\n\n"

    buttons = []

    for i, item in enumerate(result.data, start=1+(page-1)*5):
        text += (
            f"{i}. {item['title']}\n"
            f"💰{item['price']}コイン "
            f"🛒{item.get('purchase_count',0)}回\n\n"
        )

        buttons.append(
            InlineKeyboardButton(
                str(i),
                callback_data=f"detail:{item['id']}"
            )
        )

    keyboard = [buttons]

    nav = []

    if page > 1:
        nav.append(
            InlineKeyboardButton(
                "◀ 前",
                callback_data=f"page:{category}:{page-1}"
            )
        )

    if len(result.data) == 5:
        nav.append(
            InlineKeyboardButton(
                "▶ 次",
                callback_data=f"page:{category}:{page+1}"
            )
        )

    if nav:
        keyboard.append(nav)

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_detail_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()
    if not await require_private_callback(update):
        return
    await query.edit_message_reply_markup(reply_markup=None)

    content_id = int(query.data.split(":")[1])

    item = (
        supabase.table("contents")
        .select("*")
        .eq("id", content_id)
        .single()
        .execute()
    ).data

    user_id = query.from_user.id

    purchased = (
        supabase.table("purchases")
        .select("id")
        .eq("buyer_id", user_id)
        .eq("content_id", content_id)
        .execute()
    )

    is_owner = item["owner_id"] == user_id
    is_admin = user_id == ADMIN_ID

    has_access = (
        is_owner
        or is_admin
        or bool(purchased.data)
    )

    category = (
        supabase.table("categories")
        .select("name")
        .eq("id", item["category_id"])
        .single()
        .execute()
    ).data

    region = (
        supabase.table("regions")
        .select("name")
        .eq("id", item["region_id"])
        .single()
        .execute()
    ).data

    caption = (
        f"📌 {item['title']}\n"
        f"💰 {item['price']} コイン\n"
        f"📂 {category['name']} / {region['name']}"
    )

    buttons = []

    if not has_access:
        caption += "\n\n🔒 購入すると閲覧できます。"

        if not is_owner and not is_admin:
            buttons.append([
                InlineKeyboardButton(
                    "🛒 購入",
                    callback_data=f"buy:{content_id}"
                )
            ])

    if user_id == ADMIN_ID:
        buttons.append([
            InlineKeyboardButton(
                "🗑 削除",
                callback_data=f"delete:{content_id}"
            )
        ])

    if is_owner:
        buttons.append([
            InlineKeyboardButton(
                "💰 価格変更",
                callback_data=f"price:{content_id}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            "🚨 通報",
            callback_data=f"report:{content_id}"
        )
    ])

    markup = InlineKeyboardMarkup(buttons)

    file_id = item["telegram_file_id"]

    if item["media_type"] == "video":
        if has_access:
            await query.message.reply_video(
                video=item["telegram_file_id"],
                caption=caption,
                reply_markup=markup,
            )
        else:
            await query.message.reply_text(
                caption,
                reply_markup=markup,
            )
    else:
        await query.message.reply_document(
            document=file_id,
            caption=caption,
            reply_markup=markup,
        )

async def purchase_content(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()
    
    if not await require_private_callback(update):
        return

    content_id = int(query.data.split(":")[1])
    buyer_id = query.from_user.id

    item = (
        supabase.table("contents")
        .select("*")
        .eq("id", content_id)
        .single()
        .execute()
    ).data

    if item["owner_id"] == buyer_id:
        await query.message.reply_text("自分の投稿は購入できません。")
        return

    exists = (
        supabase.table("purchases")
        .select("id")
        .eq("buyer_id", buyer_id)
        .eq("content_id", content_id)
        .execute()
    )

    if exists.data:
        await query.message.reply_text("すでに購入済みです。")
        return

    buyer = get_user(buyer_id, query.from_user.username)

    if buyer["coin_balance"] < item["price"]:
        await query.message.reply_text("コインが不足しています。")
        return

    seller = get_user(item["owner_id"])

    supabase.table("users").update({
        "coin_balance": buyer["coin_balance"] - item["price"]
    }).eq("telegram_id", buyer_id).execute()

    supabase.table("users").update({
        "coin_balance": seller.get("coin_balance", 0) + item["price"],
        "daily_sales": seller.get("daily_sales", 0) + item["price"],
    }).eq("telegram_id", item["owner_id"]).execute()

    supabase.table("contents").update({
        "purchase_count": item.get("purchase_count", 0) + 1
    }).eq("id", content_id).execute()

    supabase.table("purchases").insert({
        "buyer_id": buyer_id,
        "content_id": content_id,
        "price": item["price"],
    }).execute()

    await query.message.reply_text("✅ 購入が完了しました。")

    category = (
        supabase.table("categories")
        .select("name")
        .eq("id", item["category_id"])
        .single()
        .execute()
    ).data

    region = (
        supabase.table("regions")
        .select("name")
        .eq("id", item["region_id"])
        .single()
        .execute()
    ).data

    caption = (
        f"📌 {item['title']}\n"
        f"💰 {item['price']} コイン\n"
        f"📂 {category['name']} / {region['name']}"
    )

    buttons = [
        [
            InlineKeyboardButton(
                "🚨 通報",
                callback_data=f"report:{content_id}",
            )
        ]
    ]

    if item["media_type"] == "video":
        await query.message.reply_video(
            video=item["telegram_file_id"],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    else:
        await query.message.reply_document(
            document=item["telegram_file_id"],
            caption=caption,
            reply_markup=InlineKeyboardMarkup(buttons),
        )

    return

async def start_change_price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    if not await require_private_callback(update):
        return

    content_id = int(query.data.split(":")[1])

    context.user_data["change_price_content_id"] = content_id

    await query.message.reply_text(
        "新しい価格を入力してください。（2〜99コイン）"
    )
    return CHANGE_PRICE

async def save_new_price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    try:
        price = int(update.message.text)

        if price < 2 or price > 99:
            raise ValueError

    except ValueError:
        await update.message.reply_text(
            "2〜99の数字を入力してください。"
        )
        return CHANGE_PRICE

    content_id = context.user_data["change_price_content_id"]

    supabase.table("contents").update({
        "price": price,
    }).eq("id", content_id).execute()

    context.user_data.pop(
        "change_price_content_id",
        None,
    )
    await update.message.reply_text(
        f"✅ 価格を {price} コインに変更しました。"
    )

    return ConversationHandler.END

async def delete_content(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    if not await require_private_callback(update):
        return

    if query.from_user.id != ADMIN_ID:
        return

    content_id = int(query.data.split(":")[1])

    supabase.table("purchases").delete().eq(
        "content_id", content_id
    ).execute()

    supabase.table("reports").delete().eq(
        "content_id", content_id
    ).execute()

    supabase.table("contents").delete().eq(
        "id", content_id
    ).execute()

    await query.message.reply_text(
        "🗑 投稿を削除しました。"
    )

async def open_admin_menu(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(
            "権限がありません。"
        )
        return

    await update.message.reply_text(
        "🛠 管理メニュー",
        reply_markup=admin_menu(),
    )

async def admin_user_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "🔍 検索するユーザー名を入力してください。"
    )

    return ADMIN_USER_SEARCH

async def admin_user_search(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    keyword = update.message.text.strip()

    result = (
        supabase.table("users")
        .select("*")
        .ilike("username", f"%{keyword}%")
        .limit(10)
        .execute()
    )

    if not result.data:
        await update.message.reply_text(
            "ユーザーが見つかりませんでした。"
        )
        return ADMIN_USER_SEARCH

    keyboard = []

    for user in result.data:
        keyboard.append([
            InlineKeyboardButton(
                f"@{user['username']} ({user['coin_balance']}🪙)",
                callback_data=f"adminuser:{user['telegram_id']}",
            )
        ])

    await update.message.reply_text(
        "ユーザーを選択してください。",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

    return ConversationHandler.END

async def admin_user_detail(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    telegram_id = int(query.data.split(":")[1])

    user = (
        supabase.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .single()
        .execute()
    ).data

    post_count = (
        supabase.table("contents")
        .select("id", count="exact")
        .eq("owner_id", telegram_id)
        .execute()
    ).count

    purchase_count = (
        supabase.table("purchases")
        .select("id", count="exact")
        .eq("buyer_id", telegram_id)
        .execute()
    ).count

    text = (
        f"👤 @{user['username']}\n\n"
        f"🆔 {telegram_id}\n"
        f"🪙 {user['coin_balance']} コイン\n"
        f"📤 投稿数: {post_count}\n"
        f"🛒 購入数: {purchase_count}"
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "➕10",
                callback_data=f"coin:{telegram_id}:10",
            ),
            InlineKeyboardButton(
                "➕50",
                callback_data=f"coin:{telegram_id}:50",
            ),
            InlineKeyboardButton(
                "➕100",
                callback_data=f"coin:{telegram_id}:100",
            ),
        ],
        [
            InlineKeyboardButton(
                "➖10",
                callback_data=f"coin:{telegram_id}:-10",
            ),
            InlineKeyboardButton(
                "➖50",
                callback_data=f"coin:{telegram_id}:-50",
            ),
            InlineKeyboardButton(
                "➖100",
                callback_data=f"coin:{telegram_id}:-100",
            ),
        ],
    ]

    await query.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def admin_change_coin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

    _, telegram_id, amount = query.data.split(":")

    telegram_id = int(telegram_id)
    amount = int(amount)

    result = (
        supabase.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .single()
        .execute()
    )

    user = result.data

    new_balance = max(
        0,
        user["coin_balance"] + amount,
    )

    supabase.table("users").update({
        "coin_balance": new_balance,
    }).eq(
        "telegram_id",
        telegram_id,
    ).execute()

    await query.answer("✅ コインを更新しました")

    user["coin_balance"] = new_balance

    post_count = (
        supabase.table("contents")
        .select("id", count="exact")
        .eq("owner_id", telegram_id)
        .execute()
    ).count

    purchase_count = (
        supabase.table("purchases")
        .select("id", count="exact")
        .eq("buyer_id", telegram_id)
        .execute()
    ).count

    text = (
        f"👤 @{user['username']}\n\n"
        f"🆔 {telegram_id}\n"
        f"🪙 {new_balance} コイン\n"
        f"📤 投稿数: {post_count}\n"
        f"🛒 購入数: {purchase_count}"
    )

    keyboard = [
        [
            InlineKeyboardButton("➕10", callback_data=f"coin:{telegram_id}:10"),
            InlineKeyboardButton("➕50", callback_data=f"coin:{telegram_id}:50"),
            InlineKeyboardButton("➕100", callback_data=f"coin:{telegram_id}:100"),
        ],
        [
            InlineKeyboardButton("➖10", callback_data=f"coin:{telegram_id}:-10"),
            InlineKeyboardButton("➖50", callback_data=f"coin:{telegram_id}:-50"),
            InlineKeyboardButton("➖100", callback_data=f"coin:{telegram_id}:-100"),
        ],
    ]

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )

async def back_to_main(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "メインメニューに戻りました。",
        reply_markup=main_menu(update.effective_user.id),
    )

async def open_region_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != ADMIN_ID:
        return

    keyboard = ReplyKeyboardMarkup(
        [
            [KeyboardButton("➕ 地域追加")],
            [KeyboardButton("➖ 地域削除")],
            [KeyboardButton("⬅️ 戻る")],
        ],
        resize_keyboard=True,
    )

    await update.message.reply_text(
        "📍 地域管理",
        reply_markup=keyboard,
    )

async def open_subcategory_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
    "📂 サブカテゴリ管理",
    reply_markup=subcategory_admin_menu(),
)

async def show_sales_ranking(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != ADMIN_ID:
        return

    since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    purchases = (
        supabase.table("purchases")
        .select("content_id")
        .gte("created_at", since)
        .execute()
    )

    if not purchases.data:
        await update.message.reply_text(
            "過去24時間の購入はありません。"
        )
        return

    counts = {}

    for p in purchases.data:
        cid = p["content_id"]
        counts[cid] = counts.get(cid, 0) + 1

    ranking = sorted(
        counts.items(),
        key=lambda x: x[1],
        reverse=True,
    )[:10]

    medals = ["🥇", "🥈", "🥉"]
    text = "📊 24時間ランキング\n\n"

    for i, (content_id, count) in enumerate(ranking):
        item = (
            supabase.table("contents")
            .select("title")
            .eq("id", content_id)
            .single()
            .execute()
        ).data

        icon = medals[i] if i < 3 else f"{i+1}位"

        text += (
            f"{icon}\n"
            f"📌 {item['title']}\n"
            f"🛒 {count} 件\n\n"
        )

    await update.message.reply_text(text)

async def give_coin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if update.effective_user.id != ADMIN_ID:
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "使い方:\n/givecoin ユーザーID コイン数"
        )
        return

    try:
        telegram_id = int(context.args[0])
        amount = int(context.args[1])
    except ValueError:
        await update.message.reply_text("数字を入力してください。")
        return

    user = (
        supabase.table("users")
        .select("coin_balance")
        .eq("telegram_id", telegram_id)
        .single()
        .execute()
    )

    if not user.data:
        await update.message.reply_text("ユーザーが見つかりません。")
        return

    new_balance = user.data["coin_balance"] + amount

    supabase.table("users").update(
        {"coin_balance": new_balance}
    ).eq(
        "telegram_id", telegram_id
    ).execute()

    await update.message.reply_text(
        f"✅ {telegram_id} に {amount} コイン付与しました。\n"
        f"現在残高: {new_balance}"
    )

async def show_popular_ranking(
    
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not await require_private_chat(update):
        return
    contents = (
        supabase.table("contents")
        .select("title,purchase_count")
        .order("purchase_count", desc=True)
        .limit(5)
        .execute()
    )

    if not contents.data:
        await update.message.reply_text(
            "🔥 人気ランキング\n\nまだランキングデータがありません。"
        )
        return

    medals = ["🥇", "🥈", "🥉"]
    text = "🔥 人気ランキング\n\n"

    for i, item in enumerate(contents.data):
        icon = medals[i] if i < 3 else f"{i+1}位"

        text += (
            f"{icon}\n"
            f"📌 {item['title']}\n"
            f"🛒 {item['purchase_count']} 回購入\n\n"
        )

    await update.message.reply_text(text)

from datetime import datetime, timedelta, timezone

async def daily_ranking_job(context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now(timezone.utc).date()

    start = datetime.combine(
        today,
        datetime.min.time(),
        tzinfo=timezone.utc,
    )

    end = start + timedelta(days=1)

    result = (
        supabase.table("contents")
        .select("*")
        .eq("media_type", "video")
        .gte("created_at", start.isoformat())
        .lt("created_at", end.isoformat())
        .order("purchase_count", desc=True)
        .order("created_at")
        .limit(3)
        .execute()
    )

    rewards = [100, 50, 30]
    medals = ["🥇", "🥈", "🥉"]

    for i, item in enumerate(result.data):
        reward = rewards[i]

        user = get_user(item["owner_id"])

        supabase.table("users").update({
            "coin_balance": user.get("coin_balance", 0) + reward
        }).eq(
            "telegram_id",
            item["owner_id"],
        ).execute()

        await context.bot.send_message(
            chat_id=item["owner_id"],
            text=(
                f"🏆 おめでとうございます！\n\n"
                f"あなたの動画『{item['title']}』が\n"
                f"{i+1}位になりました！\n\n"
                f"🎁 {reward}コイン付与しました！"
            ),
        )

    ranking_text = "🏆 本日の動画ランキング\n\n"

    for i, item in enumerate(result.data):
        ranking_text += (
            f"{medals[i]} {i+1}位\n"
            f"📌 {item['title']}\n"
            f"🛒 {item['purchase_count']}回購入\n"
            f"🎁 {rewards[i]}コイン\n\n"
        )

    await context.bot.send_message(
        chat_id=GROUP_ID,
        text=ranking_text,
    )

import asyncio

async def report_content(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    await query.answer()

    content_id = int(query.data.split(":")[1])

    exists = (
        supabase.table("reports")
        .select("id")
        .eq("content_id", content_id)
        .eq("reporter_id", query.from_user.id)
        .execute()
    )

    if exists.data:
        await query.message.reply_text(
            "すでに通報済みです。"
        )
        return

    supabase.table("reports").insert({
        "content_id": content_id,
        "reporter_id": query.from_user.id,
    }).execute()

    await query.message.reply_text(
        "🚨 通報を受け付けました。"
    )


async def show_reports(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != ADMIN_ID:
        return

    result = (
        supabase.table("reports")
        .select("content_id")
        .eq("resolved", False)
        .execute()
    )

    if not result.data:
        await update.message.reply_text(
            "未対応の通報はありません。"
        )
        return

    text = "🚨 通報一覧\n\n"

    for report in result.data:
        text += f"投稿ID: {report['content_id']}\n"

    await update.message.reply_text(text)




async def open_category_admin(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != ADMIN_ID:
        return

    await update.message.reply_text(
        "🗂 カテゴリ管理",
        reply_markup=category_admin_menu(),
    )


async def list_categories(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    categories = get_categories()

    if not categories:
        await update.message.reply_text(
            "カテゴリがありません。"
        )
        return

    text = "📋 カテゴリ一覧\n\n"

    for c in categories:
        text += f"・{c['name']}\n"

    await update.message.reply_text(text)


async def add_category_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    await update.message.reply_text(
        "追加するカテゴリ名を入力してください。"
    )

    return ADD_CATEGORY

async def add_region_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    await update.message.reply_text(
        "追加する地域名を入力してください。"
    )

    return ADD_REGION

async def add_subcategory_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    categories = get_categories()

    keyboard = [
        [KeyboardButton(c["name"])]
        for c in categories
    ]

    await update.message.reply_text(
        "親カテゴリを選択してください。",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return SELECT_PARENT_CATEGORY

async def delete_subcategory_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    categories = get_categories()

    keyboard = [
        [KeyboardButton(c["name"])]
        for c in categories
    ]

    await update.message.reply_text(
        "削除するサブカテゴリの親カテゴリを選択してください。",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return SELECT_DELETE_PARENT

async def select_delete_parent(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    parent_name = update.message.text

    category = (
        supabase.table("categories")
        .select("id")
        .eq("name", parent_name)
        .single()
        .execute()
    ).data

    context.user_data["delete_parent_id"] = category["id"]

    subs = (
        supabase.table("subcategories")
        .select("name")
        .eq("category_id", category["id"])
        .order("sort_order")
        .execute()
    ).data

    keyboard = [
        [KeyboardButton(s["name"])]
        for s in subs
    ]

    await update.message.reply_text(
        "削除するサブカテゴリを選択してください。",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return DELETE_SUBCATEGORY

async def delete_subcategory(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    name = update.message.text.strip()

    parent_id = context.user_data["delete_parent_id"]

    supabase.table("subcategories").delete().eq(
        "category_id",
        parent_id,
    ).eq(
        "name",
        name,
    ).execute()

    await update.message.reply_text(
        "✅ サブカテゴリを削除しました。",
        reply_markup=subcategory_admin_menu(),
    )

    return ConversationHandler.END

async def select_parent_category(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data["parent_category"] = update.message.text

    await update.message.reply_text(
        "追加するサブカテゴリ名を入力してください。"
    )

    return ADD_SUBCATEGORY

async def add_subcategory(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    name = update.message.text.strip()

    parent_name = context.user_data["parent_category"]

    category = (
        supabase.table("categories")
        .select("id")
        .eq("name", parent_name)
        .single()
        .execute()
    ).data

    count = (
        supabase.table("subcategories")
        .select("*", count="exact")
        .eq("category_id", category["id"])
        .execute()
    )

    sort_order = count.count or 0

    supabase.table("subcategories").insert({
        "category_id": category["id"],
        "name": name,
        "sort_order": sort_order,
    }).execute()

    await update.message.reply_text(
        "✅ サブカテゴリを追加しました。",
        reply_markup=subcategory_admin_menu(),
    )

    return ConversationHandler.END


async def add_category(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    name = update.message.text.strip()

    exists = (
        supabase.table("categories")
        .select("id")
        .eq("name", name)
        .execute()
    )

    if exists.data:
        await update.message.reply_text(
            "そのカテゴリはすでに存在します。"
        )
        return ADD_CATEGORY

    count = (
        supabase.table("categories")
        .select("*", count="exact")
        .execute()
    )

    sort_order = count.count or 0

    supabase.table("categories").insert({
        "name": name,
        "sort_order": sort_order,
    }).execute()

    await update.message.reply_text(
        "✅ カテゴリを追加しました。",
        reply_markup=category_admin_menu(),
    )

    return ConversationHandler.END

async def add_region(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    name = update.message.text.strip()

    exists = (
        supabase.table("regions")
        .select("id")
        .eq("name", name)
        .execute()
    )

    if exists.data:
        await update.message.reply_text(
            "その地域はすでに存在します。"
        )
        return ADD_REGION

    supabase.table("regions").insert({
        "name": name,
    }).execute()

    await update.message.reply_text(
        "✅ 地域を追加しました。",
        reply_markup=ReplyKeyboardMarkup(
            [
                [KeyboardButton("➕ 地域追加")],
                [KeyboardButton("➖ 地域削除")],
                [KeyboardButton("⬅️ 戻る")],
            ],
            resize_keyboard=True,
        ),
    )

    return ConversationHandler.END

async def delete_region(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    name = update.message.text.strip()

    supabase.table("regions").delete().eq(
        "name",
        name,
    ).execute()

    await update.message.reply_text(
        "✅ 地域を削除しました。",
        reply_markup=ReplyKeyboardMarkup(
            [
                [KeyboardButton("➕ 地域追加")],
                [KeyboardButton("➖ 地域削除")],
                [KeyboardButton("⬅️ 戻る")],
            ],
            resize_keyboard=True,
        ),
    )

    return ConversationHandler.END

async def delete_category_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    categories = get_categories()

    keyboard = [
        [KeyboardButton(c["name"])]
        for c in categories
    ]

    await update.message.reply_text(
        "削除するカテゴリを選択してください。",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return DELETE_CATEGORY

async def delete_region_start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    regions = (
        supabase.table("regions")
        .select("name")
        .order("name")
        .execute()
    ).data

    keyboard = [
        [KeyboardButton(r["name"])]
        for r in regions
    ]

    await update.message.reply_text(
        "削除する地域を選択してください。",
        reply_markup=ReplyKeyboardMarkup(
            keyboard,
            resize_keyboard=True,
            one_time_keyboard=True,
        ),
    )

    return DELETE_REGION

async def delete_category(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    name = update.message.text

    # カテゴリID取得
    category = (
        supabase.table("categories")
        .select("id")
        .eq("name", name)
        .single()
        .execute()
    )

    category_id = category.data["id"]

    # このカテゴリの投稿を全部削除
    supabase.table("contents").delete().eq(
        "category_id",
        category_id,
    ).execute()

    # サブカテゴリを全部削除
    supabase.table("subcategories").delete().eq(
        "category_id",
        category_id,
    ).execute()

    # 最後にカテゴリ削除
    supabase.table("categories").delete().eq(
        "id",
        category_id,
    ).execute()

    await update.message.reply_text(
        "✅ カテゴリを削除しました。",
        reply_markup=category_admin_menu(),
    )

    return ConversationHandler.END

async def cancel(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    context.user_data.clear()

    await update.message.reply_text(
        "キャンセルしました。",
        reply_markup=main_menu(update.effective_user.id),
    )

    return ConversationHandler.END

async def require_private_chat(update: Update):
    if update.effective_chat.type == ChatType.PRIVATE:
        return True

    return False

async def require_private_callback(update: Update):
    if update.effective_chat.type == ChatType.PRIVATE:
        return True

    query = update.callback_query
    await query.answer(
        "🤖 この機能はBotとのDMで利用してください。",
        show_alert=True,
    )
    return False

async def welcome_new_member(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = (
        "🎉 画像・動画マーケットへようこそ！\n\n"

        "このグループでは、画像や動画の投稿・購入を楽しめます！\n\n"

        "━━━━━━━━━━━━━━\n"
        "📖 ご利用方法\n"
        "━━━━━━━━━━━━━━\n"
        "① 下の『🤖 Botを開く』ボタン、またはURLからBotを開く\n"
        "② 『開始（Start）』を押して利用開始\n"
        "③ 画像・動画を投稿してコインを獲得\n"
        "④ コインで他のユーザーの作品を購入\n\n"

        "━━━━━━━━━━━━━━\n"
        "💰 投稿報酬\n"
        "━━━━━━━━━━━━━━\n"
        "🖼 画像：＋10コイン\n"
        "🎥 動画：＋15〜20コイン\n\n"

        "━━━━━━━━━━━━━━\n"
        "⚠ ご利用について\n"
        "━━━━━━━━━━━━━━\n"
        "・Botの機能はDM（個人チャット）でのみ利用できます。\n"
        "・グループ内では投稿・購入・検索などの操作はできません。\n"
        "・購入した作品はBotのDMからいつでも閲覧できます。\n\n"

        "🤖 Botはこちら\n"
        "t.me/develpoing_bot?start=welcome\n\n"

        "👇 下の『🤖 Botを開く』ボタンから始めてください！"

    )

    await update.message.reply_text(text)

app_web = Flask(__name__)


@app_web.route("/")
def home():
    return "Bot is running!"


def run_web():
    port = int(os.environ.get("PORT", 10000))

    app_web.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=False,
    )

import traceback

async def error_handler(update, context):
    print("======== ERROR ========")

    traceback.print_exception(
        type(context.error),
        context.error,
        context.error.__traceback__,
    )

    try:
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "⚠️ エラーが発生しました。\nしばらくしてからもう一度お試しください。"
            )
    except Exception:
        pass

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    from datetime import time
    from zoneinfo import ZoneInfo

    app.add_error_handler(error_handler)

    app.job_queue.run_daily(
        daily_ranking_job,
        time=time(
            hour=0,
            minute=0,
            tzinfo=ZoneInfo("Asia/Tokyo"),
        ),
)

    conv = ConversationHandler(
        allow_reentry=True,
        entry_points=[
    MessageHandler(
        filters.Regex("^📤 投稿$"),
        upload_start,
    ),
    MessageHandler(
        filters.Regex("^📂 カテゴリ検索$"),
        show_contents,
    ),
    MessageHandler(
        filters.Regex("^🔍 タイトル検索$"),
        start_title_search,
    ),
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
                    filters.VIDEO | filters.Document.ALL,
                    save_media,
                )
            ],
            CHANGE_PRICE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    save_new_price,
                )
            ],
            BROWSE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    browse_category,
                )
            ],
            SEARCH_TITLE: [
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        search_title,
    )
],

            ADMIN_USER_SEARCH: [
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        admin_user_search,
    )
],
    
        },
        fallbacks=[
            CommandHandler("cancel", cancel)
        ],
    )

    category_conv = ConversationHandler(
        allow_reentry=True,
        entry_points=[
        MessageHandler(
            filters.Regex("^➕ カテゴリ追加$"),
            add_category_start,
        ),
        MessageHandler(
            filters.Regex("^➖ カテゴリ削除$"),
            delete_category_start,
        ),
        MessageHandler(
            filters.Regex("^➕ 地域追加$"),
            add_region_start,
        ),
        MessageHandler(
            filters.Regex("^➖ 地域削除$"),
            delete_region_start,
        ),
        MessageHandler(
            filters.Regex("^➕ サブカテゴリ追加$"),
            add_subcategory_start,
        ),
        MessageHandler(
            filters.Regex("^➖ サブカテゴリ削除$"),
            delete_subcategory_start,
        ),
    ],

        states={
    ADD_CATEGORY: [
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            add_category,
        )
    ],
    DELETE_CATEGORY: [
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            delete_category,
        )
    ],
    ADD_REGION: [
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            add_region,
        )
    ],
    DELETE_REGION: [
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            delete_region,
        )
    ],
    SELECT_PARENT_CATEGORY: [
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        select_parent_category,
    )
    ],
    ADD_SUBCATEGORY: [
    MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        add_subcategory,
    )
    ],
    SELECT_DELETE_PARENT: [
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            select_delete_parent,
        )
    ],
    DELETE_SUBCATEGORY: [
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            delete_subcategory,
        )
    ],
    },

        fallbacks=[
            CommandHandler("cancel", cancel)
    ],
    )

    app.add_handler(CommandHandler("start", start))

    app.add_handler(
        MessageHandler(
            filters.Regex("^🪙 残高確認$"),
            show_balance,
        )
    )

    app.add_handler(CommandHandler("givecoin", give_coin))

    app.add_handler(
        MessageHandler(
            filters.Regex("^👤 マイページ$"),
            show_my_page,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^📤 自分の投稿$"),
            show_my_posts,
        )
    )

    app.add_handler(
    MessageHandler(
        filters.Regex("^🧾 購入履歴$"),
        show_purchase_history,
    )
)

    app.add_handler(
        MessageHandler(
            filters.Regex("^🛠 管理$"),
            open_admin_menu,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^📊 売上ランキング$"),
            show_sales_ranking,
        )

    )

    app.add_handler(
    MessageHandler(
        filters.Regex("^🔥 人気ランキング$"),
        show_popular_ranking,
        )
    )


    app.add_handler(
        MessageHandler(
            filters.Regex("^🚨 通報一覧$"),
            show_reports,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^👤 ユーザー管理$"),
            admin_user_start,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^🗂 カテゴリ管理$"),
            open_category_admin,
        )
    )

    app.add_handler(
    MessageHandler(
        filters.Regex("^📍 地域管理$"),
        open_region_admin,
    )
)

    app.add_handler(
    MessageHandler(
        filters.Regex("^📁 サブカテゴリ管理$"),
        open_subcategory_admin,
    )
)

    app.add_handler(
        MessageHandler(
            filters.Regex("^📋 カテゴリ一覧$"),
            list_categories,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^⬅️ 戻る$"),
            back_to_main,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^🎥 動画一覧$"),
            show_videos,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^📄 ファイル一覧$"),
            show_photos,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^🔍 タイトル検索$"),
            start_title_search,
        )
    )

    app.add_handler(conv)
    app.add_handler(category_conv)

    price_conv = ConversationHandler(
    entry_points=[
        CallbackQueryHandler(
            start_change_price,
            pattern="^price:"
        )
    ],
    states={
        CHANGE_PRICE: [
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                save_new_price,
            )
        ]
    },
    fallbacks=[
        CommandHandler("cancel", cancel),
    ],
)

    app.add_handler(price_conv)

    app.add_handler(
        CallbackQueryHandler(
            change_page,
            pattern="^page:"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            show_detail_callback,
            pattern="^detail:"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            browse_page,
            pattern="^page:"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            report_content,
            pattern="^report:"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            purchase_content,
            pattern="^buy:"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            delete_content,
            pattern="^delete:"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_user_detail,
            pattern="^adminuser:"
        )
    )

    app.add_handler(
        CallbackQueryHandler(
            admin_change_coin,
            pattern="^coin:"
        )
    )

    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.NEW_CHAT_MEMBERS,
            welcome_new_member,
        )
    )

    app.add_handler(
        MessageHandler(
            filters.Regex("^🧾 購入履歴$"),
            show_purchase_history,
        )
    )

    print("Bot 起動中...")

    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
        stop_signals=None,
        close_loop=False,
    )


if __name__ == "__main__":
    web_thread = Thread(target=run_web)
    web_thread.daemon = True
    web_thread.start()

    main()
    