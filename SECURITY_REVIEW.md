# StarClub v0.9 安全评估与渗透测试报告

**报告版本**：1.0
**评估日期**：2026-09-29 至 2026-09-30
**目标版本**：StarClub v0.9
**报告性质**：AI 辅助源码审计与非破坏性动态验证
**总体结论**：**No-Go，禁止直接部署到公网或用于真实用户数据**

## 重要声明

本报告不是第三方认证、合规审计或正式安全背书。评估人员未获得真实生产环境、NextCloud 实例、OAuth 凭据或线上用户数据。

本次验证采用隔离副本和临时目录，没有修改或删除项目工作区中的真实业务数据，没有对真实服务实施拒绝服务、密码爆破、横向移动或其他高影响测试。

本项目当前处于停止维护状态。报告中的问题默认保持 **Open**，不代表已经修复。若要公开源码，仓库必须显著标明“仅用于展示、学习和技术存档，不得直接用于公网生产环境”。

## 执行摘要

StarClub v0.9 的功能结构较完整，包含静态官网、内容管理后台、OAuth 服务门户和成员出勤平台。但安全边界和发布工程尚未达到生产标准，存在可被未认证远程访问者直接利用的严重问题。

风险统计如下：

| 等级 | 数量 | 说明 |
| --- | ---: | --- |
| Critical | 4 | 可导致未授权内容修改、敏感文件读取、任意文件写入/删除、会话伪造 |
| High | 5 | 私有服务越权、存储型 XSS、禁用账号仍可访问、危险依赖、部署链不可用 |
| Medium | 3 | 缺少自动化测试、演示数据直接发布、生产运行方式不符合要求 |
| Low | 1 | 示例子服务无法正常导入运行 |

核心判断：

- 未登录访问者可以调用管理后台的部分写接口和导出接口。
- 未登录访问者可以读取不应公开的源码和运行时 JSON 文件。
- 上传分类和文件路径未进行规范化校验，可以通过 `..` 越出预期目录。
- `web-admin` 在未配置环境变量时使用公开固定会话密钥。
- 私有服务嵌入路由绕过门户可见性控制。
- 被禁用的出勤平台账号不会立即失去已有权限。
- 固定的 Python 依赖版本存在公开安全公告。
- 当前 systemd 和 Nginx 资源配置不能按 README 从干净仓库直接启动。

## 评估范围

### 范围内

- `sites/web-admin`
- `sites/service`
- `sites/attendance`
- `sites/web` 中的公开静态内容
- `nginx` 反向代理配置
- `deploy/systemd` 服务配置
- Python 依赖清单和 OAuth、JWT、会话、文件上传相关逻辑

### 范围外

- 真实 NextCloud 或 OAuth 身份提供方
- TLS 证书和真实域名
- 生产服务器防火墙、云安全组和主机加固
- 大规模压力测试、拒绝服务测试和供应链完整性验证
- 第三方 JavaScript 的完整审计
- 移动端、浏览器扩展和无障碍专项测试

## 测试方法

本次评估使用以下方法：

1. 对 Python、系统服务和 Nginx 配置进行静态源码审计。
2. 使用 Flask 测试客户端在隔离临时副本中验证认证、越权和路径处理。
3. 对关键路由、权限装饰器和文件操作进行人工数据流分析。
4. 使用 `py_compile` 检查 Python 语法。
5. 使用 OSV 查询固定依赖版本的安全公告。
6. 核对 README、systemd、Nginx 与应用代码之间的部署一致性。

动态验证环境为 Windows、Python 3.12.5、Flask 3.1.3。项目固定版本为 Flask 3.0.0 等版本。动态测试结论可能受此版本差异影响，但本报告中的认证缺失和路径处理问题均可由源码直接确认。

Nginx 和 systemd 未在 Linux 主机上实际启动，相关结论来自静态配置检查和目录完整性检查。

## 风险汇总

