import io
import os
import asyncio
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image, ImageDraw, ImageFont
from concurrent.futures import ThreadPoolExecutor

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await client.aclose()
    process_pool.shutdown()

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

INFO_API_URL = "https://fffinfo.tsunstudio.pw/get"
FONT_FILE = "arial_unicode_bold.otf"
FONT_CHEROKEE = "NotoSansCherokee.ttf"

client = httpx.AsyncClient(
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=10.0,
    follow_redirects=True
)

process_pool = ThreadPoolExecutor(max_workers=4)

def load_unicode_font(size, font_file=FONT_FILE):
    try:
        font_path = os.path.join(os.path.dirname(__file__), font_file)
        if os.path.exists(font_path):
            return ImageFont.truetype(font_path, size)
        return ImageFont.load_default()
    except:
        return ImageFont.load_default()

async def fetch_image_bytes(item_id):
    if not item_id or str(item_id) == "0":
        return None

    item_id = str(item_id)

    for repo_num in range(1, 7):
        if repo_num == 1:
            batch_start, batch_end = 1, 7
        else:
            batch_start = (repo_num - 1) * 6 + 1
            batch_end = batch_start + 6

        for batch_num in range(batch_start, batch_end):
            batch_str = f"{batch_num:02d}"
            url = f"https://raw.githubusercontent.com/djdndbdjfi/free-fire-items-{repo_num}/main/items/batch-{batch_str}/{item_id}.png"

            try:
                resp = await client.head(url)
                if resp.status_code == 200:
                    img_resp = await client.get(url)
                    return img_resp.content
            except:
                continue
    return None

def bytes_to_image(img_bytes):
    if img_bytes:
        return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    return Image.new('RGBA', (100, 100), (0, 0, 0, 0))

def process_banner_image(data, avatar_bytes, banner_bytes, pin_bytes):
    avatar_img = bytes_to_image(avatar_bytes)
    banner_img = bytes_to_image(banner_bytes)
    pin_img = bytes_to_image(pin_bytes)

    level = str(data.get("AccountLevel", "0"))
    name = data.get("AccountName", "Unknown")
    guild = data.get("GuildName", "")

    TARGET_HEIGHT = 400
    avatar_img = avatar_img.resize((TARGET_HEIGHT, TARGET_HEIGHT), Image.LANCZOS)

    b_w, b_h = banner_img.size
    if b_w > 50 and b_h > 50:
        banner_img = banner_img.rotate(3, resample=Image.BICUBIC, expand=True)

        b_w, b_h = banner_img.size
        crop_top, crop_bottom, crop_sides = 0.23, 0.32, 0.17
        left, top = b_w * crop_sides, b_h * crop_top
        right, bottom = b_w * (1 - crop_sides), b_h * (1 - crop_bottom)
        banner_img = banner_img.crop((left, top, right, bottom))

    b_w, b_h = banner_img.size
    if b_h > 0:
        new_banner_w = int(TARGET_HEIGHT * (b_w / b_h) * 2.0)
        banner_img = banner_img.resize((new_banner_w, TARGET_HEIGHT), Image.LANCZOS)
    else:
        banner_img = Image.new("RGBA", (800, 400), (50, 50, 50))

    final_w = TARGET_HEIGHT + new_banner_w
    final_h = TARGET_HEIGHT

    combined = Image.new("RGBA", (final_w, final_h), (0, 0, 0, 0))
    combined.paste(avatar_img, (0, 0))
    combined.paste(banner_img, (TARGET_HEIGHT, 0))

    draw = ImageDraw.Draw(combined)

    font_large = load_unicode_font(125)
    font_small = load_unicode_font(95)
    font_level = load_unicode_font(50)

    stroke_col, text_col = "black", "white"

    def draw_text(x, y, text, font, stroke):
        for dx in range(-stroke, stroke + 1):
            for dy in range(-stroke, stroke + 1):
                draw.text((x + dx, y + dy), text, font=font, fill=stroke_col)
        draw.text((x, y), text, font=font, fill=text_col)

    text_x = TARGET_HEIGHT + 40
    draw_text(text_x, 40, name, font_large, 4)
    draw_text(text_x, 200, guild, font_small, 3)

    if pin_img and pin_img.size != (100, 100):
        pin_img = pin_img.resize((130, 130), Image.LANCZOS)
        combined.paste(pin_img, (0, TARGET_HEIGHT - 130), pin_img)

    level_txt = f"Lvl.{level}"
    draw.rectangle([final_w - 200, final_h - 80, final_w, final_h], fill="black")
    draw.text((final_w - 180, final_h - 60), level_txt, font=font_level, fill="white")

    img_io = io.BytesIO()
    combined.save(img_io, 'PNG')
    img_io.seek(0)
    return img_io


# ===== HOME INFO =====
@app.get("/")
async def home():
    content = """⚡ BANNER API BY DK ⚡

👤 Developer: DK
📱 Telegram : @kaizdev1
🎵 Tiktok   : @kaizdev1
🌐 Facebook : https://facebook.com/dkdev25

━━━━━━━━━━━━━━━━━━

📖 Mô tả API:
Tạo banner Free Fire tự động từ UID người chơi.

📌 Endpoint:
GET /profile?uid={uid}

📥 Kết quả:
→ Trả về ảnh PNG (banner profile)

📍 Ví dụ:
http://127.0.0.1:5000/profile?uid=123456789

━━━━━━━━━━━━━━━━━━

🚀 Powered by DK
"""
    return Response(content=content, media_type="text/plain; charset=utf-8")


# ===== MAIN API =====
@app.get("/profile")
async def get_banner(uid: str):
    if not uid:
        raise HTTPException(status_code=400, detail="UID required")

    try:
        resp = await client.get(f"{INFO_API_URL}?uid={uid}")
        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Info API Error")

        data = resp.json()

        account_info = data.get("AccountInfo", {})
        equipped_items = data.get("EquippedItemsInfo", {})
        profile_info = data.get("AccountProfileInfo", {})
        guild_info = data.get("GuildInfo", {})

        if not account_info:
            raise HTTPException(status_code=404, detail="Not Found")

        avatar_task = fetch_image_bytes(equipped_items.get("EquippedAvatarId"))
        banner_task = fetch_image_bytes(equipped_items.get("EquippedBannerId"))

        pin_id = profile_info.get("Title")
        pin_task = fetch_image_bytes(pin_id) if pin_id else asyncio.sleep(0)

        avatar_bytes, banner_bytes, pin_bytes = await asyncio.gather(
            avatar_task, banner_task, pin_task
        )

        if pin_bytes is None:
            pin_bytes = b''

        loop = asyncio.get_event_loop()
        banner_data = {
            "AccountLevel": account_info.get("AccountLevel", "0"),
            "AccountName": account_info.get("AccountName", "Unknown"),
            "GuildName": guild_info.get("GuildName", "")
        }

        img_io = await loop.run_in_executor(
            process_pool,
            process_banner_image,
            banner_data,
            avatar_bytes,
            banner_bytes,
            pin_bytes
        )

        return Response(content=img_io.getvalue(), media_type="image/png")

    except Exception as e:
        print("Error:", e)
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)