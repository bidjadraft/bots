import feedparser
import requests
import os
import time
import xml.etree.ElementTree as ET

# إعدادات
RSS_URL = "https://feed.alternativeto.net/news/all"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MASTODON_INSTANCE = "mastodon.social"  # غيّر إلى مثيل Mastodon الخاص بك
MASTODON_ACCESS_TOKEN = os.getenv("MASTODON_ACCESS_TOKEN")
LAST_ID_FILE = "last_sent_id.txt"
RSS_OUTPUT_PATH = "rss.xml"

def read_last_sent_id():
    if not os.path.exists(LAST_ID_FILE):
        return None
    with open(LAST_ID_FILE, "r") as f:
        return f.read().strip()

def write_last_sent_id(post_id):
    with open(LAST_ID_FILE, "w") as f:
        f.write(post_id)

def call_gemini_api(prompt, max_retries=5, wait_seconds=5):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}]
    }
    headers = {'Content-Type': 'application/json'}

    for attempt in range(max_retries):
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            try:
                data = response.json()
                return data['candidates'][0]['content']['parts'][0]['text']
            except Exception as e:
                print(f"خطأ في تحليل استجابة Gemini: {e}")
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

def summarize_title(text):
    prompt = (
        "لخص النص كعنوان قصير باللغة العربية، يجب أن يبدأ العنوان بكلمة عربية، "
        "مع إبقاء أسماء الخدمات والبرامج والتطبيقات بالإنجليزية كما هي، "
        "وبقية العنوان يكون بالعربية:\n"
        f"{text}"
    )
    return call_gemini_api(prompt)

def summarize_description(text):
    prompt = (
        "لخص النص في فقرتين باللغة العربية، مع إبقاء أسماء الخدمات والبرامج والتطبيقات بالإنجليزية كما هي، "
        "وتأكد أن النص عربي واضح وسلس:\n"
        f"{text}"
    )
    return call_gemini_api(prompt)

def create_rss_xml(items, output_path=RSS_OUTPUT_PATH):
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")

    ET.SubElement(channel, "title").text = "قناة الأخبار"
    ET.SubElement(channel, "link").text = f"https://{MASTODON_INSTANCE}/"
    ET.SubElement(channel, "description").text = "ملخص الأخبار من المصادر المختلفة"

    for item in items:
        item_elem = ET.SubElement(channel, "item")
        ET.SubElement(item_elem, "title").text = item["title"]
        ET.SubElement(item_elem, "description").text = item["description"]
        ET.SubElement(item_elem, "link").text = item.get("link", "")
        ET.SubElement(item_elem, "guid").text = item.get("guid", item.get("link", ""))
        if item.get("image"):
            ET.SubElement(item_elem, "enclosure", url=item["image"], type="image/jpeg")

    tree = ET.ElementTree(rss)
    dir_name = os.path.dirname(output_path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    print(f"تم حفظ ملف RSS في {output_path}")

def post_to_mastodon(status_text, image_url=None):
    url = f"https://{MASTODON_INSTANCE}/api/v1/statuses"
    headers = {
        "Authorization": f"Bearer {MASTODON_ACCESS_TOKEN}"
    }

    media_ids = []
    if image_url:
        try:
            img_resp = requests.get(image_url)
            if img_resp.status_code == 200:
                files = {'file': ('image.jpg', img_resp.content)}
                media_resp = requests.post(f"https://{MASTODON_INSTANCE}/api/v1/media", headers=headers, files=files)
                if media_resp.status_code in (200, 202):
                    media_id = media_resp.json().get("id")
                    if media_id:
                        media_ids.append(media_id)
                else:
                    print(f"فشل رفع الصورة إلى Mastodon: {media_resp.status_code} - {media_resp.text}")
            else:
                print(f"فشل تحميل الصورة من الرابط: {image_url}")
        except Exception as e:
            print(f"خطأ أثناء رفع الصورة: {e}")

    data = {
        "status": status_text,