| ID | 等级 | 问题 | 状态 |
| --- | --- | --- | --- |
| SEC-001 | Critical | 管理后台写接口和导出接口缺少认证 | Open |
| SEC-002 | Critical | 未认证任意文件读取和敏感配置暴露 | Open |
| SEC-003 | Critical | 上传、重命名和删除路径可越界 | Open |
| SEC-004 | Critical | 固定默认会话密钥可被用于会话伪造 | Open |
| SEC-005 | High | 详情页内容可形成未认证存储型 XSS | Open |
| SEC-006 | High | 私有服务嵌入路由绕过可见性检查 | Open |
| SEC-007 | High | 禁用账号的现有会话和管理权限不失效 | Open |
| SEC-008 | High | 固定 Python 依赖存在公开安全公告 | Open |
| SEC-009 | High | 提供的 systemd 和 Nginx 部署链不可直接启动 | Open |
| SEC-010 | Medium | 缺少自动化测试、CI 和发布门禁 | Open |
| SEC-011 | Medium | 演示域名、示例邮箱和演示数据直接进入发布包 | Open |
| SEC-012 | Medium | 以 Flask 内置开发服务器承载生产流量 | Open |
| SEC-013 | Low | 示例子服务因错误配置导入而无法运行 | Open |

## 详细发现

### SEC-001：管理后台写接口和导出接口缺少认证

**等级**：Critical
**CWE**：CWE-306 Missing Authentication for Critical Function

**受影响位置**

