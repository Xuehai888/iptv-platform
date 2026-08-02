#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV Health Monitor v5 - 含仓库线路逐条测试
============================================
1. Tests source file accessibility + samples channels.
2. 新增：读取 repo.json 全部线路，逐条测试（状态码/内容类型/频道数/抽样可用率）。
Handles BOTH local files and remote URLs correctly.
Completes in < 3 minutes.
"""
import os, sys, re, json, time, logging, hashlib, glob, random
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import OrderedDict

BASE_DIR = "/opt/iptv"
M3U_DIR = os.path.join(BASE_DIR, "m3u")
TXT_DIR = os.path.join(BASE_DIR, "txt")
LOG_DIR = os.path.join(BASE_DIR, "logs")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
REPO_JSON = os.path.join(BASE_DIR, "tvbox", "repo.json")
os.makedirs(REPORT_DIR, exist_ok=True)

TEST_TIMEOUT = 10
SAMPLE_CHANNELS = 5

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "health_check.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger(__name__)


def parse_m3u(content):
    channels = []
    if not content:
        return channels
    lines = content.strip().split("\n")
    current = {}
    for line in lines:
        line = line.strip()
        if line.startswith("#EXTINF:"):
            match = re.search(r'#EXTINF:-?\d+\s*(?:[a-z-]+="[^"]*"\s*)*,(.+)', line)
            name = match.group(1).strip() if match else "Unknown"
            group_m = re.search(r'group-title="([^"]*)"', line)
            group = group_m.group(1) if group_m else "Other"
            current = {"name": name, "group": group}
        elif line and not line.startswith("#"):
            current["url"] = line.strip()
            if "name" in current and "url" in current:
                channels.append(current)
            current = {}
    return channels


def parse_txt(content):
    channels = []
    if not content:
        return channels
    current_group = "Other"
    for line in content.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ",#genre#" in line:
            current_group = line.replace(",#genre#", "").strip()
        elif "," in line:
            parts = line.split(",", 1)
            if len(parts) == 2:
                name, url = parts[0].strip(), parts[1].strip()
                if url.startswith("http"):
                    channels.append({"name": name, "url": url, "group": current_group})
    return channels


def fetch_content(source_spec):
    """
    Fetch content from either a local file or remote URL.
    source_spec can be:
      - A string starting with 'file:' -> local file path
      - A string starting with 'http:'/'https:' -> remote URL
    Returns (content_str, status_info_dict)
    """
    spec = source_spec
    
    if spec.startswith('file:'):
        fpath = spec[5:]
        try:
            size = os.path.getsize(fpath)
            with open(fpath, 'r', encoding='utf-8') as f:
                content = f.read(500000)  # First 500KB
            return content, {"status": 200, "size": size, "error": None}
        except Exception as e:
            return "", {"status": 0, "size": 0, "error": str(e)[:60]}
    
    elif spec.startswith('http'):
        try:
            req = Request(spec, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
            })
            with urlopen(req, timeout=TEST_TIMEOUT) as resp:
                size = int(resp.headers.get('Content-Length', 0))
                content = resp.read(500000).decode('utf-8', errors='replace')
            return content, {"status": resp.status, "size": size, "error": None}
        except HTTPError as e:
            return "", {"status": e.code, "size": 0, "error": str(e)[:60]}
        except Exception as e:
            return "", {"status": 0, "size": 0, "error": str(e)[:60]}
    
    return "", {"status": 0, "size": 0, "error": "Unknown source type"}


def test_sample_channels(channels, n=SAMPLE_CHANNELS):
    """Test N random channels."""
    if not channels:
        return {"ok": 0, "test": 0, "errors": []}
    
    sampled = random.sample(channels, min(n, len(channels)))
    ok_count = 0
    errors = []
    
    def check_one(ch):
        try:
            req = Request(ch["url"], headers={"User-Agent": "VLC/3.0"})
            with urlopen(req, timeout=CHANNEL_TIMEOUT) as resp:
                return resp.status >= 200
        except:
            return False
    
    CHANNEL_TIMEOUT = 4
    with ThreadPoolExecutor(max_workers=10) as pool:
        futures = {pool.submit(check_one, ch): ch for ch in sampled}
        for future in as_completed(futures):
            ch = futures[future]
            try:
                if future.result():
                    ok_count += 1
                else:
                    errors.append(ch["name"])
            except:
                errors.append(ch["name"])
    
    return {"ok": ok_count, "test": len(sampled), "errors": errors[:3]}


def classify_content(content):
    """判断直播内容类型：m3u / txt / json / other"""
    head = (content or "")[:500].strip().lower()
    if head.startswith('{') or head.startswith('['):
        return "json"
    if '#extm3u' in head or '#extinf' in head:
        return "m3u"
    if ',#genre#' in head:
        return "txt"
    return "other"


def test_repo_lines():
    """测试 repo.json 全部线路：状态码 / 内容类型 / 频道数（lives数）"""
    if not os.path.exists(REPO_JSON):
        return [], 0
    try:
        repo = json.load(open(REPO_JSON, encoding='utf-8'))
    except Exception as e:
        return [{"name": "repo.json 解析失败", "url": "", "status": 0, "ok": False,
                 "type": "error", "channels": 0, "error": str(e)[:50]}], 0

    urls = repo.get("urls", [])
    lines = []

    def check_one(item):
        name = item.get("name", "?")
        url = item.get("url", "")
        try:
            content, info = fetch_content(url)
            status = info.get("status", 0)
            ok = status >= 200 and status < 400
            ctype = "other"
            channels = 0
            if content and ok:
                ctype = classify_content(content)
                if ctype == "m3u":
                    channels = len(parse_m3u(content))
                elif ctype == "txt":
                    channels = len(parse_txt(content))
                elif ctype == "json":
                    try:
                        cfg = json.loads(content)
                        if isinstance(cfg, dict):
                            channels = len(cfg.get("lives", []) or [])
                    except Exception:
                        pass
            return {"name": name, "url": url, "status": status, "ok": ok,
                    "type": ctype, "channels": channels, "error": info.get("error")}
        except Exception as e:
            return {"name": name, "url": url, "status": 0, "ok": False,
                    "type": "error", "channels": 0, "error": str(e)[:50]}

    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(check_one, item): item for item in urls}
        for f in as_completed(futures):
            lines.append(f.result())

    lines.sort(key=lambda r: (not r["ok"], r["type"]))
    return lines, len(urls)


def main():
    log.info("=" * 70)
    log.info("IPTV Health Monitor v4 Starting")
    log.info("=" * 70)
    
    start_time = time.time()
    
    # ===================== Sources Definition =====================
    # (显示名, 源地址, 公开直播地址/URL)
    SOURCES = [
        # === LOCAL FILES (read directly from disk) ===
        ("天天电视 · 🇨🇳 中国频道", "file:" + M3U_DIR + "/cn.m3u", "http://207.246.102.108/m3u/cn.m3u"),
        ("天天电视 · 🌍 全球频道", "file:" + M3U_DIR + "/all.m3u", "http://207.246.102.108/m3u/all.m3u"),
        ("天天电视 · 📺 央视频道", "file:" + M3U_DIR + "/cctv.m3u", "http://207.246.102.108/m3u/cctv.m3u"),
        ("天天电视 · 📡 卫视频道", "file:" + M3U_DIR + "/weishi.m3u", "http://207.246.102.108/m3u/weishi.m3u"),
        ("天天电视 · 🏠 地方台", "file:" + M3U_DIR + "/local.m3u", "http://207.246.102.108/m3u/local.m3u"),
        ("天天电视 · 🇭🇰 港澳台", "file:" + M3U_DIR + "/hktwmo.m3u", "http://207.246.102.108/m3u/hktwmo.m3u"),
        ("天天电视 · 🌐 国际频道", "file:" + M3U_DIR + "/international.m3u", "http://207.246.102.108/m3u/international.m3u"),
        
        # === EXTERNAL LIVE SOURCES ===
        ("天天电视 · 📺 悦然直播", "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u", "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u"),
        ("天天电视 · 🌍 悦然全球", "https://raw.githubusercontent.com/YueChan/Live/main/Global.m3u", "https://raw.githubusercontent.com/YueChan/Live/main/Global.m3u"),
        ("天天电视 · 🛰️ 国云直播", "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u", "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u"),
        ("天天电视 · 📡 ZBDS直播", "https://live.zbds.top/tv/iptv4.txt", "https://live.zbds.top/tv/iptv4.txt"),
        ("天天电视 · 📺 苏翔直播", "https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u", "https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u"),
        ("天天电视 · 🌐 自由电视", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"),
        ("天天电视 · 📺 游魂直播", "https://www.iyouhun.com/tv/zb", "https://www.iyouhun.com/tv/zb"),
    ]
    
    # ===================== Step 1: Test all sources =====================
    results = []
    
    # Fix: use wrapper function defined below
    def test_source(name, spec, public_url):
        content, info = fetch_content(spec)
        channels = []
        ok = info["status"] >= 200 if info["status"] else False
        
        if content and ok:
            if "#EXTM3U" in content[:200] or "#EXTINF" in content[:200]:
                channels = parse_m3u(content)
            else:
                channels = parse_txt(content)
        
        # Sample channels only for external sources
        sample_result = None
        channel_rate = None
        if channels and "github" in spec.lower() or "iyouhun" in spec.lower() or "zbds" in spec.lower():
            sr = test_sample_channels(channels)
            sample_result = sr
            channel_rate = round(sr["ok"] / max(sr["test"], 1) * 100, 1)
        
        return {
            "source": name,
            "url": public_url,
            "file_ok": ok,
            "status": info["status"],
            "size": info["size"],
            "error": info["error"],
            "channels": len(channels),
            "sample_ok": sample_result["ok"] if sample_result else None,
            "sample_total": sample_result["test"] if sample_result else None,
            "channel_rate": channel_rate,
            "type": "external" if not spec.startswith("file:") else "local"
        }
    
    with ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(test_source, name, spec, url): (name, spec, url) for name, spec, url in SOURCES}
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
    
    # Sort: external first, then by OK status
    results.sort(key=lambda r: (r["type"] != "external", not r["file_ok"]))
    
    elapsed = time.time() - start_time
    
    # ===================== Generate reports =====================
    ext_results = [r for r in results if r["type"] == "external"]
    ext_ok = len([r for r in ext_results if r["file_ok"]])
    
    overall = {
        "generated_at": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "total_sources": len(results),
        "ext_sources_ok": ext_ok,
        "ext_sources_total": len(ext_results),
        "results": results
    }
    
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = os.path.join(REPORT_DIR, f"health_{ts}.json")
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(overall, f, ensure_ascii=False, indent=2)
    
    # HTML report
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = ""
    for r in results:
        icon = "✅" if r["file_ok"] else "❌"
        color = "#28a745" if r["file_ok"] else "#dc3545"
        
        extra = ""
        if r.get("channel_rate") is not None:
            cr = r["channel_rate"]
            ch_icon = "✅" if cr >= 60 else "⚠️" if cr >= 30 else "❌"
            extra = f"<br><small>{ch_icon} 抽样: {r['sample_ok']}/{r['sample_total']} ({cr}%)</small>"
        
        bar_w = min(r.get("channel_rate") or 0, 100) if r["file_ok"] else 0
        bar_color = "#28a745" if bar_w >= 60 else "#ffc107" if bar_w >= 30 else "#dc3545"
        bar = f'<div style="background:#eee;border-radius:3px;height:6px;width:70px;display:inline-block"><div style="background:{bar_color};height:100%;width:{bar_w:.0f}%;border-radius:3px"></div></div>'
        
        tag = "<span style='color:#007bff'>🌐</span>" if r["type"]=="external" else "<span style='color:green'>💻</span>"
        
        # 直播地址列：显示可点击复制的 URL
        live_url = r.get("url", "")
        if live_url:
            url_html = f'<a href="{live_url}" target="_blank" style="color:#0066cc;word-break:break-all;font-size:0.85em">{live_url}</a>'
        else:
            url_html = '-'
        
        rows += f"""<tr>
            <td>{icon} {r['source']}</td>
            <td>{tag}</td>
            <td>{r['status'] if r['status'] else '-'}</td>
            <td>{r['size'] if r['size'] > 0 else '-'} B</td>
            <td>{extra}</td>
            <td>{bar}</td>
            <td>{url_html}</td>
        </tr>\n"""
    
    valid_rates = [r["channel_rate"] for r in ext_results if r.get("channel_rate") is not None]
    avg_cr = sum(valid_rates) / max(len(valid_rates), 1)
    
    # ===================== Step 2: Test all repo.json lines =====================
    log.info("Testing all repo.json lines...")
    repo_lines, repo_total = test_repo_lines()
    repo_ok = len([r for r in repo_lines if r["ok"]])
    repo_rows = ""
    TYPE_LABEL = {"json": "🎬 配置", "m3u": "📺 直播m3u", "txt": "📺 直播txt", "other": "❓ 其他", "error": "💥 错误"}
    for r in repo_lines:
        icon = "✅" if r["ok"] else "❌"
        tlabel = TYPE_LABEL.get(r["type"], r["type"])
        status = r["status"] if r["status"] else "-"
        chs = r["channels"] if r["channels"] else "-"
        # 有错误信息时显示
        err_txt = ""
        if r.get("error"):
            err_txt = f'<br><small style="color:#dc3545">{r["error"]}</small>'
        url_txt = ""
        if r.get("url"):
            url_txt = f'<br><small><a href="{r["url"]}" target="_blank" style="color:#0066cc;word-break:break-all;font-size:0.8em">{r["url"]}</a></small>'
        repo_rows += f"""<tr>
            <td>{icon} {r['name']}</td>
            <td>{tlabel}</td>
            <td>{status}</td>
            <td>{chs}</td>
            <td>{url_txt}{err_txt}</td>
        </tr>\n"""
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>天天电视健康报告 - {timestamp}</title>
<style>
body {{ font-family: -apple-system, sans-serif; max-width: 1100px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
h1 {{ text-align: center; color: #333; }}
h2 {{ color: #4a90d9; margin-top: 30px; border-bottom: 2px solid #4a90d9; padding-bottom: 5px; }}
.summary {{ display: flex; gap: 15px; margin: 20px 0; flex-wrap: wrap; }}
.card {{ background: white; border-radius: 8px; padding: 15px; box-shadow: 0 1px 4px rgba(0,0,0,0.1); flex: 1; min-width: 120px; text-align: center; }}
.big {{ font-size: 2em; font-weight: bold; color: #4a90d9; }}
table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid #eee; }}
th {{ background: #4a90d9; color: white; }}
tr.fail td {{ background-color: #fff5f5; }}
.updated {{ text-align: center; color: #666; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>📺 天天电视 · 健康报告</h1>
<p class="updated">{timestamp} | Cron: 每12小时自动检测</p>
<div class="summary">
<div class="card"><div class="big">{ext_ok}/{len(ext_results)}</div><div>外部直播源可用</div></div>
<div class="card"><div class="big">{repo_ok}/{repo_total}</div><div>仓库线路可用</div></div>
<div class="card"><div class="big">{avg_cr:.0f}%</div><div>抽样平均可用率</div></div>
<div class="card"><div class="big" style="font-size:1.5em">{round(elapsed)}s</div><div>检测耗时</div></div>
</div>

<h2>🌐 直播源检测</h2>
<table>
<tr><th>来源</th><th>类型</th><th>状态码</th><th>大小</th><th>抽样</th><th>状态</th><th>直播地址</th></tr>
{rows}
</table>

<h2>📦 仓库线路检测（repo.json 全部 {repo_total} 条）</h2>
<table>
<tr><th>线路</th><th>类型</th><th>状态码</th><th>频道/lives数</th><th>地址</th></tr>
{repo_rows}
</table>
</body>
</html>"""
    
    outpath = os.path.join(BASE_DIR, "health_report.html")
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print("\n" + "=" * 60)
    print("IPTV HEALTH MONITOR v5 SUMMARY")
    print("=" * 60)
    print(f"Total sources:    {len(results)}")
    print(f"External sources: {ext_ok}/{len(ext_results)} working")
    print(f"Avg channel rate: {avg_cr:.0f}%")
    print(f"Repo lines:       {repo_ok}/{repo_total} working")
    print(f"Elapsed:          {elapsed:.1f}s")
    print()
    for r in results:
        ch = ""
        if r.get("channel_rate") is not None:
            ch = f" | 📡 {r['sample_ok']}/{r['sample_total']} ({r['channel_rate']}%)"
        icon = "✅" if r["file_ok"] else "❌"
        print(f"{icon} {r['source']:<25} HTTP {r['status']:>3} | {r['channels']} chs|{ch}")
        print(f"     📍 {r.get('url', '-')}")
    print()
    print("--- 仓库线路 ---")
    for r in repo_lines:
        icon = "✅" if r["ok"] else "❌"
        print(f"{icon} {r['name']:<30} {r['type']:<8} HTTP {r['status']:>3} | {r['channels']} chs/lives")
    print(f"\n📊 Report: http://207.246.102.108/health_report.html")
    print(f"📄 JSON:   {json_path}")


if __name__ == "__main__":
    main()
