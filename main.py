import requests
import re
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ---------- CONFIG ----------
USER = os.getenv("API_USER")   # 🔐 from GitHub Secret

SOURCE_URL = f"https://api.cdnlivetv.ru/api/v1/events/sports/?user={USER}&plan=vip"
OUTPUT_FILE = "playlist.m3u"

REFERER = "https://example.com"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"

TIMEOUT = 8
MAX_WORKERS = 10

HEADERS = {
    "User-Agent": UA,
    "Referer": REFERER,
    "Origin": REFERER
}

# ---------- FETCH ----------
def fetch_html():
    try:
        r = requests.get(SOURCE_URL, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print("Fetch error:", e)
        return ""

# ---------- EXTRACT ----------
def extract_links(html):
    pattern = r'https?://[^\s"\']+\.m3u8[^\s"\']*'
    return list(set(re.findall(pattern, html)))

# ---------- VALIDATE ----------
def check_link(url):
    try:
        r = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code == 200:
            return url

        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        if r.status_code == 200:
            return url
    except:
        pass
    return None

# ---------- PARALLEL FILTER ----------
def filter_links(links):
    valid = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(check_link, link): link for link in links}

        for f in as_completed(futures):
            result = f.result()
            if result:
                valid.append(result)
                print("OK")
            else:
                print("FAIL")

    return valid

# ---------- FORMAT ----------
def format_m3u(links):
    lines = ["#EXTM3U"]

    for i, url in enumerate(links):
        lines.append(f"#EXTINF:-1,Channel {i+1}")
        lines.append(f"#EXTVLCOPT:http-referrer={REFERER}")
        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(url)

    return "\n".join(lines)

# ---------- SAVE ----------
def save(data):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(data)

# ---------- MAIN ----------
def main():
    if not USER:
        print("❌ Missing API_USER secret")
        return

    print("Start...")

    html = fetch_html()
    if not html:
        return

    links = extract_links(html)
    print("Found:", len(links))

    if not links:
        return

    valid = filter_links(links)
    print("Working:", len(valid))

    if not valid:
        return

    playlist = format_m3u(valid)
    save(playlist)

    print("Done:", datetime.now())


if __name__ == "__main__":
    main()
