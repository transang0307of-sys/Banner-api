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

client = httpx.AsyncClient(
    headers={"User-Agent": "Mozilla/5.0"},
    timeout=6.0,
    follow_redirects=True
)

process_pool = ThreadPoolExecutor(max_workers=2)

# ===== FONT (fallback nhẹ cho vercel) =====
def load_font(size):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except:
        return ImageFont.load_default()

# ===== FETCH IMAGE =====
async def fetch_image_bytes(item_id):
    if not item_id or str(item_id) == "0":
        return None

    item_id = str(item_id)

    for repo_num in range(1, 4):  # giảm vòng lặp cho nhanh
        for batch_num in range(1, 10):
            batch_str = f"{batch_num:02d}"
            url = f"https://raw.githubusercontent.com/djdndbdjfi/free-fire-items-{repo_num}/main/items/batch-{batch_str}/{item_id}.png"

            try:
                resp = await client.head(url)
                if resp.status_code == 200:
                    img = await client.get(url)
                    return img.content
            except:
                continue
    return None

def bytes_to_image(img_bytes):
    try:
        if img_bytes:
            return Image.open(io.BytesIO(img_bytes)).convert("RGBA")
    except:
        pass
    return Image.new("RGBA", (100, 100), (0, 0, 0, 0))

# ===== PROCESS IMAGE =====
def process_banner_image(data, avatar_bytes, banner_bytes, pin_bytes):
    avatar = bytes_to_image(avatar_bytes)
    banner = bytes_to_image(banner_bytes)
    pin = bytes_to_image(pin_bytes)

    # FIX NONE
    name = str(data.get("AccountName") or "Unknown")
    guild = str(data.get("GuildName") or "")
    level = str(data.get("AccountLevel") or "0")

    avatar = avatar.resize((400, 400))
    banner = banner.resize((800, 400))

    final = Image.new("RGBA", (1200, 400))
    final.paste(avatar, (0, 0))
    final.paste(banner, (400, 0))

    draw = ImageDraw.Draw(final)

    font_big = load_font(60)
    font_small = load_font(40)

    # text
    draw.text((420, 50), name, font=font_big, fill="white")
    draw.text((420, 150), guild, font=font_small, fill="white")

    # level box
    draw.rectangle((1000, 320, 1200, 400), fill="black")
    draw.text((1020, 330), f"Lvl.{level}", font=font_small, fill="white")

    # pin
    if pin_bytes:
        pin = pin.resize((100, 100))
        final.paste(pin, (0, 300), pin)

    img_io = io.BytesIO()
    final.save(img_io, "PNG")
    img_io.seek(0)
    return img_io

# ===== HOME =====
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
https://your-domain.vercel.app/profile?uid=123456789

━━━━━━━━━━━━━━━━━━

🚀 Powered by DK
"""
    return Response(content=content, media_type="text/plain; charset=utf-8")

# ===== MAIN API =====
@app.get("/profile")
async def get_banner(uid: str):
    if not uid:
        raise HTTPException(status_code=400, detail="Thiếu UID")

    try:
        resp = await client.get(f"{INFO_API_URL}?uid={uid}")

        if resp.status_code != 200:
            raise HTTPException(status_code=502, detail="Lỗi API info")

        data = resp.json()

        account = data.get("AccountInfo") or {}
        equipped = data.get("EquippedItemsInfo") or {}
        profile = data.get("AccountProfileInfo") or {}
        guild = data.get("GuildInfo") or {}

        if not account:
            raise HTTPException(status_code=404, detail="Không tìm thấy")

        avatar_task = fetch_image_bytes(equipped.get("EquippedAvatarId"))
        banner_task = fetch_image_bytes(equipped.get("EquippedBannerId"))

        pin_id = profile.get("Title") or None
        pin_task = fetch_image_bytes(pin_id) if pin_id else asyncio.sleep(0)

        avatar_bytes, banner_bytes, pin_bytes = await asyncio.gather(
            avatar_task, banner_task, pin_task
        )

        if pin_bytes is None:
            pin_bytes = b""

        banner_data = {
            "AccountLevel": str(account.get("AccountLevel") or "0"),
            "AccountName": str(account.get("AccountName") or "Unknown"),
            "GuildName": str(guild.get("GuildName") or "")
        }

        loop = asyncio.get_event_loop()
        img = await loop.run_in_executor(
            process_pool,
            process_banner_image,
            banner_data,
            avatar_bytes,
            banner_bytes,
            pin_bytes
        )

        return Response(content=img.getvalue(), media_type="image/png")

    except Exception as e:
        print("ERROR:", e)
        raise HTTPException(status_code=500, detail=str(e))

# ===== RUN LOCAL =====
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=5000)
