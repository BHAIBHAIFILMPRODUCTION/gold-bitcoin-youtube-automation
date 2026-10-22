import os, json, base64, subprocess, textwrap, random, hashlib
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ROOT = Path(".")
OUT = Path("out")
OUT.mkdir(exist_ok=True)
W, H = 1920, 1080
BG = (10, 16, 32)
GOLD = (245, 190, 65)
WHITE = (245, 247, 250)
MUTED = (173, 185, 204)

def run(cmd):
    subprocess.run(cmd, check=True)

def font(size, bold=False):
    candidates = [
        "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf" if bold else "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()

def wrap_words(draw, text, fnt, max_width):
    lines, line = [], ""
    for word in text.split():
        test = (line + " " + word).strip()
        if draw.textbbox((0, 0), test, font=fnt)[2] <= max_width:
            line = test
        else:
            if line: lines.append(line)
            line = word
    if line: lines.append(line)
    return lines

def make_slide(title, body, idx, topic_title, path):
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    # subtle gold frame and decorative chart-like lines
    d.rounded_rectangle((55, 55, W-55, H-55), radius=28, outline=GOLD, width=4)
    d.text((105, 95), "GOLD • BITCOIN • MARKET EDUCATION", font=font(30, True), fill=GOLD)
    d.text((105, 165), f"{idx:02d}  /  08", font=font(27), fill=MUTED)
    y = 250
    for line in wrap_words(d, title, font(66, True), W-220):
        d.text((105, y), line, font=font(66, True), fill=WHITE)
        y += 82
    y += 38
    for line in wrap_words(d, body, font(38), W-240):
        d.text((110, y), line, font=font(38), fill=MUTED)
        y += 58
    # decorative bar chart at bottom
    base_y = H-155
    heights = [45, 70, 55, 100, 80, 125, 95, 140, 115, 155, 130, 175]
    for i, h in enumerate(heights):
        x = 110 + i*34
        d.rounded_rectangle((x, base_y-h, x+18, base_y), radius=5, fill=GOLD if i % 3 else (86, 148, 186))
    d.text((650, H-145), topic_title[:70], font=font(25), fill=WHITE)
    d.text((650, H-105), "Educational content • Not investment advice", font=font(22), fill=MUTED)
    im.save(path, quality=92)

def make_audio(text, wav_path):
    # Free Hindi speech synthesis; the workflow installs espeak-ng.
    run(["espeak-ng", "-v", "hi", "-s", "138", "-p", "42", "-w", str(wav_path), text])

def seconds(wav_path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "default=noprint_wrappers=1:nokey=1", str(wav_path)], text=True)
    return float(out.strip())

def create_video(topic):
    work = OUT / "segments"
    work.mkdir(exist_ok=True, parents=True)
    segment_paths = []
    for i, (heading, paragraph) in enumerate(topic["scenes"], start=1):
        image_path = work / f"slide_{i:02d}.jpg"
        wav_path = work / f"voice_{i:02d}.wav"
        mp4_path = work / f"part_{i:02d}.mp4"
        make_slide(heading, paragraph, i, topic["title"], image_path)
        make_audio(paragraph, wav_path)
        dur = seconds(wav_path) + 0.25
        run(["ffmpeg", "-y", "-loop", "1", "-i", str(image_path), "-i", str(wav_path),
             "-t", f"{dur:.2f}", "-c:v", "libx264", "-preset", "ultrafast", "-r", "24",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-shortest", str(mp4_path)])
        segment_paths.append(mp4_path)
    concat_file = work / "concat.txt"
    concat_file.write_text("".join(f"file '{p.resolve()}'\n" for p in segment_paths), encoding="utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    video_path = OUT / f"{topic['slug']}_{stamp}.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file),
         "-c", "copy", "-movflags", "+faststart", str(video_path)])
    return video_path

