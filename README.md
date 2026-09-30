# StarClub（星社）

**Version** v0.9（归档预览）｜ **安全状态** [不满足公网生产部署要求](./SECURITY_REVIEW.md) ｜ **Repo** [github.com/AnyaWantsStars/StarClub](https://github.com/AnyaWantsStars/StarClub)

> [!CAUTION]
> 本项目已停止维护，未修复的安全问题包括未认证后台写接口、任意文件读取/写入、默认会话密钥和私有服务越权。**禁止直接部署到公网，禁止用于真实成员、考勤或 OAuth 数据。** 完整评估见 [SECURITY_REVIEW.md](./SECURITY_REVIEW.md)。

> 星社（StarClub）数字创新社团的开源项目集，面向高校数字化创新场景提供可独立运行的一体化站点解决方案：公开官网、内容管理后台、OAuth 单点登录服务门户与成员出勤平台。本仓库以 AGPL-3.0 协议开源，代码可独立运行，但当前版本不满足公网生产发布条件。

## 为什么是 v0.9

版本停在 0.9，不是因为差一点就到 1.0，而是因为它已经烂尾了。

从功能上讲，它目前是完整可用的：官网、内容管理后台、服务门户、成员出勤四个子项目都能独立部署运行。但从开发者角度，想做的事还远没有做完——界面风格还没有统一、交互细节还很粗糙，代码里也还有大量可以进一步优化和改进的地方。这些"还有很多很多"的想法最终都没有一一兑现，于是版本号停在了 0.9，而不是 1.0。坦白说，这个项目后续大概率会继续烂尾下去。

在当今 AI 时代，这个项目本身也是 AI 时代的产物——它诞生于 AI 辅助开发盛行的时期，也受限于当时的需求场景。它的存在意义，或许更多是为了纪念：纪念一段认真投入过的时光，和一个搭起来了、却没能打磨到"完美"的数字角落。如果你恰好看到它，愿意把它 clone 下去继续折腾，那就是它最好的归宿。

## 目录结构

```
StarClub/
├── sites/                    # 四个子项目
│   ├── web/                  # 官网（纯静态站点）
│   ├── web-admin/            # 官网内容管理后台（Flask）
│   ├── service/              # 服务门户（Flask + OAuth SSO）
│   └── attendance/           # 成员出勤平台（Flask）
├── deploy/
│   ├── README.md             # 部署说明（systemd 方式）
│   └── systemd/              # systemd 单元
│       ├── system/starclub-nginx.service
│       └── user/*.service    # web-admin / service / attendance
├── nginx/                    # Nginx 反向代理配置（conf / html 错误页）
├── LICENSE                   # GNU Affero General Public License v3.0
└── .gitignore
```

## 子项目一览

| 子项目 | 目录 | 技术栈 | 端口 | 说明 |
| --- | --- | --- | --- | --- |
| 官网 | `sites/web` | 原生 HTML/CSS/JS（静态） | Nginx 直接托管 | 社团公开主页、共创、成员、资源页 |
| 内容管理后台 | `sites/web-admin` | Flask + Jinja2 + Markdown | 10240 | 站点内容/成员/共创/资源的管理与导出 |
| 服务门户 | `sites/service` | Flask + PyJWT + OAuth2 | 10241 | 基于 NextCloud OAuth 的社团服务入口与子服务托管 |
| 成员出勤 | `sites/attendance` | Flask + SQLite + SMTP | 10242 | 成员出勤登记、活动签到与后台统计 |

## 部署方式

推荐使用仓库内提供的 systemd 单元 + Nginx 反向代理部署，目标机路径约定为 `/home/starclub/StarClub`。

### 1. 安装依赖

```bash
cd /home/starclub/StarClub/sites/web-admin
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt

cd ../../service && . ../web-admin/.venv/bin/activate
pip install -r requirements.txt

cd ../attendance && . ../web-admin/.venv/bin/activate
pip install -r requirements.txt
```

> `sites/web` 为纯静态站点，无需 Python 依赖。

### 2. 准备配置

```bash
cd sites/service && cp config.example.json config.json   # 修改端口、OAuth 参数
cd ../attendance && cp config.example.json config.json   # 修改端口、邮件参数
cd ../web-admin                                          # 无需额外配置，密钥自动生成
```

各子项目配置字段说明见各目录内 `README.md`。

### 3. 启动服务（systemd）

```bash
# 系统级（Nginx）
sudo cp deploy/systemd/system/starclub-nginx.service /etc/systemd/system/
sudo systemctl enable --now starclub-nginx

# 用户级（web-admin / service / attendance）
mkdir -p ~/.config/systemd/user
cp deploy/systemd/user/*.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now starclub-web-admin starclub-service starclub-attendance
```

### 4. Nginx 站点配置

`nginx/conf/conf.d/` 下按序提供：

| 配置文件 | 作用 |
| --- | --- |
| `00-default.conf` | 默认站点与错误页 |
| `01-website.conf` | 官网（静态） |
| `02-manage.conf` | web-admin 管理后台 |
| `03-service.conf` | 服务门户 |
| `04-attendance.conf` | 成员出勤 |

仓库内 `nginx/` 目录即 Nginx 运行前缀（prefix），`nginx.conf` 按相对路径引用 `conf.d/*.conf` 与 `html/`。可用 `deploy/systemd/system/starclub-nginx.service` 直接以该目录为前缀部署（按实际路径替换），或手动将 `nginx/` 作为 prefix 配置到系统 Nginx 后启用 `conf.d/` 下站点，并替换配置内的占位域名。

## 依赖

- Python 3.9+
- Flask 3.0 / Jinja2 / PyJWT / requests / markdown
- Nginx（反向代理与静态托管）
- Docker（可选，用于 NextCloud + MySQL，OAuth 身份提供方）
- 前端资源：图标使用 Font Awesome CDN（`cdnjs.cloudflare.com`），其余资源本地化

完整依赖清单见各子项目 `requirements.txt`。

## 许可

[GNU Affero General Public License v3.0](./LICENSE)，Copyright (c) 2026 StarClub。

## 致谢

感谢所有为星社做出贡献的成员与历届社团骨干；感谢 NextCloud 提供的开源协作平台；感谢开源生态中的 Flask、Nginx 等项目。
