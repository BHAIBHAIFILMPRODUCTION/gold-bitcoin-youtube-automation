import os, json, base64, subprocess, textwrap, random, hashlib
from market_brief import build_topic
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

def fmt_chart_value(value):
    return f"{value:,.2f}"

def make_slide(title, body, idx, topic_title, path, chart_data=None):
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
    # Use real recent market closes on the relevant technical-analysis slides.
    series = []
    series_label = ""
    if idx == 6 and chart_data:
        series, series_label = chart_data.get("gold", []), "GOLD FUTURES • RECENT HOURLY CLOSES"
    elif idx == 7 and chart_data:
        series, series_label = chart_data.get("bitcoin", []), "BITCOIN • RECENT HOURLY CLOSES"
    if len(series) >= 2:
        left, right, top, bottom = 760, W-125, 700, H-170
        d.text((left, top-42), series_label, font=font(23, True), fill=GOLD)
        d.line((left, bottom, right, bottom), fill=(75, 87, 108), width=2)
        lo, hi = min(series), max(series)
        span = hi-lo or 1.0
        pts = []
        for i, value in enumerate(series):
            x = left + int(i * (right-left) / (len(series)-1))
            yv = bottom - int((value-lo) / span * (bottom-top))
            pts.append((x, yv))
        d.line(pts, fill=(86, 180, 220), width=5)
        for px, py in (pts[0], pts[-1]):
            d.ellipse((px-6, py-6, px+6, py+6), fill=GOLD)
        d.text((left, bottom+12), fmt_chart_value(lo), font=font(20), fill=MUTED)
        d.text((right-180, bottom+12), fmt_chart_value(hi), font=font(20), fill=MUTED)
    else:
        d.text((110, H-170), "LIVE MARKET DATA UNAVAILABLE — VERIFY BEFORE TRADING", font=font(24, True), fill=GOLD)
    d.text((110, H-105), topic_title[:90], font=font(23), fill=WHITE)
    d.text((110, H-70), "Educational market scenarios • Not investment advice", font=font(20), fill=MUTED)
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
        make_slide(heading, paragraph, i, topic["title"], image_path, topic.get("chart_data"))
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
    """Create a high-contrast, original 16:9 English market-analysis thumbnail."""
    thumb_path = OUT / f"{topic['slug']}_thumbnail.jpg"
    im = Image.new("RGB", (1280, 720), (7, 13, 29))
    d = ImageDraw.Draw(im)

    # High-contrast editorial layout; no fake profit claims or invented price targets.
    d.rectangle((0, 0, 1280, 16), fill=GOLD)
    d.rectangle((0, 16, 1280, 720), outline=(37, 53, 80), width=3)
    d.text((58, 48), "GLOBAL MARKETS  |  DAILY ANALYSIS", font=font(26, True), fill=GOLD)

    # Main headline sized to remain readable on mobile.
    d.text((55, 145), "GOLD", font=font(102, True), fill=(255, 204, 77))
    d.text((55, 252), "vs", font=font(52, True), fill=(220, 228, 240))
    d.text((55, 315), "BITCOIN", font=font(88, True), fill=(244, 247, 252))

    d.rounded_rectangle((55, 445, 705, 510), radius=14, fill=(21, 34, 58), outline=(75, 102, 143), width=2)
    d.text((78, 463), "NEWS  •  PRICE LEVELS  •  TRADE SETUPS", font=font(22, True), fill=(232, 238, 248))
    d.text((58, 626), "EDUCATIONAL ANALYSIS  |  MANAGE RISK", font=font(20, True), fill=(165, 181, 204))

    # Chart panel on the right: use actual recent closes when available.
    panel = (760, 118, 1218, 575)
    d.rounded_rectangle(panel, radius=24, fill=(12, 22, 42), outline=(65, 82, 111), width=3)
    d.text((795, 145), "RECENT PRICE ACTION", font=font(22, True), fill=(191, 205, 226))
    series = []
    chart_data = topic.get("chart_data") or {}
    series = chart_data.get("gold") or chart_data.get("bitcoin") or []
    if len(series) >= 2:
        left, right, top, bottom = 795, 1180, 215, 480
        lo, hi = min(series), max(series)
        span = hi - lo or 1.0
        pts = []
        for i, value in enumerate(series):
            x = left + int(i * (right-left) / (len(series)-1))
            y = bottom - int((value-lo) / span * (bottom-top))
            pts.append((x, y))
        # Faint grid lines behind the real price series.
        for gy in (260, 325, 390, 455):
            d.line((left, gy, right, gy), fill=(35, 49, 72), width=1)
        d.line(pts, fill=(70, 190, 225), width=6)
        d.ellipse((pts[-1][0]-8, pts[-1][1]-8, pts[-1][0]+8, pts[-1][1]+8), fill=GOLD)
        direction = "UP" if series[-1] > series[0] else "DOWN" if series[-1] < series[0] else "FLAT"
        direction_color = (76, 205, 140) if direction == "UP" else (255, 112, 112) if direction == "DOWN" else (220, 228, 240)
        d.text((795, 505), f"RECENT TREND: {direction}", font=font(23, True), fill=direction_color)
    else:
        # Honest fallback; never draw fabricated chart data.
        d.text((795, 270), "MARKET DATA", font=font(29, True), fill=(225, 232, 244))
        d.text((795, 315), "unavailable", font=font(27), fill=(165, 181, 204))
        d.text((795, 380), "Check data before trading", font=font(19), fill=(165, 181, 204))

    # Date stamp adds freshness without claiming the video is a live stream.
    date_text = datetime.now(timezone.utc).strftime("%d %b %Y  |  UTC")
    d.text((795, 545), date_text, font=font(19, True), fill=(165, 181, 204))
    im.save(thumb_path, format="JPEG", quality=94, optimize=True)
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
        "status": {"privacyStatus": "unlisted", "selfDeclaredMadeForKids": False}
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
    # Build a fresh English-language briefing from current market data and verified RSS headlines.
    topic = build_topic()
    print("Selected live-market topic:", topic["title"])
    video = create_video(topic)
    print("Created:", video, "size:", round(video.stat().st_size / 1024 / 1024, 1), "MB")
    upload(video, topic)

if __name__ == "__main__":
    main()
