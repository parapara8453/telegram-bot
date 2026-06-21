import os
from flask import Flask
from threading import Thread
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

from supabase import create_client


load_dotenv()

TOKEN = os.getenv("TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

ADMIN_ID = 8214877974

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

(
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
) = range(11)

PAGE_SIZE = 10

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

def main_menu(user_id):
    keyboard = [
        [KeyboardButton("📤 投稿")],
        [
            KeyboardButton("🎥 動画一覧"),
            KeyboardButton("🖼 写真一覧"),
        ],
        [
            KeyboardButton("🔍 タイトル検索"),
            KeyboardButton("📂 カテゴリ検索"),
        ],
        [KeyboardButton("🔥 人気ランキング")],
        [
            KeyboardButton("🪙 残高確認"),
            KeyboardButton("👤 マイページ"),
        ],
        [KeyboardButton("🧾 購入履歴")],
    ]

    if user_id == ADMIN_ID:
        keyboard.append([KeyboardButton("🛠 管理")])

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
    )


def admin_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📊 売上ランキング")],
            [KeyboardButton("🚨 通報一覧")],
            [KeyboardButton("🗂 カテゴリ管理")],
            [KeyboardButton("🗑 投稿削除")],
            [KeyboardButton("⬅️ 戻る")],
        ],
        resize_keyboard=True,
    )

def category_admin_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📋 カテゴリ一覧")],
            [KeyboardButton("➕ カテゴリ追加")],
            [KeyboardButton("➖ カテゴリ削除")],
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
    if media_type == "photo":
        return 10
    return 20 if file_size >= 100 * 1024 * 1024 else 15


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()

    await update.message.reply_text(
        "メニューを選択してください。",
        reply_markup=main_menu(update.effective_user.id),
    )


async def show_balance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = get_user(
        update.effective_user.id,
        update.effective_user.username,
    )

    await update.message.reply_text(
        f"🪙 現在の残高: {user['coin_balance']} コイン"
    )




async def show_my_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

async def show_purchase_history(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
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

    text = "🧾 購入履歴\n\n"

    for p in result.data:
        item = (
            supabase.table("contents")
            .select("title")
            .eq("id", p["content_id"])
            .single()
            .execute()
        ).data

        text += f"・{item['title']}\n"

    await update.message.reply_text(text)


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
            one_time_keyboard=True,
        ),
    )

    return MEDIA_TYPE


async def select_media_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["media_type"] = (
        "video" if update.message.text == "🎥 動画" else "photo"
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
        else "写真を送信してください。"
    )

    await update.message.reply_text(text)

    return MEDIA


async def save_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        file_id = update.message.photo[-1].file_id

        context.user_data["telegram_file_id"] = file_id
        context.user_data["thumbnail_file_id"] = file_id
        context.user_data["media_type"] = "photo"

        return await finish_upload(update, context)

    if update.message.video:
        context.user_data["telegram_file_id"] = update.message.video.file_id
        context.user_data["file_size"] = update.message.video.file_size or 0
        context.user_data["media_type"] = "video"

        context.user_data["auto_thumbnail_file_id"] = (
            update.message.video.thumbnail.file_id
            if update.message.video.thumbnail
            else update.message.video.file_id
        )

        await update.message.reply_text(
"サムネイルを設定してください。\n"
"写真を送ると手動設定、ボタンを押すと自動設定になります。",
reply_markup=ReplyKeyboardMarkup(
[[KeyboardButton("⚡ 自動設定")]],
resize_keyboard=True,
one_time_keyboard=True,
),
)


        return THUMBNAIL

    await update.message.reply_text("写真または動画を送信してください。")
    return MEDIA


async def save_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.photo:
        await update.message.reply_text("サムネイル用の写真を送信してください。")
        return THUMBNAIL

    context.user_data["thumbnail_file_id"] = update.message.photo[-1].file_id
    return await finish_upload(update, context)


async def auto_thumbnail(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["thumbnail_file_id"] = (
        context.user_data["auto_thumbnail_file_id"]
    )
    return await finish_upload(update, context)


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

    if media_type == "photo":
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
        "thumbnail_file_id": context.user_data["thumbnail_file_id"],
    }).execute()

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
    await show_media_list(update, context, "video", "🎥 動画一覧")


async def show_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_media_list(update, context, "photo", "🖼 写真一覧")


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
        .limit(10)
        .execute()
    )

    if len(result.data) == 0:
        await update.message.reply_text(
            "このカテゴリには投稿がありません。",
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
        "表示したい投稿を選択してください。",
        reply_markup=InlineKeyboardMarkup(buttons),
    )

    return ConversationHandler.END


async def show_detail_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()
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

    buttons.append([
        InlineKeyboardButton(
            "🚨 通報",
            callback_data=f"report:{content_id}"
        )
    ])

    markup = InlineKeyboardMarkup(buttons)

    file_id = (
        item["telegram_file_id"]
        if has_access else item["thumbnail_file_id"]
    )

    if item["media_type"] == "video":
        await query.message.reply_video(
            video=file_id,
            caption=caption,
            reply_markup=markup,
        )
    else:
        await query.message.reply_photo(
            photo=file_id,
            caption=caption,
            reply_markup=markup,
        )


async def purchase_content(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

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

    fake = type("x",(object,),{})()
    fake.callback_query = type("y",(object,),{
        "answer": query.answer,
        "edit_message_reply_markup": query.edit_message_reply_markup,
        "from_user": query.from_user,
        "message": query.message,
        "data": f"detail:{content_id}",
    })()

    await show_detail_callback(fake, context)



async def delete_content(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query
    await query.answer()

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


async def back_to_main(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    await update.message.reply_text(
        "メインメニューに戻りました。",
        reply_markup=main_menu(update.effective_user.id),
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


async def delete_category(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    name = update.message.text

    supabase.table("categories").delete().eq(
        "name",
        name,
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

async def welcome_new_member(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    text = (
        "🎉 ようこそ！\n\n"
        "このグループでは画像や動画を投稿・購入できます。\n\n"
        "【使い方】\n"
        "1. ボットを開く\n"
        "2. /start を送信\n"
        "3. 投稿してコインを獲得\n"
        "4. コインで他の投稿を購入\n\n"
        "🎁 投稿報酬\n"
        "🖼 画像: +10コイン（1日5件まで）\n"
        "🎥 動画: +15〜20コイン（1日5件まで）\n\n"
        "まずは /start を送信してください！"
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


def main():
    app = ApplicationBuilder().token(TOKEN).build()

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
                    filters.PHOTO | filters.VIDEO,
                    save_media,
                )
            ],
            THUMBNAIL: [
                MessageHandler(
                    filters.PHOTO,
                    save_thumbnail,
                ),
                MessageHandler(
                    filters.Regex("^⚡ 自動設定$"),
                    auto_thumbnail,
                ),
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

    app.add_handler(
        MessageHandler(
            filters.Regex("^👤 マイページ$"),
            show_my_page,
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
            filters.Regex("^🚨 通報一覧$"),
            show_reports,
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
            filters.Regex("^🖼 写真一覧$"),
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
    