# IPTV Platform / IPTV 直播源站平台

[English](#english) | [中文](#中文)

---

## 中文

自建 IPTV 直播源站 + TVBox 仓库自动化平台。自动采集、验证、分类国内外直播频道，生成 TVBox 多仓配置，附带健康检查与自动补种。

### ✨ 功能特性

- 📺 **IPTV 直播源站**：自动采集、验证、分类国内外直播频道（央视/卫视/地方台/港澳台/国际）
- 📦 **TVBox 仓库**：自动生成多仓 `repo.json`，内置 26+ 点播线路，每 12 小时自动测试可用性
- 🔍 **健康检查**：自动检测各源可用性，生成可视化健康报告
- 🌱 **自动补种**：定时从公开源补充失效/新增频道
- ✅ **两级验证**：国际频道严格内容验证（防 CDN 假 200），国内频道宽松验证（防防盗链误杀）

### 📁 目录结构

```
/opt/iptv/
├── scripts/                  # 核心脚本
│   ├── collect.py            # 频道采集（每6h）
│   ├── collect_categorized.py# 采集+分类+生成 m3u/index.html
│   ├── auto_supplement.py    # 失效频道补种（每天3:30）
│   ├── update_repo_v4_server.py # TVBox 仓库更新+线路可用性测试（每12h）
│   ├── health_checker.py     # 健康检查器（每12h，生成 health_report.html）
│   └── verify_repo_strict.py # 仓库严格校验
├── tvbox/                    # TVBox 配置产物
│   ├── repo.json             # 多仓地址（推荐）
│   └── config.json           # 单线路配置
├── m3u/                      # 生成的直播源文件（不入库，脚本自动生成）
├── txt/                      # TXT 格式直播源（不入库）
├── index.html                # 站点首页
└── health_report.html        # 健康检查报告
```

### 🚀 部署与配置方法

```bash
# 1. 依赖：Python 3.8+ / nginx / git
apt install python3 nginx git -y

# 2. 创建目录
mkdir -p /opt/iptv/{scripts,m3u,txt,tvbox,logs,reports}

# 3. 拷贝 scripts/ 与 tvbox/ 到服务器后，替换配置中的 IP 占位符：
#    ⚠️ 重要：将代码中所有 YOUR_SERVER_IP 替换为你的服务器 IP（或域名）
sed -i 's/YOUR_SERVER_IP/你的服务器IP/g' /opt/iptv/scripts/*.py /opt/iptv/tvbox/*.json /opt/iptv/index.html

# 4. 配置 nginx 将 /opt/iptv 目录暴露为站点根目录
#    示例（/etc/nginx/sites-enabled/iptv）：
#    server {
#        listen 80;
#        server_name _;
#        root /opt/iptv;
#        location / { try_files $uri $uri/ =404; }
#    }
systemctl reload nginx

# 5. 首次初始化：先手工跑一次采集脚本生成基础 m3u
cd /opt/iptv/scripts
python3 collect.py
python3 collect_categorized.py
python3 update_repo_v4_server.py
```

### ⏰ 定时任务（crontab，服务器时区 UTC）

```cron
# 采集+分类（每6小时）
0 */6 * * * cd /opt/iptv/scripts && python3 collect_categorized.py >> /opt/iptv/logs/collect.log 2>&1
# TVBox 仓库更新（每12小时）
0 */12 * * * cd /opt/iptv/scripts && python3 update_repo_v4_server.py >> /opt/iptv/logs/tvbox_test.log 2>&1
# 健康检查（每12小时）
0 */12 * * * cd /opt/iptv/scripts && python3 health_checker.py --quick >> /opt/iptv/logs/health_check.log 2>&1
# 频道补种（每天3:30）
30 3 * * * cd /opt/iptv/scripts && python3 auto_supplement.py >> /opt/iptv/logs/auto_supplement.log 2>&1
```

### 🔗 关键地址（部署后）

| 资源 | 地址 |
|---|---|
| TVBox 多仓 | `http://<服务器IP>/tvbox/repo.json` |
| TVBox 单线路 | `http://<服务器IP>/tvbox/config.json` |
| 站点首页 | `http://<服务器IP>/index.html` |
| 健康报告 | `http://<服务器IP>/health_report.html` |
| 直播总源 | `http://<服务器IP>/m3u/all.m3u` |
| 国内精简 | `http://<服务器IP>/m3u/cn.m3u` |

### ⚠️ 安全提示

- 仓库代码不含真实服务器地址（统一为 `YOUR_SERVER_IP` 占位符），部署前请自行替换
- 直播源版权归各源站所有，请遵守当地法律法规

### ❤️ 捐赠

如果这个项目对你有帮助，欢迎请我喝杯咖啡 ☕

**PayPal：** `paypal:xue1515@sina.com`

### 📜 许可

仅供个人学习与技术交流使用。

---

## English

Self-hosted IPTV live source site + TVBox repository automation platform. Automatically collects, validates, and categorizes live TV channels, generates TVBox multi-repo configs, with health checks and auto-supplement.

### ✨ Features

- 📺 **IPTV Live Site**: Auto collect, validate & categorize channels (CCTV / Satellite / Local / HK-TW-MO / International)
- 📦 **TVBox Repository**: Auto-generate `repo.json` with 26+ VOD lines, availability tested every 12h
- 🔍 **Health Check**: Detect source availability and generate visual health reports
- 🌱 **Auto Supplement**: Periodically replenish dead/new channels from public sources
- ✅ **Two-level validation**: Strict content check for international channels (prevents fake HTTP 200 HTML), lenient check for domestic channels (avoids anti-hotlink false positives)

### 🚀 Deployment & Configuration

```bash
# 1. Dependencies: Python 3.8+ / nginx / git
apt install python3 nginx git -y

# 2. Create directories
mkdir -p /opt/iptv/{scripts,m3u,txt,tvbox,logs,reports}

# 3. Copy scripts/ and tvbox/ to your server, then replace the IP placeholder:
#    ⚠️ Important: replace ALL YOUR_SERVER_IP with your server IP (or domain)
sed -i 's/YOUR_SERVER_IP/your-server-ip/g' /opt/iptv/scripts/*.py /opt/iptv/tvbox/*.json /opt/iptv/index.html

# 4. Configure nginx to expose /opt/iptv as web root
#    Example (/etc/nginx/sites-enabled/iptv):
#    server {
#        listen 80;
#        server_name _;
#        root /opt/iptv;
#        location / { try_files $uri $uri/ =404; }
#    }
systemctl reload nginx

# 5. First run: manually run collection scripts to generate base m3u
cd /opt/iptv/scripts
python3 collect.py
python3 collect_categorized.py
python3 update_repo_v4_server.py
```

### ⏰ Cron Jobs (server TZ = UTC)

```cron
# Collect + categorize (every 6h)
0 */6 * * * cd /opt/iptv/scripts && python3 collect_categorized.py >> /opt/iptv/logs/collect.log 2>&1
# TVBox repo update (every 12h)
0 */12 * * * cd /opt/iptv/scripts && python3 update_repo_v4_server.py >> /opt/iptv/logs/tvbox_test.log 2>&1
# Health check (every 12h)
0 */12 * * * cd /opt/iptv/scripts && python3 health_checker.py --quick >> /opt/iptv/logs/health_check.log 2>&1
# Channel supplement (daily 03:30)
30 3 * * * cd /opt/iptv/scripts && python3 auto_supplement.py >> /opt/iptv/logs/auto_supplement.log 2>&1
```

### 🔗 Key URLs (after deployment)

| Resource | URL |
|---|---|
| TVBox multi-repo | `http://<server-ip>/tvbox/repo.json` |
| TVBox single config | `http://<server-ip>/tvbox/config.json` |
| Home page | `http://<server-ip>/index.html` |
| Health report | `http://<server-ip>/health_report.html` |
| All channels | `http://<server-ip>/m3u/all.m3u` |
| China channels | `http://<server-ip>/m3u/cn.m3u` |

### ⚠️ Security Notes

- The repo contains NO real server address (all replaced with `YOUR_SERVER_IP` placeholder); replace before deployment
- Live source copyrights belong to their respective sources; comply with local laws

### ❤️ Donate

If this project helps you, feel free to buy me a coffee ☕

**PayPal:** `paypal:xue1515@sina.com`

### 📜 License

For personal learning and technical exchange only.
