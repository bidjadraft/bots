import feedparser
import requests
import os
import time
import xml.etree.ElementTree as ET

# إعدادات
RSS_URL = "https://feed.alternativeto.net/news/all"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
LAST_ID_FILE = "last_sent_id.txt"
RSS_OUTPUT_PATH = "rss.xml"  # مسار حفظ ملف RSS

def read_last_sent_id():
    if not os.path.exists(LAST_ID_FILE):
        return None
    with open(LAST_ID_FILE, "r") as f:
        return f.read().strip()

def write_last_sent_id(post_id):
    with open(LAST_ID_FILE, "w") as f:
        f.write(post_id)

def call_gemini_api(prompt, max_retries=10, wait_seconds=10):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt}
                ]
            }
        ]
    }
    headers = {'Content-Type': 'application/json'}

    for attempt in range(max_retries):
        response = requests.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            try:
                return data['candidates'][0]['content']['parts'][0]['text']
            except Exception:
                return None
        else:
            if response.status_code == 503 or "overloaded" in response.text:
                print(f"محاولة {attempt+1} فشلت بسبب ازدحام الخدمة. إعادة المحاولة بعد {wait_seconds} ثانية...")
                time.sleep(wait_seconds)
            else:
                print(f"حدث خطأ آخر في الاتصال بـ Gemini: {response.text}")
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
    ET.SubElement(channel, "link").text = "https://bidjadraft.github.io/bots/"
    ET.SubElement(channel, "description").text = "ملخص الأخبار من المصادر المختلفة"

    for item in items:
        item_elem = ET.SubElement(channel, "item")
        ET.SubElement(item_elem, "title").text = item["title"]
        ET.SubElement(item_elem, "description").text = item["description"]
        ET.SubElement(item_elem, "link").text = item.get("link", "")
        ET.SubElement(item_elem, "guid").text = item.get("guid", item.get("link", ""))
        if "image" in item:
            ET.SubElement(item_elem, "enclosure", url=item["image"], type="image/jpeg")

    tree = ET.ElementTree(rss)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    tree.write(output_path, encoding="utf-8", xml_declaration=True)
    print(f"تم حفظ ملف RSS في {output_path}")

def main():
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
        print("لا توجد منشورات جديدة للإرسال.")
        return

    items = []

    for entry in entries_to_send:
        post_id = entry.get('id') or entry.get('link')
        description = entry.get('summary', '')

        photo_url = None
        if 'media_content' in entry and len(entry.media_content) > 0:
            photo_url = entry.media_content[0]['url']
        elif 'enclosures' in entry and len(entry.enclosures) > 0:
            photo_url = entry.enclosures[0]['url']
        if not photo_url:
            photo_url = "https://via.placeholder.com/600x400.png?text=No+Image"

        title = summarize_title(description)
        if title is None:
            print("فشل تلخيص العنوان، تخطي المنشور.")
            continue

        description_summary = summarize_description(description)
        if description_summary is None:
            print("فشل تلخيص الوصف، تخطي المنشور.")
            continue

        items.append({
            "title": title,
            "description": description_summary,
            "link": entry.get('link', ''),
            "guid": post_id,
            "image": photo_url
        })

        write_last_sent_id(post_id)

    create_rss_xml(items)

if __name__ == "__main__":
    main()