def make_thumbnail(topic):
    """Create an original 16:9 Hindi thumbnail locally with Pillow."""
    thumb_path = OUT / f"{topic['slug']}_thumbnail.jpg"
    im = Image.new("RGB", (1280, 720), BG)
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((28, 28, 1252, 692), radius=30, outline=GOLD, width=6)
    d.text((75, 72), "GOLD • BITCOIN • HINDI EXPLAINED", font=font(27, True), fill=GOLD)
    # Keep the title to the left so the decorative bars do not obscure the text.
    title_font = font(54, True)
    lines = wrap_words(d, topic["title"], title_font, 900)
    y = 190
    for line in lines[:4]:
        d.text((75, y), line, font=title_font, fill=WHITE)
        y += 72
    d.text((78, 580), "MARKET EDUCATION  •  NOT INVESTMENT ADVICE", font=font(20, True), fill=MUTED)
    base_y = 520
    heights = [70, 110, 86, 145, 116, 180, 138, 205]
    for i, h in enumerate(heights):
        x = 960 + i * 30
        d.rounded_rectangle((x, base_y - h, x + 18, base_y), radius=5,
                            fill=GOLD if i % 2 else (86, 148, 186))
    im.save(thumb_path, format="JPEG", quality=92, optimize=True)
    return thumb_path

def youtube_client():
    raw = os.environ.get("YOUTUBE_TOKEN_JSON", "")
    if not raw:
        raise RuntimeError("Missing YOUTUBE_TOKEN_JSON GitHub Actions secret.")
    token_json = base64.b64decode(raw).decode("utf-8")
    token_path = OUT / "token.json"
    token_path.write_text(token_json, encoding="utf-8")
    data = json.loads(token_json)
    creds = Credentials.from_authorized_user_info(data, scopes=["https://www.googleapis.com/auth/youtube.upload"])
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(), encoding="utf-8")
    return build("youtube", "v3", credentials=creds, cache_discovery=False)

def upload(video_path, topic):
    yt = youtube_client()
    description = (
        f"{topic['title']}\n\n"
        "Yeh video sirf saamanya jaankari aur education ke liye hai. Yeh financial, investment, "
        "tax ya legal advice nahi hai. Gold aur Bitcoin dono ki keemat gir sakti hai. Apni research "
        "karein aur apni situation ke hisaab se qualified professional se salah lein.\n\n"
        "#Bitcoin #Gold #FinancialEducation #Hindi"
    )
    body = {
        "snippet": {
            "title": topic["title"] + " | Gold & Bitcoin Explained",
            "description": description,
            "tags": ["Bitcoin", "Gold", "Hindi", "Hinglish", "financial education", "market basics", "crypto education"],
            "categoryId": "27"
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }
    req = yt.videos().insert(part="snippet,status", body=body,
        media_body=MediaFileUpload(str(video_path), mimetype="video/mp4", resumable=True))
    response = None
    while response is None:
        status, response = req.next_chunk()
        if status:
            print(f"Upload progress: {int(status.progress() * 100)}%")
    video_id = response.get("id")
    print("Uploaded video:", video_id, "https://www.youtube.com/watch?v=" + video_id if video_id else "")
    if video_id:
        try:
            thumbnail_path = make_thumbnail(topic)
            yt.thumbnails().set(
                videoId=video_id,
                media_body=MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
            ).execute()
            print("Custom thumbnail uploaded.")
        except Exception as exc:
            # Video upload is still valid if this channel/API does not permit custom thumbnails.
            print("Thumbnail upload skipped; check channel eligibility/API access:", type(exc).__name__)

def main():
    topics = json.loads(Path("topics.json").read_text(encoding="utf-8"))
    # Each scheduled run chooses a deterministic topic based on UTC date and run slot.
    slot = os.environ.get("VIDEO_SLOT", "1")
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    seed = int(hashlib.sha256(f"{day}-{slot}".encode()).hexdigest()[:8], 16)
    topic = topics[seed % len(topics)]
    print("Selected topic:", topic["title"])
    video = create_video(topic)
    print("Created:", video, "size:", round(video.stat().st_size / 1024 / 1024, 1), "MB")
    upload(video, topic)

if __name__ == "__main__":
    main()
