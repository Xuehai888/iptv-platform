# 天天电视 IPTV 平台 (Everyday TV Platform)

自建 IPTV 直播源站 + TVBox 仓库自动化平台，部署于 Vultr 服务器。

## ✨ 功能特性

- 📺 **IPTV 直播源站**：自动采集、验证、分类国内外直播频道（央视/卫视/地方台/港澳台/国际/成人）
- 📦 **TVBox 仓库**：自动生成多仓 `repo.json`，内置 28+ 点播线路（含成人点播），每 6 小时自动测试可用性
- 🔍 **健康检查**：自动检测各源可用性，生成可视化健康报告
- 🌱 **自动补种**：定时从公开源补充失效/新增频道
- 🔞 **成人频道**：独立成人直播源 `adult.m3u`（776 频道）与成人点播线路，每天自动重建
- 🏷️ **品牌化**：所有线路/分组统一"天天电视"品牌命名

## 📁 目录结构

```
/opt/iptv/
├── scripts/                  # 核心脚本
│   ├── collect.py            # 频道采集（每6h）
│   ├── collect_categorized.py# 采集+分类+生成 m3u/index.html
│   ├── auto_supplement.py    # 失效频道补种（每天3:30）
│   ├── update_repo_v4_server.py # TVBox 仓库更新+线路可用性测试（每12h）
│   ├── health_checker.py     # 健康检查器（每12h，生成 health_report.html）
│   ├── gen_adult_m3u.py      # 成人直播源重建（每天3:30）
│   └── brand_m3u_groups.py   # m3u 分组品牌化
├── tvbox/                    # TVBox 配置产物
│   ├── repo.json             # 多仓地址（推荐）
│   └── config.json           # 单线路配置
├── m3u/                      # 生成的直播源文件（不入库，脚本自动生成）
├── txt/                      # TXT 格式直播源（不入库）
├── index.html                # 站点首页
└── health_report.html        # 健康检查报告
```

## 🚀 部署

```bash
# 依赖：Python 3.8+ / nginx / git
apt install python3 nginx git -y

# 目录
mkdir -p /opt/iptv/{scripts,m3u,txt,tvbox,logs,reports}
# 拷贝 scripts/ 与 tvbox/ 到服务器后：
cd /opt/iptv/scripts
# 首次初始化：先手工跑一次 collect.py 生成基础 m3u
python3 collect.py
```

### 定时任务（crontab，服务器时区 UTC）

```cron
# 采集+分类（每6小时）
0 */6 * * * cd /opt/iptv/scripts && python3 collect_categorized.py >> /opt/iptv/logs/collect.log 2>&1
# TVBox 仓库更新（每12小时）
0 */12 * * * cd /opt/iptv/scripts && python3 update_repo_v4_server.py >> /opt/iptv/logs/tvbox_test.log 2>&1
# 健康检查（每12小时）
0 */12 * * * cd /opt/iptv/scripts && python3 health_checker.py --quick >> /opt/iptv/logs/health_check.log 2>&1
# 频道补种（每天3:30）
30 3 * * * cd /opt/iptv/scripts && python3 auto_supplement.py >> /opt/iptv/logs/auto_supplement.log 2>&1
# 成人直播源重建（每天3:30）
30 3 * * * cd /opt/iptv/scripts && python3 gen_adult_m3u.py >> /opt/iptv/logs/gen_adult.log 2>&1
```

## 🔗 关键地址（部署后）

| 资源 | 地址 |
|---|---|
| TVBox 多仓 | `http://<服务器IP>/tvbox/repo.json` |
| TVBox 单线路 | `http://<服务器IP>/tvbox/config.json` |
| 站点首页 | `http://<服务器IP>/index.html` |
| 健康报告 | `http://<服务器IP>/health_report.html` |
| 直播总源 | `http://<服务器IP>/m3u/all.m3u` |
| 国内精简 | `http://<服务器IP>/m3u/cn.m3u` |
| 成人直播 | `http://<服务器IP>/m3u/adult.m3u` |

## 📜 许可

仅供个人学习与技术交流使用。直播源版权归各源站所有，请遵守当地法律法规。
