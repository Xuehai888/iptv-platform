# -*- coding: utf-8 -*-
"""合并成人直播源生成 adult.m3u（内容级验证：剔除返回HTML/非视频流的失效频道）"""
import urllib.request, ssl, re, os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

TIMEOUT = 10

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        return r.read().decode('utf-8', errors='replace')

def is_video(head_bytes, content_type):
    ct = (content_type or "").lower()
    if any(k in ct for k in ("mpegurl", "m3u8", "mp4", "video", "octet-stream", "x-msvideo",
                             "quicktime", "x-matroska", "x-flv", "mpeg", "x-mpegts", "vnd.apple")):
        return True
    if head_bytes.startswith(b"#EXTM3U"):
        return True
    if head_bytes.startswith((b"\x1a\x45\xdf\xa3", b"ID3", b"ftyp", b"\x47")):
        return True
    low = head_bytes[:1024].lstrip().lower()
    if low.startswith(b"<!doctype") or low.startswith(b"<html") or b"<title>" in low:
        return False  # HTML 页面
    return False

def check_one(item):
    group, name, url = item
    if not url:
        return False
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "VLC/3.0", "Range": "bytes=0-4095"})
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
            head = r.read(4096)
            status = r.status
            if status not in (200, 206, 301, 302):
                return False
            return is_video(head, r.headers.get("Content-Type", ""))
    except Exception:
        try:
            req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "VLC/3.0"})
            with urllib.request.urlopen(req, timeout=TIMEOUT, context=ctx) as r:
                return r.status in (200, 301, 302)
        except Exception:
            return False

sources = [
    ("vicjl", "https://raw.githubusercontent.com/vicjl/myIPTV/master/Adult.m3u"),
    ("spx",   "https://raw.githubusercontent.com/SPX372928/MyIPTV/master/%E6%88%90%E4%BA%BA%E7%94%B5%E8%A7%86CDN%E7%89%88"),
    ("hj",    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/xxx.m3u8"),
    ("gist4", "https://gist.githubusercontent.com/ageresz/a1b1790b4febbf219df31ba32094e3bf/raw/4_List.m3u"),
]

seen = set()
channels = []

for tag, url in sources:
    try:
        text = fetch(url)
    except Exception as e:
        print("[%s] 拉取失败: %s" % (tag, e))
        continue
    if text.strip().startswith('#EXTM3U'):
        lines = text.split('\n')
        i = 0
        while i < len(lines):
            ln = lines[i].strip()
            if ln.startswith('#EXTINF:'):
                info = ln
                url_line = ''
                j = i + 1
                while j < len(lines) and not lines[j].strip().startswith('#EXTINF:'):
                    if lines[j].strip() and not lines[j].strip().startswith('#'):
                        url_line = lines[j].strip()
                        break
                    j += 1
                m = re.search(r'group-title="([^"]*)"', info)
                group = m.group(1) if m else '\U0001f51e \u6210\u4eba'
                name = info.split(',', 1)[-1].strip() if ',' in info else ''
                if url_line and url_line not in seen:
                    seen.add(url_line)
                    channels.append((group, name, url_line))
                i = j + 1
            else:
                i += 1
    else:
        for ln in text.split('\n'):
            ln = ln.strip()
            if not ln or ln.startswith('#') or ',' not in ln:
                continue
            parts = ln.split(',')
            name = parts[0].strip()
            url = parts[-1].strip()
            if not url.startswith('http'):
                continue
            if url in seen:
                continue
            seen.add(url)
            channels.append(('\U0001f51e \u6210\u4eba', name, url))

print("共收集 %d 个频道（去重后），内容级验证中..." % len(channels))

valid = []
with ThreadPoolExecutor(max_workers=60) as pool:
    futures = {pool.submit(check_one, ch): ch for ch in channels}
    done = 0
    for future in as_completed(futures):
        done += 1
        ch = futures[future]
        try:
            if future.result():
                valid.append(ch)
        except Exception:
            pass
        if done % 200 == 0:
            print("  验证 %d/%d, 有效 %d" % (done, len(channels), len(valid)))

print("验证完成: %d/%d 有效 (%d%%)" % (len(valid), len(channels), int(len(valid)/max(len(channels),1)*100)))

out_lines = ["#EXTM3U", "# 天天电视成人直播 - %d channels (内容级验证)" % len(valid)]
for group, name, url in valid:
    g = group.replace('"', '')
    out_lines.append('#EXTINF:-1 group-title="%s",%s' % (g, name))
    out_lines.append(url)

path = "/opt/iptv/m3u/adult.m3u"
with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines) + "\n")

print("adult.m3u 已生成: %d bytes" % os.path.getsize(path))
grp = Counter(g for g, _, _ in valid)
print("分组:", dict(grp.most_common(10)))
