import requests
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ---------- CONFIG ----------
USER = os.getenv("API_USER")

BASE_URL = "https://api.cdnlivetv.ru/api/v1/events/sports/"
SOURCE_URL = f"{BASE_URL}?user={USER}&plan=vip"

OUTPUT_FILE = "playlist.m3u"

REFERER = "https://edge.cdnlivetv.ru"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"

TIMEOUT = 8
MAX_WORKERS = 10

HEADERS = {
    "User-Agent": UA,
    "Referer": REFERER,
    "Origin": REFERER
}

# ---------- FETCH JSON ----------
def fetch_json():
    try:
        r = requests.get(SOURCE_URL, headers={"User-Agent": UA}, timeout=TIMEOUT)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print("Fetch error:", e)
        return None

# ---------- EXTRACT ----------
def extract_links(data):
    """
    API structure handle (safe parsing)
    """
    results = []

    if not data:
        return results

    try:
        events = data.get("events", [])

        for event in events:
            name = event.get("title", "Unknown")

            streams = event.get("streams", [])
            for s in streams:
                url = s.get("url")
                if url and ".m3u8" in url:
                    results.append((name, url))

    except Exception as e:
        print("Parse error:", e)

    return results

# ---------- VALIDATE ----------
def check_link(item):
    name, url = item

    try:
        r = requests.head(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if r.status_code == 200:
            return (name, url)

        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT, stream=True)
        if r.status_code == 200:
            return (name, url)
    except:
        pass

    return None

# ---------- PARALLEL FILTER ----------
def filter_links(items):
    valid = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(check_link, item) for item in items]

        for f in as_completed(futures):
            res = f.result()
            if res:
                valid.append(res)
                print("OK:", res[0])
            else:
                print("FAIL")

    return valid

# ---------- FORMAT ----------
def format_m3u(items):
    lines = ["#EXTM3U"]

    for name, url in items:
        lines.append(f"#EXTINF:-1,{name}")
        lines.append(f"#EXTVLCOPT:http-referrer={REFERER}")
        lines.append(f"#EXTVLCOPT:http-user-agent={UA}")
        lines.append(url)

    return "\n".join(lines)

# ---------- SAVE ----------
def save(content):
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(content)

# ---------- MAIN ----------
def main():
    print("Start...")

    if not USER:
        print("Missing API_USER")
        save("#EXTM3U\n")
        return

    data = fetch_json()
    if not data:
        print("No API data")
        save("#EXTM3U\n")
        return

    items = extract_links(data)
    print("Found:", len(items))

    if not items:
        save("#EXTM3U\n")
        return

    valid = filter_links(items)
    print("Working:", len(valid))

    if not valid:
        print("No valid links → empty playlist")
        save("#EXTM3U\n")
        return

    playlist = format_m3u(valid)
    save(playlist)

    print("Done:", datetime.now())


if __name__ == "__main__":
    main()
