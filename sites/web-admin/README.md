# StarClub 内容管理后台（sites/web-admin）

星社官网的内容管理后台，基于 Flask 提供站点内容（成员、共创、资源、导航等）的可视化管理与数据导出能力。

## 功能

- 内容管理：站点信息、成员、共创、资源、导航/页脚等数据的增删改查
- 数据持久化：统一写入 `data/site-data.json`
- 数据导出：`exporter.py` 提供站点数据导出能力
- 模板渲染：`templates/` 为 Flask 渲染模板，`*.html` 为静态落地页

## 技术栈

- Flask 3.0 + Jinja2 + Werkzeug
- Markdown 渲染（markdown 库）
- 原生 HTML/CSS/JS 前端
- 本地依赖：`Sortable.min.js`（拖拽排序）、Font Awesome CDN

## 目录结构

```
web-admin/
├── admin.py               # 主入口（Flask 应用）
├── exporter.py            # 数据导出脚本
├── requirements.txt       # Python 依赖
├── about.html activities.html contact.html  # 静态落地页
├── index.html join.html members.html resources.html  # 静态落地页
├── admin/                 # 管理界面资源（JS/HTML）
├── css/ js/ static/       # 前端资源
├── data/
│   └── site-data.json     # 站点数据（内容源）
├── templates/             # Flask 模板
├── detail-template.html   # 详情页模板
└── uploads/               # 上传媒体
```

## 配置

默认监听 `10240` 端口。运行后首次启动自动生成 `data/.secret_key` 用于会话签名，无需手工配置。

如需调整端口，在 `deploy/systemd/user/starclub-web-admin.service` 的 `ExecStart` 中修改：

```ini
ExecStart=/usr/bin/python3 /home/starclub/StarClub/sites/web-admin/admin.py 10240
```

## 启动

```bash
cd sites/web-admin
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 admin.py 10240
```

生产环境由 Nginx 反代（`nginx/conf/conf.d/02-manage.conf`）与 systemd 托管。

## 依赖

见 `requirements.txt`：Flask==3.0.0、requests==2.31.0、markdown==3.5.1、Jinja2==3.1.2、Werkzeug==3.0.1。
