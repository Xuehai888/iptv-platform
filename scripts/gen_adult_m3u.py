# -*- coding: utf-8 -*-
"""合并成人直播源生成 adult.m3u"""
import urllib.request, ssl, re, os
from collections import Counter

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        return r.read().decode('utf-8', errors='replace')

sources = [
    ("vicjl", "https://raw.githubusercontent.com/vicjl/myIPTV/master/Adult.m3u"),
    ("spx",   "https://raw.githubusercontent.com/SPX372928/MyIPTV/master/%E6%88%90%E4%BA%BA%E7%94%B5%E8%A7%86CDN%E7%89%88"),
    ("hj",    "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/xxx.m3u8"),
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

print("共收集 %d 个频道（去重后）" % len(channels))

out_lines = ["#EXTM3U", "# 天天电视成人直播 - %d channels" % len(channels)]
for group, name, url in channels:
    g = group.replace('"', '')
    out_lines.append('#EXTINF:-1 group-title="%s",%s' % (g, name))
    out_lines.append(url)

path = "/opt/iptv/m3u/adult.m3u"
with open(path, "w", encoding="utf-8") as f:
    f.write("\n".join(out_lines) + "\n")

print("adult.m3u 已生成: %d bytes" % os.path.getsize(path))
grp = Counter(g for g, _, _ in channels)
print("分组:", dict(grp.most_common(10)))
