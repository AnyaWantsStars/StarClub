# StarClub 服务门户（sites/service）

星社服务门户：基于 NextCloud OAuth2 的单点登录（SSO）入口，提供 JWT 签发/校验、子服务托管与后台用户/服务管理。

## 功能

- OAuth2 登录：对接 NextCloud OAuth2 身份提供方（`/login`、`/oauth/callback`、`/logout`）
- JWT 签发与校验：`/api/jwt/sign`、`/api/jwt/verify`、`/api/permission/check`
- 子服务托管：`/service/<embed_path>` 代理内嵌子服务
- 后台管理：`/admin` 用户管理、服务管理、模块管理与系统设置（`/api/admin/*`、`/api/users/*`）
- 健康检查：`/api/health`

## 技术栈

- Flask 3.0
- PyJWT 2.8.0（JWT 签发与校验）
- requests（OAuth 回调与上游 API）
- 前端：原生 HTML/CSS/JS

## 目录结构

```
service/
├── app.py                 # 主应用（门户 + 后台 + API）
├── sub_service.py         # 子服务托管示例应用
├── jwt_utils.py           # JWT 工具
├── config.py              # 配置加载（config.json + 环境变量）
├── config.example.json    # 配置示例
├── requirements.txt       # Python 依赖
├── static/                # 静态资源
└── templates/             # Jinja2 模板
```

## 配置

复制配置示例并修改：

```bash
cd sites/service
cp config.example.json config.json
```

关键字段：

| 字段 | 说明 |
| --- | --- |
| `port` | 监听端口，默认 `10241` |
| `secret_key` | JWT/会话密钥，留空则自动生成（`data/.secret_key`） |
| `oauth.enabled` | 是否启用 OAuth2 登录 |
| `oauth.client_id` / `oauth.client_secret` | NextCloud OAuth 客户端凭据 |
| `oauth.redirect_uri` / `authorize_url` / `token_url` | OAuth 端点地址（示例：`id.starclub.example.com`） |

> 生产环境请通过环境变量注入 `OAUTH_CLIENT_ID` / `OAUTH_CLIENT_SECRET` 等密钥，避免写入配置文件。

## 启动

```bash
cd sites/service
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
python3 app.py 10241
```

生产环境由 systemd 托管（`deploy/systemd/user/starclub-service.service`），Nginx 反代见 `nginx/conf/conf.d/03-service.conf`。

## 依赖

见 `requirements.txt`：Flask==3.0.0、PyJWT==2.8.0、requests==2.31.0。
