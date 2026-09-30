# StarClub 官网（sites/web）

星社（StarClub）社团公开官网，纯静态站点，由 Nginx 直接托管，无需 Python 运行环境。

## 功能

- 首页 `index.html`：社团简介、最新动态入口
- 关于页 `about.html`：社团介绍与信息
- 共创页 `activities.html`：共创时间线
- 成员页 `members.html`：社团成员与指导老师展示
- 资源页 `resources.html`：学习资源链接（智慧社团/创新实践等）
- 加入页 `join.html`：加入星社流程与报名入口
- 联系页 `contact.html`：联系方式与位置

## 技术栈

- 原生 HTML5 / CSS3 / JavaScript（无构建步骤）
- 样式：`css/style.css`、`css/responsive.css`
- 脚本：`js/main.js`
- 图标：Font Awesome 6.4.0（CDN：`cdnjs.cloudflare.com`）
- 数据：`static/` 与 `uploads/` 下的本地资源

## 目录结构

```
web/
├── *.html                  # 顶层页面
├── css/                    # 全局样式
├── js/                     # 全局脚本
├── static/                 # 站点静态资源（logo 等）
├── uploads/                # 上传/媒体资源
```

## 配置

无配置文件。页面中的示例链接（如 `https://www.starclub.example.com`、`https://github.com/AnyaWantsStars/StarClub`）可按需替换为实际地址。

## 启动

将本目录作为站点根目录交给 Nginx 托管即可，参考仓库根 `nginx/conf/conf.d/01-website.conf`：

```nginx
server {
    listen 80;
    server_name www.starclub.example.com;
    root /home/starclub/StarClub/sites/web;
    index index.html;
}
```

## 依赖

- Nginx（或其他任意静态文件服务器）
- 无需 Python 依赖
