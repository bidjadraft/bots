import asyncio
import feedparser
import requests
import os
import json
from bs4 import BeautifulSoup

# إعدادات البوت والقناة
TELEGRAM_TOKEN = "8047551966:AAHemh18f1PN9C2zQb3_Byd_5frRcVBDciE"
TELEGRAM_CHANNEL_ID = "-1002121204099"
RSS_URL = "https://aus.social/@bidjadraft.rss"
LAST_ID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_draft.txt")

def read_last_sent_id():
    try:
        with open(LAST_ID_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        return None

def write_last_sent_id(post_id):
    try:
        with open(LAST_ID_FILE, "w") as f:
            f.write(post_id)
    except Exception as e:
        print(f"خطأ في حفظ الملف: {e}")

def clean_html_and_unescape(raw_html):
    soup = BeautifulSoup(raw_html, "html.parser")
    text = soup.get_text(separator='\n').strip()
    lines = [line.strip() for line in text.split('\n') if line.strip()]
    return '\n\n'.join(lines)

def send_telegram_media_group_with_caption(media_urls, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMediaGroup"
    media = []
    for i, media_url in enumerate(media_urls[:10]):
        media_item = {
            "type": "photo",
            "media": media_url
        }
        if i == 0:
            media_item["caption"] = caption
            media_item["parse_mode"] = "HTML"
        media.append(media_item)

    data = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "media": json.dumps(media)
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        print(f"تم الإرسال إلى تلغرام (عدة صور).")
        return True
    else:
        print(f"فشل الإرسال إلى تلغرام (عدة صور): {response.text}")
        return False

def send_telegram_text(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        print("تم الإرسال إلى تلغرام (نص).")
        return True
    else:
        print(f"فشل الإرسال إلى تلغرام (نص): {response.text}")
        return False

async def main():
    feed = feedparser.parse(RSS_URL)
    entries = feed.entries
    if not entries:
        print("لا توجد منشورات في الخلاصة.")
        return

    last_sent_id = read_last_sent_id()
    entries = sorted(entries, key=lambda e: e.get('published_parsed', 0))

    if not last_sent_id:
        entries_to_send = [entries[-1]]
    else:
        entries_to_send = []
        found_last = False
        for e in entries:
            post_id = e.get('id') or e.get('link')
            if not post_id:
                continue
            if found_last:
                entries_to_send.append(e)
            elif post_id == last_sent_id:
                found_last = True
        if not found_last:
            entries_to_send = entries

    if not entries_to_send:
        print("لا توجد منشورات جديدة للنشر.")
        return

    for e in entries_to_send:
        post_id = e.get('id') or e.get('link')
        raw_desc = e.get('description') or e.get('summary') or ''
        text = clean_html_and_unescape(raw_desc)

        media_urls = []
        videos = []

        media_contents = e.get('media_content', [])
        for media in media_contents:
            url_media = media.get('url')
            if url_media:
                if any(url_media.lower().endswith(ext) for ext in (".mp4", ".mov", ".avi", ".mkv", ".webm")):
                    videos.append(url_media)
                elif any(url_media.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")):
                    media_urls.append(url_media)

        enclosures = e.get('enclosures', [])
        for enc in enclosures:
            url_media = enc.get('url')
            if url_media:
                if any(url_media.lower().endswith(ext) for ext in (".mp4", ".mov", ".avi", ".mkv", ".webm")):
                    videos.append(url_media)
                elif any(url_media.lower().endswith(ext) for ext in (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp")):
                    media_urls.append(url_media)

        # إزالة التكرارات
        media_urls = list(dict.fromkeys(media_urls))
        videos = list(dict.fromkeys(videos))

        print(f"منشور جديد: {post_id}")
        print(f"النص: {text}")
        print(f"عدد الصور: {len(media_urls)}")
        print(f"عدد الفيديوهات: {len(videos)}")

        sent = False
        if videos:
            # أرسل أول فيديو فقط منفرد مع التعليق
            video_url = videos[0]
            url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendVideo"
            data = {
                "chat_id": TELEGRAM_CHANNEL_ID,
                "video": video_url,
                "caption": text,
                "parse_mode": "HTML"
            }
            response = requests.post(url_api, data=data)
            if response.status_code == 200:
                print("تم الإرسال إلى تلغرام (فيديو واحد).")
                sent = True
            else:
                print(f"فشل الإرسال إلى تلغرام (فيديو واحد): {response.text}")
                sent = False
        else:
            # لا يوجد فيديوهات، تعالج الصور حسب العدد
            if len(media_urls) == 0:
                sent = send_telegram_text(text)
            elif len(media_urls) == 1:
                # صورة واحدة مع تعليق
                photo_url = media_urls[0]
                url_api = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendPhoto"
                data = {
                    "chat_id": TELEGRAM_CHANNEL_ID,
                    "photo": photo_url,
                    "caption": text,
                    "parse_mode": "HTML"
                }
                response = requests.post(url_api, data=data)
                if response.status_code == 200:
                    print("تم الإرسال إلى تلغرام (صورة واحدة).")
                    sent = True
                else:
                    print(f"فشل الإرسال إلى تلغرام (صورة واحدة): {response.text}")
                    sent = False
            elif 2 <= len(media_urls) <= 4:
                # 2 - 4 صور كـ مجموعة صور
                sent = send_telegram_media_group_with_caption(media_urls[:4], text)
            else:
                # أكثر من 4 صور - نرسل أول 4 فقط كمجموعة صور مع تعليق
                sent = send_telegram_media_group_with_caption(media_urls[:4], text)

        if sent:
            write_last_sent_id(post_id)
            await asyncio.sleep(1)
        else:
            print(f"فشل الإرسال: {post_id}")

if __name__ == "__main__":
    asyncio.run(main())
