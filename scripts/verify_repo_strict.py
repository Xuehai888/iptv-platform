
# -*- coding: utf-8 -*-
import json, sys
from urllib.request import urlopen, Request
from urllib.error import HTTPError
from urllib.parse import quote
import concurrent.futures

def encode_url(url):
    if '://' not in url:
        return url
    scheme, rest = url.split('://', 1)
    if '/' in rest:
        h, p = rest.split('/', 1)
        try:
            h = h.encode('idna').decode('ascii')
        except Exception:
            pass
        p = quote(p, safe='/')
        return f"{scheme}://{h}/{p}"
    else:
        try:
            return f"{scheme}://{rest.encode('idna').decode('ascii')}"
        except Exception:
            return url

def test(item):
    name = item["name"]
    url = item["url"]
    try:
        req = Request(encode_url(url), headers={
            "User-Agent": "Mozilla/5.0 (Linux; Android 11) AppleWebKit/537.36 TVBox/1.0",
            "Accept": "*/*"
        })
        with urlopen(req, timeout=12) as resp:
            content = resp.read(200000)
            status = resp.status
        text = content.decode('utf-8', errors='ignore')[:10000]
        low = text.lower()
        ct = resp.headers.get('Content-Type', '')
        if 'application/json' in ct or text.strip().startswith(('{', '[')):
            kind = "JSON"
        elif low.startswith('#extm3u') or '#extinf' in low or '.m3u8' in low:
            kind = "M3U"
        elif ',#' in low or '#genre#' in low:
            kind = "TXT"
        elif '<html' in low or 'text/html' in ct:
            kind = "HTML"
        else:
            kind = "UNKNOWN"
        return name, url, status, kind, len(content), True
    except HTTPError as e:
        return name, url, e.code, "HTTPERR", 0, False
    except Exception as e:
        return name, url, 0, "FAIL:" + str(e)[:30], 0, False

data = json.load(open('/opt/iptv/tvbox/repo.json'))
print(f"测试 {len(data['urls'])} 条线路...")
results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=15) as pool:
    futures = {pool.submit(test, it): it for it in data["urls"]}
    for f in concurrent.futures.as_completed(futures):
        results.append(f.result())

GOOD = ("JSON", "M3U", "TXT")
ok = [r for r in results if r[5] and r[3] in GOOD]
bad = [r for r in results if not (r[5] and r[3] in GOOD)]

print(f"\n✅ 可用 {len(ok)}/{len(results)}:")
for name, url, st, kind, size, _ in sorted(ok, key=lambda r: r[0]):
    print(f"  ✅ {name[:34]:<36} {kind:<7} {size}B")
print(f"\n❌ 不可用 {len(bad)}/{len(results)}:")
for name, url, st, kind, size, _ in sorted(bad, key=lambda r: r[0]):
    print(f"  ❌ {name[:34]:<36} {kind}")

# 保存结果供主控处理
json.dump({
    "ok": [[r[0], r[1]] for r in ok],
    "bad": [[r[0], r[1]] for r in bad]
}, open('/tmp/repo_verify_result.json', 'w'), ensure_ascii=False, indent=2)
