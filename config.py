import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

ADMIN_ID = 8214877974

PAGE_SIZE = 10

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