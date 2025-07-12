import asyncio
import feedparser
import requests
import os
import time

# حفظ ملف last_sent_id.txt في نفس مجلد tech.py
LAST_ID_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "last_sent_id.txt")

RSS_URL = "https://feed.alternativeto.net/news/all"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MASTODON_ACCESS_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")
MASTODON_API_BASE_URL = "https://mastodon.social"

def read_last_sent_id():
    if not os.path.exists(LAST_ID_FILE):
        print(f"ملف {LAST_ID_FILE} غير موجود، سيتم إنشاؤه عند أول حفظ.")
        return None
    try:
        with open(LAST_ID_FILE, "r") as f:
            last_id = f.read().strip()
            print(f"تم قراءة آخر معرف منشور: {last_id}")
            return last_id
    except Exception as e:
        print(f"خطأ أثناء قراءة الملف {LAST_ID_FILE}: {e}")
        return None

def write_last_sent_id(post_id):
    try:
        with open(LAST_ID_FILE, "w") as f:
            f.write(post_id)
        print(f"تم حفظ آخر معرف منشور: {post_id} في الملف {LAST_ID_FILE}")
    except Exception as e:
        print(f"خطأ أثناء حفظ الملف {LAST_ID_FILE}: {e}")

def summarize_with_gemini(text, max_retries=10, wait_seconds=10):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    prompt = f"لخص النص باللغة العربية، احرص أن لا يتعدى 245 حرفًا بما في ذلك المسافات وعلامات الترقيم:\n{text}"
    payload = {
        "contents": [
            {
                "parts": [{"text": prompt}]
            }
        ],
        "generationConfig": {
            "maxOutputTokens": 240,
            "temperature": 0.7,
            "topP": 0.8
        }
    }
    headers = {'Content-Type': 'application/json'}

    for attempt in range(max_retries):
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            try:
                return data['candidates'][0]['content']['parts'][0]['text']
            except Exception:
                print("فشل استخراج الملخص من الاستجابة.")
                return None
        else:
            if response.status_code == 503 or "overloaded" in response.text:
                print(f"محاولة {attempt+1} فشلت بسبب ازدحام الخدمة. إعادة المحاولة بعد {wait_seconds} ثانية...")
                time.sleep(wait_seconds)
            else:
                print(f"خطأ في الاتصال بـ Gemini: {response.status_code} - {response.text}")
                return None
    print("فشلت كل المحاولات مع Gemini.")
    return None

def upload_media_to_mastodon(image_url):
    try:
        img_response = requests.get(image_url)
        img_response.raise_for_status()
    except Exception as e:
        print(f"فشل تحميل الصورة من {image_url}: {e}")
        return None

    files = {'file': ('image.jpg', img_response.content)}
    headers = {"Authorization": f"Bearer {MASTODON_ACCESS_TOKEN}"}
    upload_url = f"{MASTODON_API_BASE_URL}/api/v2/media"

    response = requests.post(upload_url, headers=headers, files=files)
    if response.status_code in (200, 202):
        media_id = response.json().get('id')
        if media_id:
            print("تم رفع الصورة بنجاح.")
            return media_id
        else:
            print("لم يتم الحصول على media_id بعد رفع الصورة.")
            return None
    else:
        print(f"فشل رفع الصورة: {response.status_code} - {response.text}")
        return None

def post_to_mastodon(text, image_url=None):
    headers = {"Authorization": f"Bearer {MASTODON_ACCESS_TOKEN}"}
    data = {"status": text}
    media_ids = []

    if image_url:
        media_id = upload_media_to_mastodon(image_url)
        if media_id:
            media_ids.append(media_id)
        else:
            print("سيتم إرسال المنشور بدون صورة بسبب فشل رفع الصورة.")

    if media_ids:
        data["media_ids[]"] = media_ids

    post_url = f"{MASTODON_API_BASE_URL}/api/v1/statuses"
    response = requests.post(post_url, headers=headers, data=data)
    if response.status_code == 200:
        print("تم النشر بنجاح على Mastodon.")
        return True
    else:
        print(f"فشل النشر: {response.status_code} - {response.text}")
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
        for entry in entries:
            post_id = entry.get('id') or entry.get('link')
            if not post_id:
                continue
            if found_last:
                entries_to_send.append(entry)
            elif post_id == last_sent_id:
                found_last = True
        if not found_last:
            entries_to_send = entries

    if not entries_to_send:
        print("لا توجد منشورات جديدة للنشر.")
        return

    for entry in entries_to_send:
        post_id = entry.get('id') or entry.get('link')
        description = entry.get('summary', '')

        image_url = None
        if 'media_content' in entry and len(entry.media_content) > 0:
            image_url = entry.media_content[0].get('url')
        elif 'enclosures' in entry and len(entry.enclosures) > 0:
            image_url = entry.enclosures[0].get('url')

        summary = summarize_with_gemini(description)
        if summary is None:
            print("فشل التلخيص، تخطى المنشور.")
            continue

        print(f"منشور جديد: {post_id}")
        print("الملخص:\n", summary)
        if image_url:
            print(f"صورة مرفقة: {image_url}")

        success = post_to_mastodon(summary, image_url=image_url)
        if success:
            write_last_sent_id(post_id)
        else:
            print("لم يتم تحديث ملف آخر معرف بسبب فشل النشر.")

if __name__ == "__main__":
    asyncio.run(main())