- [`sites/web-admin/admin.py`](sites/web-admin/admin.py#L651)
- [`sites/web-admin/admin.py`](sites/web-admin/admin.py#L1183)
- [`sites/web-admin/admin.py`](sites/web-admin/admin.py#L1324)
- [`sites/web-admin/exporter.py`](sites/web-admin/exporter.py#L1051)
- [`sites/web-admin/exporter.py`](sites/web-admin/exporter.py#L1157)

**问题说明**

后台的数据保存、批量导入、文件上传、文件重命名、文件删除、详情页编辑和静态站点导出接口没有统一要求登录，也没有使用 `require_auth` 等鉴权装饰器。

Nginx 将 `manage.starclub.example.com` 的全部请求转发到该 Flask 应用，因此问题不仅是本地开发接口，而是部署后的公网管理入口。

**验证结果**

在隔离临时副本中，未建立任何登录会话时：

- `POST /api/save` 返回 `200`，并成功修改站点 JSON。
- `POST /api/files/upload` 返回 `200` 并写入文件。
- `POST /api/files/delete` 返回 `200` 并删除目标文件。
- `POST /api/export` 和 `GET /api/export/download` 没有认证检查。

**影响**

- 未认证远程访问者可篡改官网内容。
- 可上传、重命名或删除后台文件。
- 可触发导出、覆盖静态站点文件或下载完整站点包。
- 可与 SEC-002、SEC-003、SEC-005 组合形成更严重的远程破坏和内容注入。

**建议**

- 为所有写接口、导出接口和内部读取接口统一增加认证和授权。
- 采用默认拒绝的 `before_request` 白名单，而不是逐个补充装饰器。
- 对基于 Cookie 的管理请求增加 CSRF 防护。
- 将管理入口限制在可信网络、VPN 或额外身份网关之后。

### SEC-002：未认证任意文件读取和敏感配置暴露

**等级**：Critical
**CWE**：CWE-552 Files or Directories Accessible to External Parties

**受影响位置**

- [`sites/web-admin/admin.py`](sites/web-admin/admin.py#L563)
- [`sites/web-admin/admin.py`](sites/web-admin/admin.py#L580)

**问题说明**

通配路由 `/<path:filename>` 会把任意请求交给 `serve_file()`。该函数只对以 `admin/` 开头的路径检查登录状态，其他项目文件可以直接读取。

运行时 `data/allowed_users.json` 可能包含 `oauth_settings`，其中存在 NextCloud OAuth `client_secret`。该文件也位于可读取路径下。

**验证结果**

在隔离临时副本中：

- `GET /admin.py` 返回 `200` 和 Python 源码。
- `GET /data/allowed_users.json` 返回 `200`。
- 测试 JSON 中的伪 OAuth 密钥值可被未登录访问者读取。

**影响**

- 项目源码、运行数据和部分配置可被匿名下载。
- OAuth 客户端密钥一旦存在，可能被用于攻击身份提供方集成。
- 攻击者可获取内部路径、结构和管理逻辑，降低后续攻击成本。

**建议**

- 禁止使用项目根目录作为通用文件服务根。
- 仅开放明确白名单中的静态资源。
- 将认证相关 JSON、密钥和运行数据放到 Web 根目录之外。
- 使用 `send_from_directory()` 或受控静态目录提供文件。

### SEC-003：上传、重命名和删除路径可越界

**等级**：Critical
**CWE**：CWE-22 Path Traversal

**受影响位置**

- [`sites/web-admin/admin.py`](sites/web-admin/admin.py#L1183)
- [`sites/web-admin/admin.py`](sites/web-admin/admin.py#L1241)
- [`sites/web-admin/admin.py`](sites/web-admin/admin.py#L1292)
- [`sites/web-admin/admin.py`](sites/web-admin/admin.py#L1324)

**问题说明**

上传接口直接使用用户提交的 `category` 拼接目标目录，没有白名单或目录边界检查。

文件重命名和删除接口仅使用字符串前缀判断：

```python
full_path.startswith(os.path.join(SITE_ROOT, 'uploads'))
```

该判断没有先规范化路径，不能阻止 `uploads/../...` 形式的目录穿越，也不能可靠处理符号链接、Windows 大小写和同前缀兄弟目录。

**验证结果**

在隔离临时副本中：

- 上传分类使用 `../outside` 时返回 `200`，文件被写到 `uploads` 之外。
- 删除路径使用 `uploads/../victim.txt` 时返回 `200`，目录外文件被删除。

**影响**

- 未认证访问者可在应用目录范围内任意写入文件。
- 可删除或重命名应用文件。
- 与其他问题组合后可能覆盖模板、配置或静态站点文件。

**建议**

- 使用 `Path.resolve()` 和 `Path.is_relative_to()` 进行规范化边界检查。
- 上传分类必须使用固定白名单。
- 文件名由服务端重新生成，不接受客户端控制目录部分。
- 禁止跟随符号链接，并限制上传大小和文件类型。

### SEC-004：固定默认会话密钥可被用于会话伪造

**等级**：Critical
**CWE**：CWE-798 Use of Hard-coded Credentials

**受影响位置**

- [`sites/web-admin/admin.py`](sites/web-admin/admin.py#L21)
- [`deploy/systemd/user/starclub-web-admin.service`](deploy/systemd/user/starclub-web-admin.service#L11)

**问题说明**

`web-admin` 在没有 `SESSION_SECRET` 环境变量时使用公开常量：

```text
dev-secret-key-change-in-production
```

systemd 单元没有注入该环境变量，因此默认部署会使用公开密钥签发 Flask 会话 Cookie。

**验证方式**

通过源码和部署配置交叉检查确认。评审未生成伪造的真实生产 Cookie。

**影响**

- 攻击者可在知道密钥的情况下构造 Flask 会话。
- 当白名单中存在 `admin` 用户 ID 时，可尝试绕过 `admin/` 页面的登录检查。
- 还会放大 SEC-001 和 SEC-002 的破坏范围。

**建议**

- 启动时强制要求随机生成的 `SESSION_SECRET`。
- 未配置时直接拒绝启动，不使用默认密钥。
- 对密钥文件设置最小权限并从版本控制中排除。
- 轮换密钥后使所有现有会话失效。

### SEC-005：详情页内容可形成未认证存储型 XSS

**等级**：High
**CWE**：CWE-79 Improper Neutralization of Input During Web Page Generation

**受影响位置**

- [`sites/web-admin/admin.py`](sites/web-admin/admin.py#L1388)
- [`sites/web-admin/admin.py`](sites/web-admin/admin.py#L1653)
- [`sites/web-admin/exporter.py`](sites/web-admin/exporter.py)

**问题说明**

详情页支持 `html` 内容块，渲染时直接拼接原始 HTML。卡片链接、图片地址、视频地址、页脚链接和其他属性也没有统一转义或 URL 协议白名单。

由于详情页保存接口缺少认证，未登录访问者可以写入恶意 HTML，并在公开页面或管理后台中被渲染。

**影响**

- 可对官网访问者执行存储型脚本。
- 可在管理后台上下文执行操作或窃取会话数据。
- 可构造钓鱼内容、恶意跳转或页面篡改。

**建议**

- 富文本只允许经过严格白名单过滤的 HTML。
- 普通文本、链接和属性必须根据上下文转义。
- URL 仅允许 `http`、`https`、`mailto` 和可信相对路径。
- 在修复前关闭原始 HTML 内容块。

### SEC-006：私有服务嵌入路由绕过可见性检查

**等级**：High
**CWE**：CWE-862 Missing Authorization

**受影响位置**

- [`sites/service/app.py`](sites/service/app.py#L227)

**问题说明**

`/api/services` 会根据用户身份过滤服务和模块。但 `/service/<embed_path>` 只检查服务是否存在和是否启用嵌入，没有检查服务类型、模块类型、`visible_to` 或当前用户身份。

**验证结果**

在隔离临时副本中：

- 匿名访问 `/api/services` 返回 `0` 个服务。
- 同一匿名客户端直接访问私有服务的 `/service/private-path` 返回 `200`。
- 返回页面包含私有服务 URL。

**影响**

- 私有或内部服务的门户层访问控制可被绕过。
- 若目标子服务自身鉴权不足，可能导致数据或功能暴露。

**建议**

- 在嵌入路由中复用统一的可见性判断。
- 对私有服务同时校验当前用户、模块和 `visible_to`。
- 不依赖前端隐藏服务入口作为访问控制。

### SEC-007：禁用账号的现有会话和管理权限不失效

**等级**：High
**CWE**：CWE-613 Insufficient Session Expiration
**附加**：CWE-863 Incorrect Authorization

**受影响位置**

- [`sites/attendance/tool_func.py`](sites/attendance/tool_func.py#L62)
- [`sites/attendance/tool_func.py`](sites/attendance/tool_func.py#L108)

**问题说明**

出勤平台的 `get_current_user()` 找到 session 对应用户后直接返回，不检查 `disabled` 或 `locked` 状态。`admin_required` 只检查用户类型。

**验证结果**

在隔离临时副本中，将管理员设为 `disabled` 后保留原 session：

- `GET /api/attendance/rankings` 返回 `200`。
- `GET /api/management/users` 返回 `200` 并返回用户数据。

**影响**

- 被禁用或锁定的管理员、普通用户仍可在会话有效期内访问系统。
- 最高可保持 30 天默认会话有效期。
- 账号禁用不等同于权限撤销。

**建议**

- 每次请求读取用户状态并拒绝 `disabled` 和 `locked` 用户。
- 禁用账号时使其现有会话失效，并维护撤销列表或会话版本号。
- 管理权限检查必须同时要求账号状态正常。

### SEC-008：固定 Python 依赖存在公开安全公告

**等级**：High
**CWE**：CWE-1104 Use of Unmaintained Third-Party Components

**受影响位置**

- [`sites/web-admin/requirements.txt`](sites/web-admin/requirements.txt#L1)
- [`sites/service/requirements.txt`](sites/service/requirements.txt#L1)
- [`sites/attendance/requirements.txt`](sites/attendance/requirements.txt#L1)

**固定版本**

- Flask 3.0.0
- Jinja2 3.1.2
- Werkzeug 3.0.1
- requests 2.31.0
- Markdown 3.5.1
- PyJWT 2.8.0

**验证结果**

截至 2026-09-30，查询 OSV 后，上述固定版本均返回一个或多个公开安全公告。

| 包 | 当前固定版本 | 评估日最新稳定版本 | 公开公告示例 |
| --- | --- | --- | --- |
| Flask | 3.0.0 | 3.1.3 | CVE-2026-27205 |
| Jinja2 | 3.1.2 | 3.1.6 | CVE-2025-27516、CVE-2024-56201、CVE-2024-22195、CVE-2024-34064、CVE-2024-56326 |
| Werkzeug | 3.0.1 | 3.1.9 | CVE-2026-27199、CVE-2026-21860、CVE-2024-49766、CVE-2024-49767、CVE-2025-66221 |
| requests | 2.31.0 | 2.34.2 | CVE-2024-47081、CVE-2024-35195、CVE-2026-25645 |
| Markdown | 3.5.1 | 3.11 | CVE-2025-69534 |
| PyJWT | 2.8.0 | 2.15.1 | CVE-2026-32597、CVE-2026-48525、CVE-2026-48526 |

公告并不代表每个漏洞在当前用法中都可直接利用。例如本次代码显式限制 JWT 算法，部分 PyJWT 公告可能不可触达；Werkzeug 表单解析风险、Requests 重定向风险等则与当前上传和外部请求功能相关。

**影响**

- 可能受到依赖层拒绝服务、凭据泄漏、模板属性注入或解析异常影响。
- 停止更新会不断扩大已知漏洞暴露面。

**建议**

- 在归档版本中至少升级到无已知高危公告的兼容版本。
- 表中“最新稳定版本”仅代表评估日信息，升级后仍需执行兼容性测试。
- 生成锁文件和哈希，加入依赖审计。
- 若坚持不升级，必须在 README 中明确风险并提供隔离部署说明。

### SEC-009：提供的 systemd 和 Nginx 部署链不可直接启动

**等级**：High
**类别**：部署完整性、可用性

**受影响位置**

- [`deploy/systemd/user/starclub-web-admin.service`](deploy/systemd/user/starclub-web-admin.service#L11)
- [`deploy/systemd/user/starclub-service.service`](deploy/systemd/user/starclub-service.service#L11)
- [`deploy/systemd/user/starclub-attendance.service`](deploy/systemd/user/starclub-attendance.service#L11)
- [`deploy/systemd/system/starclub-nginx.service`](deploy/systemd/system/starclub-nginx.service#L11)
- [`nginx/conf/snippets/ssl-params.conf`](nginx/conf/snippets/ssl-params.conf#L2)

**问题说明**

- README 要求把 Python 依赖安装到虚拟环境，但 systemd 调用 `/usr/bin/python3`，不会使用该虚拟环境。
- systemd 调用 `nginx/sbin/nginx`，仓库中没有 `nginx/sbin/`。
- Nginx 使用 `nginx/logs/`，仓库中没有该目录。
- 配置引用 `nginx/ssl/fullchain.pem` 和 `privkey.pem`，仓库中没有证书目录或完整的证书准备步骤。
- 所有 Flask 服务都使用内置开发服务器。

**验证结果**

静态检查确认：

```text
nginx/sbin/nginx 不存在
nginx/logs 不存在
nginx/ssl 不存在
```

**影响**

- 按 README 操作无法从干净仓库直接启动。
- 服务可能依赖服务器预装包而被“偶然运行”，难以复现部署。
- Nginx 在证书或日志目录缺失时会启动失败。
- Flask 开发服务器不适合生产并发、超时和进程管理。

**建议**

- systemd 显式调用虚拟环境中的 WSGI 服务进程。
- Nginx 使用系统 `/usr/sbin/nginx` 或明确安装独立二进制。
- 创建并文档化日志、证书和权限准备步骤。
- 增加 `nginx -t`、systemd 启动和健康检查的发布验证。

### SEC-010：缺少自动化测试、CI 和发布门禁

**等级**：Medium
**CWE**：CWE-1059 Insufficient Examination and Testing

**问题说明**

仓库未发现测试目录、`pytest` 配置、CI 工作流、依赖审计或部署验证脚本。

**影响**

- 认证、越权和路径处理回归无法被发现。
- OAuth 状态校验、角色变更、考勤时间边界和文件导出缺少保障。
- 后续维护者容易重复引入同类问题。

**建议**

至少加入以下测试：

- 所有写接口未登录必须返回 `401` 或 `403`。
- 路径穿越、符号链接和上传分类白名单。
- 私有服务匿名访问和低权限用户访问。
- 禁用账号立即失效。
- OAuth 状态、回调、一次性兑换码和重放。
- 考勤签到、签退、举报、申诉和批量导入边界。

### SEC-011：演示域名、示例邮箱和演示数据直接进入发布包

**等级**：Medium
**类别**：发布内容、隐私和配置安全

**问题说明**

官网、站点数据、配置示例、前端模板和 Nginx 配置中存在大量 `example.com`、示例邮箱、演示成员、演示奖项和测试入口。

**影响**

- 公网发布后会产生失效链接和错误联系方式。
- 演示个人资料可能被误认为真实成员数据。
- 使用者可能把示例域名或密钥直接带入生产。

**建议**

- 在归档发布中明确标注所有内容和身份均为虚构演示数据。
- 把域名、邮箱、ICP 和外部链接集中到配置模板。
- 不在源码发布包中包含真实成员资料、邮箱或考勤数据。

### SEC-012：以 Flask 内置开发服务器承载生产流量

**等级**：Medium
**类别**：生产运行配置

**受影响位置**

- [`sites/service/app.py`](sites/service/app.py#L1105)
- [`sites/attendance/app.py`](sites/attendance/app.py#L75)
- [`sites/web-admin/admin.py`](sites/web-admin/admin.py#L1879)

**问题说明**

所有服务最终均调用 `app.run()`。Flask 内置服务器主要用于开发，不提供生产级进程管理、连接处理、超时控制和稳定工作者模型。

**影响**

- 并发和故障恢复能力有限。
- 多进程部署时，内存中的一次性兑换码和后台定时任务会失效或重复执行。
- 调试开关或代理配置错误时，可能暴露额外信息。

**建议**

- 使用 Gunicorn、uWSGI 或 Waitress。
- 一次性授权码改为 Redis、SQLite 或数据库事务存储。
- 定时任务从 Web 进程拆分为单一调度进程或 systemd timer。

### SEC-013：示例子服务因错误配置导入而无法运行

**等级**：Low
**CWE**：CWE-758 Reliance on Undefined, Unspecified, or Implementation-Defined Behavior

**受影响位置**

- [`sites/service/sub_service.py`](sites/service/sub_service.py#L10)

**问题说明**

`sub_service.py` 导入：

```python
from config import CONFIG
```

但 `sites/service/config.py` 只定义 `Config` 类，没有 `CONFIG` 对象。

**验证结果**

导入时抛出：

```text
ImportError: cannot import name 'CONFIG' from 'config'
```

**影响**

- 文档中的子服务示例无法直接运行。
- 降低项目作为参考实现的可信度。

**建议**

修正为现有配置接口，或从发布包中删除该失效示例。

## 修复优先级

如果未来恢复维护，建议按以下顺序处理：

1. 冻结公网部署，关闭管理后台外部访问。
2. 修复 SEC-001 至 SEC-004，这四个问题决定是否可安全接触真实环境。
3. 修复 SEC-005 至 SEC-007，补全授权、输入处理和账号撤销。
4. 重做 WSGI、systemd、Nginx 和密钥部署流程。
5. 升级依赖并加入锁文件、CI、安全测试和依赖审计。
6. 清理演示数据，明确发布范围和隐私责任。

## 发布建议

结合本项目不再大改的实际情况，建议公开方式如下：

- 将版本标记为 `v0.9-archived`、`pre-release` 或技术预览。
- README 首屏加入显眼的“不安全，禁止直接部署”声明。
- 随源码发布本报告，不声称已经达到生产质量。
- 不接收、保存或展示真实成员、考勤、OAuth 密钥或生产配置。
- 在 release notes 中明确列出四个 Critical 问题和未修复状态。
- 若只做展示，建议提供不可写入、无真实数据库连接的只读演示环境。

## 评估限制

- 未测试真实 NextCloud、邮件服务器、反向代理和公网网络。
- 未执行 DoS、暴力破解、供应链投毒或主机层渗透。
- 未验证所有第三方前端资源和 CDN。
- 动态测试版本与固定依赖版本不完全一致。
- 本报告不能证明不存在其他未发现问题。

## 快照哈希

以下 SHA-256 哈希用于标识本次评估对应的关键文件快照：

```text
3E0AF42EB2C4C0E6D019D9DFAC20EC6BD8A45C7B34056B384FBD916AE7248173  sites/web-admin/admin.py
248B78D9AB769D8F17C4EE774B02E017372E8F9953926B77D5665F48C14AA5F7  sites/web-admin/exporter.py
0A07926D4240291854308309721E7779F37051B376A624D036B83D60CCE9AC61  sites/service/app.py
C1CDE983710220C5F2CE4B139B65BCF2D2A68C163D7233469D3D0925E6280659  sites/attendance/tool_func.py
5876F74EA49D2249DD01E02464F74E6E93FA9D35CE3B2B3A08984F81816F9B23  deploy/systemd/user/starclub-web-admin.service
805B474678973C2854DA157EB0A801FA7CB20B5E8DFFF8A5C6C7A5C100D2B1AB  nginx/conf/snippets/ssl-params.conf
```

任何关键文件变化后，本报告都应对相应发现重新验证。
