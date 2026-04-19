import json
import re
import requests
import base64
import os
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------- CONFIG ----------
API_USER = os.getenv("API_USER")
REFERER = "https://edge.cdnlivetv.ru/"

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

HEADERS = {
    "User-Agent": UA,
    "Referer": REFERER
}

TIMEOUT = 10
MAX_WORKERS = 12

# ---------- SAFE CHECK ----------
if not API_USER:
    print("❌ Missing API_USER")
    exit()

# ---------- DECODE CORE ----------
def _0xe35c(d, e, f):
    g = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ+/"
    h = g[:e]
    i = g[:f]

    j = 0
    for idx, c in enumerate(d[::-1]):
        if c in h:
            j += h.index(c) * (e ** idx)

    if j == 0:
        return '0'

    k = ''
    while j > 0:
        k = i[j % f] + k
        j //= f

    return k

def deobfuscate(h, n, t, e):
    r = ""
    i = 0
    delim = n[e]
    n_map = {c: str(i) for i, c in enumerate(n)}

    while i < len(h):
        s = ""
        while i < len(h) and h[i] != delim:
            s += h[i]
            i += 1
        i += 1

        if s:
            s_digits = "".join(n_map.get(c, c) for c in s)
            char_code = int(_0xe35c(s_digits, e, 10)) - t
            r += chr(char_code)

    return r

def b64_fix(s):
    s = s.replace('-', '+').replace('_', '/')
    while len(s) % 4:
        s += '='
    return base64.b64decode(s).decode()

# ---------- EXTRACT STREAM ----------
def get_m3u8_url(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        html = r.text

        match = re.search(r'eval\(function\(h,u,n,t,e,r\)\{.*?\}\((.*?)\)\)', html, re.DOTALL)
        if not match:
            return None

        params = match.group(1)

        pm = re.search(r'([\'"])((?:(?!\1).)*)\1,\s*\d+,\s*([\'"])((?:(?!\3).)*)\3,\s*(\d+),\s*(\d+)', params, re.DOTALL)
        if not pm:
            return None

        h = pm.group(2)
        n = pm.group(4)
        t = int(pm.group(5))
        e = int(pm.group(6))

        code = deobfuscate(h, n, t, e)

        src_var = re.search(r"src:\s*(\w+)", code)
        if not src_var:
            return None

        var = src_var.group(1)

        assign = re.search(rf"const\s+{var}\s*=\s*(.*?);", code)
        if not assign:
            return None

        line = assign.group(1)

        func = re.search(r"function\s+(\w+)\(str\)", code)
        if not func:
            return None

        fname = func.group(1)

        vars_used = re.findall(rf"{fname}\((\w+)\)", line)
        consts = dict(re.findall(r"const\s+(\w+)\s*=\s*'([^']+)'", code))

        parts = [b64_fix(consts[v]) for v in vars_used if v in consts]

        return "".join(parts)

    except:
        return None

# ---------- CHANNEL LIST ----------
def get_channels():
    url = f"https://api.cdnlivetv.ru/api/v1/channels/?user={API_USER}&plan=free"

    r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    data = r.json().get("channels", [])

    keywords = [
        'sport','football','cricket','espn','wwe','league',
        'dazn','tnt','sky','bein','fox','sony','ssc'
    ]

    result = []
    for ch in data:
        if ch.get("status") != "online":
            continue

        name = ch.get("name","").lower()
        if any(k in name for k in keywords):
            result.append(ch)

    return result

# ---------- PROCESS ----------
def process_channel(ch):
    name = ch.get("name")
    url = ch.get("url")

    m3u8 = get_m3u8_url(url)

    if m3u8:
        return {
            "name": name,
            "code": ch.get("code"),
            "logo": ch.get("image"),
            "url": m3u8
        }
    return None

# ---------- MAIN ----------
def main():
    channels = get_channels()

    results = []

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = [executor.submit(process_channel, ch) for ch in channels]

        for f in as_completed(futures):
            res = f.result()
            if res:
                results.append(res)
                print("OK:", res["name"])
            else:
                print("FAIL")

    # timezone +6
    now = datetime.now(timezone(timedelta(hours=6))).strftime("%Y-%m-%d %H:%M:%S %z")

    with open("playlist.m3u", "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        f.write("#Created_by: freeiotv25\n")
        f.write(f"#Last_updated: {now}\n")
        f.write(f"#Total_channels: {len(results)}\n")

        for ch in results:
            f.write(
                f'#EXTINF:-1 tvg-id="{ch["code"]}" tvg-name="{ch["name"]}" tvg-logo="{ch["logo"]}",{ch["name"]}\n'
            )
            f.write(f"#EXTVLCOPT:http-referrer={REFERER}\n")
            f.write(f"{ch['url']}\n")

    print("✅ Done:", len(results))


if __name__ == "__main__":
    main()
