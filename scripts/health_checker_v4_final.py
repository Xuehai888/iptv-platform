#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IPTV Health Monitor v4 - 【天天电视】品牌版
============================================
Tests source file accessibility + samples channels.
Handles BOTH local files and remote URLs correctly.
Completes in < 2 minutes.
支持 --quick 快速模式（跳过抽样，只测连通性）
"""
import os, sys, re, json, time, logging, hashlib, glob, random
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import OrderedDict

# ===================== 品牌设置 =====================
BRAND_NAME = "天天电视"

def get_branded_name(source_name):
    """映射原始名称到带有品牌前缀的漂亮名称"""
    mapping = {
        "cn.m3u": f"{BRAND_NAME} · 中国",
        "all.m3u": f"{BRAND_NAME} · 全集",
        "cctv.m3u": f"{BRAND_NAME} · 央视",
        "weishi.m3u": f"{BRAND_NAME} · 卫视",
        "hktwmo.m3u": f"{BRAND_NAME} · 港澳台",
        "international.m3u": f"{BRAND_NAME} · 世界",
        "local.m3u": f"{BRAND_NAME} · 地方",
        "🔞 Adult Elite": f"{BRAND_NAME} · 🔞 极乐",
        "🔞 XXX Master": f"{BRAND_NAME} · 🔞 悦动",
        "yuechan_iptv": f"{BRAND_NAME} · 📺 悦然直播",
        "yuechan_global": f"{BRAND_NAME} · 🌍 悦然全球",
        "iyouhun_zb": f"{BRAND_NAME} · 📡 游魂直播",
        "zbds_ipv4": f"{BRAND_NAME} · 📡 ZBDS直播",
        "suxuang_ipv4": f"{BRAND_NAME} · 📡 苏翔直播",
        "Free-TV": f"{BRAND_NAME} · 🌐 自由电视",
        "Guovin-api": f"{BRAND_NAME} · 🛰️ 国云直播",
    }
    for k, v in mapping.items():
        if k in source_name:
            return v
    return f"{BRAND_NAME} · {source_name}"

BASE_DIR = "/opt/iptv"
M3U_DIR = os.path.join(BASE_DIR, "m3u")
TXT_DIR = os.path.join(BASE_DIR, "txt")
LOG_DIR = os.path.join(BASE_DIR, "logs")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(REPORT_DIR, exist_ok=True)

TEST_TIMEOUT = 10
SAMPLE_CHANNELS = 5

QUICK_MODE = "--quick" in sys.argv

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


def main():
    log.info("=" * 70)
    log.info(f"{BRAND_NAME} | IPTV Health Monitor v4 {'[QUICK]' if QUICK_MODE else ''}")
    log.info("=" * 70)
    
    start_time = time.time()
    
    # ===================== Sources Definition =====================
    SOURCES = [
        # === LOCAL FILES (read directly from disk) ===
        ("cn.m3u", "file:" + M3U_DIR + "/cn.m3u"),
        ("all.m3u", "file:" + M3U_DIR + "/all.m3u"),
        ("cctv.m3u", "file:" + M3U_DIR + "/cctv.m3u"),
        ("weishi.m3u", "file:" + M3U_DIR + "/weishi.m3u"),
        ("international.m3u", "file:" + M3U_DIR + "/international.m3u"),
        ("hktwmo.m3u", "file:" + M3U_DIR + "/hktwmo.m3u"),
        
        # === EXTERNAL LIVE SOURCES ===
        ("yuechan_iptv", "https://raw.githubusercontent.com/YueChan/Live/main/IPTV.m3u"),
        ("yuechan_global", "https://raw.githubusercontent.com/YueChan/Live/main/Global.m3u"),
        ("iyouhun_zb", "https://www.iyouhun.com/tv/zb"),
        ("zbds_ipv4", "https://live.zbds.top/tv/iptv4.txt"),
        ("suxuang_ipv4", "https://raw.githubusercontent.com/suxuang/myIPTV/main/ipv4.m3u"),
        ("Free-TV", "https://raw.githubusercontent.com/Free-TV/IPTV/master/playlist.m3u8"),
        ("Guovin-api", "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/result.m3u"),
        ("🔞 Adult Elite", "https://raw.githubusercontent.com/hujingguang/ChinaIPTV/main/xxx.m3u8"),
        ("🔞 XXX Master", "https://gist.github.com/639936/ee108ef4fc3eadcc23c41408fa0d107e"),
    ]
    
    # ===================== Step 1: Test all sources =====================
    results = []
    
    def test_source(name, spec):
        content, info = fetch_content(spec)
        channels = []
        ok = info["status"] >= 200 if info["status"] else False
        
        if content and ok:
            if "#EXTM3U" in content[:200] or "#EXTINF" in content[:200]:
                channels = parse_m3u(content)
            else:
                channels = parse_txt(content)
        
        # Sample channels only for external sources (skip in quick mode)
        sample_result = None
        channel_rate = None
        if channels and not QUICK_MODE and ("github" in spec.lower() or "iyouhun" in spec.lower() or "zbds" in spec.lower()):
            sr = test_sample_channels(channels)
            sample_result = sr
            channel_rate = round(sr["ok"] / max(sr["test"], 1) * 100, 1)
        
        return {
            "source": get_branded_name(name),
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
        futures = {pool.submit(test_source, name, spec): (name, spec) for name, spec in SOURCES}
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
        
        rows += f"""<tr class="{'ok' if r['file_ok'] else 'fail'}">
            <td>{icon} {r['source']}</td>
            <td>{tag}</td>
            <td class="status-cell">{r['status'] if r['status'] else '-'}</td>
            <td>{r['size'] if r['size'] > 0 else '-'} B</td>
            <td>{extra}</td>
            <td>{bar}</td>
        </tr>\n"""
    
    valid_rates = [r["channel_rate"] for r in ext_results if r.get("channel_rate") is not None]
    avg_cr = sum(valid_rates) / max(len(valid_rates), 1)
    
    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>{BRAND_NAME} - 健康报告</title>
<style>
body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; background: #f8f9fa; color: #333; }}
h1 {{ text-align: center; color: {BRAND_NAME}; font-size: 2.5em; margin-bottom: 10px; text-shadow: 1px 1px 2px rgba(0,0,0,0.1); }}
.summary {{ display: flex; gap: 20px; margin: 30px 0; flex-wrap: wrap; justify-content: center; }}
.card {{ background: white; border-radius: 12px; padding: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); flex: 1; min-width: 200px; text-align: center; }}
.big {{ font-size: 2.5em; font-weight: bold; color: #4a90d9; }}
table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #eee; }}
th {{ background: {BRAND_NAME}; color: white; }}
tr.fail td {{ background-color: #fff5f5; }}
.updated {{ text-align: center; color: #666; font-size: 0.9em; }}
</style>
</head>
<body>
<h1>📺 {BRAND_NAME}</h1>
<p class="updated">{timestamp} | 系统状态: {'✅ 运行良好' if ext_ok == len(ext_results) else '⚠️ 有源不可用'}</p>
<div class="summary">
<div class="card"><div class="big">{ext_ok}/{len(ext_results)}</div><div>外部源可用</div></div>
<div class="card"><div class="big">{avg_cr:.0f}%</div><div>抽样平均可用率</div></div>
<div class="card"><div class="big" style="font-size:1.5em">{round(elapsed)}s</div><div>检测耗时</div></div>
</div>
<table>
<thead><tr><th style="width:30%">来源</th><th style="width:10%">类型</th><th style="width:10%">状态码</th><th style="width:15%">大小</th><th style="width:20%">抽样情况</th><th style="width:15%">可用率</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</body>
</html>"""
    
    outpath = os.path.join(BASE_DIR, "health_report.html")
    with open(outpath, 'w', encoding='utf-8') as f:
        f.write(html)
    
    print("\n" + "=" * 60)
    print(f"{BRAND_NAME} | IPTV HEALTH MONITOR v4 SUMMARY")
    print("=" * 60)
    print(f"Total sources:    {len(results)}")
    print(f"External sources: {ext_ok}/{len(ext_results)} working")
    print(f"Avg channel rate: {avg_cr:.0f}%")
    print(f"Elapsed:          {elapsed:.1f}s")
    print()
    for r in results:
        ch = ""
        if r.get("channel_rate") is not None:
            ch = f" | 📡 {r['sample_ok']}/{r['sample_total']} ({r['channel_rate']}%)"
        icon = "✅" if r["file_ok"] else "❌"
        print(f"{icon} {r['source']:<25} HTTP {r['status']:>3} | {r['channels']} chs|{ch}")
    print(f"\n📊 Report: http://207.246.102.108/health_report.html")
    print(f"📄 JSON:   {json_path}")


if __name__ == "__main__":
    main()
