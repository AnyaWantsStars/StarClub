# StarClub selected-service deployment

> 中文说明：本目录为 StarClub（星社）精选服务（service / attendance / web-admin 等）的部署说明，包含 systemd 单元清单、Nginx 反向代理与 iframe 安全策略，以及常用的部署、检查与重启命令。本文件采用英文编写，内容与根目录 README「部署方式」一节保持一致。

This release only manages:

- official website and Nginx
- website administration
- attendance
- service portal

This release does not include TLS certificates, application secrets, databases or user runtime data.

## systemd units

User-level units (in `systemd/user/`):

- starclub-service.service
- starclub-web-admin.service
- starclub-attendance.service

System-level unit (in `systemd/system/`):

- starclub-nginx.service

Inspect all managed services:

```bash
systemctl --user list-units 'starclub-*' --no-pager
systemctl status starclub-nginx.service --no-pager
```

Restart all managed services:

```bash
systemctl --user restart starclub-service starclub-web-admin starclub-attendance
sudo systemctl restart starclub-nginx
```

## Cross-subdomain iframe policy

Nginx removes upstream `X-Frame-Options` headers and applies:

```text
frame-ancestors 'self' https://starclub.example.com https://*.starclub.example.com;
```

This permits HTTPS pages under `starclub.example.com` and its subdomains to embed each other.
