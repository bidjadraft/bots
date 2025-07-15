import asyncio
import feedparser
import requests
import os
import json
from bs4 import BeautifulSoup

# إعدادات البوت والقناة
TELEGRAM_TOKEN = "8034451425:AAGrQwwj6rH3TcDdGAk8XlpyND5T0FW5aDY"
TELEGRAM_CHANNEL_ID = "-1002369286715"
RSS_URL = "https://aus.social/@nofab.rss"
LAST_ID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_nofab.txt")

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

def send_telegram_media_group_with_caption(image_urls, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMediaGroup"
    media = []
    for i, img_url in enumerate(image_urls[:10]):
        media_item = {
            "type": "photo",
            "media": img_url
        }
        if i == 0:
            media_item["caption"] = caption
        media.append(media_item)
    data = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "media": json.dumps(media)
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        print("تم الإرسال إلى تلغرام (عدة صور مع تعليق).")
        return True
    else:
        print(f"فشل الإرسال إلى تلغرام (عدة صور): {response.text}")
        return False

def send_telegram_text(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {
        "chat_id": TELEGRAM_CHANNEL_ID,
        "text": text,
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

        image_urls = []
        media_contents = e.get('media_content', [])
        for media in media_contents:
            url_img = media.get('url')
            if url_img:
                image_urls.append(url_img)

        enclosures = e.get('enclosures', [])
        for enc in enclosures:
            url_img = enc.get('url')
            if url_img:
                image_urls.append(url_img)

        image_urls = list(dict.fromkeys(image_urls))

        print(f"منشور جديد: {post_id}")
        print(f"النص: {text}")
        print(f"عدد الصور: {len(image_urls)}")

        if image_urls:
            sent = send_telegram_media_group_with_caption(image_urls, text)
        else:
            sent = send_telegram_text(text)

        if sent:
            write_last_sent_id(post_id)
            await asyncio.sleep(1)  # التمهل ثانية واحدة بين الإرسال
        else:
            print(f"فشل الإرسال: {post_id}")

if __name__ == "__main__":
    asyncio.run(main())

