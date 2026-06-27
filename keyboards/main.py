from telegram import ReplyKeyboardMarkup, KeyboardButton

from config import ADMIN_ID

def main_menu(user_id):    
    keyboard = [
        [KeyboardButton("📤 投稿")],
        [
            KeyboardButton("🎥 動画一覧"),
            KeyboardButton("📄 ファイル一覧"),
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
        [KeyboardButton("📤 自分の投稿")],
        [KeyboardButton("🧾 購入履歴")],
    ]

    if user_id == ADMIN_ID:
            keyboard.append([
                KeyboardButton("🛠 管理")
            ])

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
    )


def admin_menu():
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("➕ カテゴリ追加")],
            [KeyboardButton("➖ カテゴリ削除")],
            [KeyboardButton("⬅ 戻る")],
        ],
        resize_keyboard=True,
    )