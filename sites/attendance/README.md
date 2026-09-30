# StarClub 成员出勤平台（sites/attendance）

星社成员出勤平台：支持成员登记、每日出勤登记、补充登记、管理员审核与出勤排名。

## 功能

- 成员认证：登记/登录/登出（`routes/auth.py`），会话过期可配置
- 每日出勤：限时登记（`routes/attendance.py`），支持 IP 网段白名单
- 补充登记与审核：管理员审核补充登记申请（`routes/management.py`）
- 后台管理：用户管理、出勤记录、系统设置
- 邮件通知：SMTP 定时提醒（`services/scheduler.py`）
- 出勤排名：`services/ranking.py` 统计与展示

## 技术栈

- Flask 3.0（应用工厂模式）
- SQLite（`db.py` 初始化，数据本地持久化）
- SMTP（邮件提醒，可选）
- 前端：原生 HTML/CSS/JS，`static/` 本地资源

## 目录结构

```
attendance/
├── app.py                 # 入口（Flask 应用工厂）
├── config.py              # 配置加载（config.json + 环境变量）
├── config.example.json    # 配置示例
├── db.py                  # 数据库初始化与系统配置
├── models.py              # 数据模型
├── email_service.py       # 邮件服务
├── tool_func.py           # 工具函数
├── routes/
│   ├── attendance.py      # 出勤登记
│   ├── auth.py            # 认证
│   └── management.py      # 后台管理
├── services/
│   ├── ranking.py         # 排名统计
│   └── scheduler.py       # 定时任务
├── requirements.txt       # Python 依赖
├── static/                # 静态资源
└── templates/             # Jinja2 模板
```

## 配置

复制配置示例并修改：

```bash
cd sites/attendance
cp config.example.json config.json
```

关键字段：

| 字段 | 说明 |
| --- | --- |
| `port` | 监听端口，默认 `10242` |
| `session_expire_seconds` | 会话有效期（秒） |
| `attendance.start_time` / `end_time` | 每日出勤时间段 |
| `attendance.interval_seconds` | 出勤登记间隔 |
| `attendance.reminder_minutes` | 提醒提前量（配合邮件） |
| `allowed_ip_ranges` | 出勤 IP 白名单（CIDR / 通配符示例：`192.168.0.0/24`） |
| `email.enabled` | 是否启用邮件提醒（需配置 SMTP 参数） |

## 启动

```bash
cd sites/attendance
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

生产环境由 systemd 托管（`deploy/systemd/user/starclub-attendance.service`），Nginx 反代见 `nginx/conf/conf.d/04-attendance.conf`。

## 依赖

见 `requirements.txt`：Flask==3.0.0、requests==2.31.0。
