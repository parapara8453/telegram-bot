from database import supabase


def get_user(telegram_id, username=None):
    result = (
        supabase.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .execute()
    )

    if result.data:
        return result.data[0]

    supabase.table("users").insert(
        {
            "telegram_id": telegram_id,
            "username": username,
            "coin_balance": 0,
        }
    ).execute()

    return (
        supabase.table("users")
        .select("*")
        .eq("telegram_id", telegram_id)
        .single()
        .execute()
    ).data