#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
StarClub 网站管理工具 - 数据管理后端 v0.9 (Flask版)
支持 RESTful API + OAuth2认证 + 用户管理
运行方式: python admin.py
"""

import os
import json
import re
import datetime
import urllib.parse
import requests
import markdown as md
from functools import wraps
from flask import Flask, request, jsonify, Response, redirect, session

app = Flask(__name__, static_folder='.')
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['SECRET_KEY'] = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')

SITE_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(SITE_ROOT, 'data', 'site-data.json')
LOG_FILE = os.path.join(SITE_ROOT, 'data', 'operation-log.json')
ALLOWED_USERS_FILE = os.path.join(SITE_ROOT, 'data', 'allowed_users.json')

OAUTH_STATE_KEY = 'oauth2_state'
SESSION_USER_KEY = 'oauth2_user'

def get_oauth_settings():
    if os.path.exists(ALLOWED_USERS_FILE):
        with open(ALLOWED_USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('oauth_settings', {})
    return {}

def get_allowed_users():
    if os.path.exists(ALLOWED_USERS_FILE):
        with open(ALLOWED_USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('allowed_users', [])
    return []

def save_allowed_users(users):
    if os.path.exists(ALLOWED_USERS_FILE):
        with open(ALLOWED_USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {'allowed_users': [], 'oauth_settings': {}}
    data['allowed_users'] = users
    with open(ALLOWED_USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_user_allowed(user_id):
    return user_id in get_allowed_users()

def get_current_user():
    return session.get(SESSION_USER_KEY)

def require_auth(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'error': '未授权访问', 'need_login': True}), 401
        if not is_user_allowed(user.get('id')):
            return jsonify({'success': False, 'error': '无权访问此功能', 'user_id': user.get('id')}), 403
        return f(*args, **kwargs)
    return decorated_function

def get_user_info(access_token):
    import xml.etree.ElementTree as ET
    oauth_settings = get_oauth_settings()
    nextcloud_url = oauth_settings.get('nextcloud_internal_url', 'http://nextcloud.example.com')
    userinfo_url = oauth_settings.get('userinfo_url', '/ocs/v2.php/cloud/user')
    headers = {'Authorization': f'Bearer {access_token}', 'OCS-APIRequest': 'true'}
    try:
        resp = requests.get(f'{nextcloud_url}{userinfo_url}', headers=headers, timeout=10)
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            data_elem = root.find('data')
            if data_elem is not None:
                def get_text(tag):
                    e = data_elem.find(tag)
                    return e.text if e is not None else ''
                return {
                    'id': get_text('id'),
                    'displayname': get_text('display-name'),
                    'email': get_text('email')
                }
    except Exception as e:
        print(f'获取用户信息失败: {e}')
    return None

# 导入导出模块
try:
    from exporter import add_export_routes
    EXPORTER_AVAILABLE = True
except ImportError:
    EXPORTER_AVAILABLE = False
    print("  警告: 导出模块不可用 (需要 jinja2 库)")
    print("  安装命令: pip install jinja2")


# ==================== OAuth2 认证路由 ====================

@app.route('/oauth/login')
def oauth_login():
    oauth_settings = get_oauth_settings()
    if not oauth_settings.get('client_id'):
        return jsonify({'success': False, 'error': 'OAuth未配置'}), 500
    import secrets
    state = secrets.token_urlsafe(32)
    session['oauth2_state'] = state
    nextcloud_url = oauth_settings.get('nextcloud_external_url', 'https://cloud.starclub.example.com')
    redirect_uri = f'https://{request.host}/oauth/callback'
    params = {
        'client_id': oauth_settings.get('client_id'),
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': 'openid',
        'state': state
    }
    auth_url = f"{nextcloud_url}{oauth_settings.get('authorization_url', '/oauth/authorize')}?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)

@app.route('/oauth/callback')
def oauth_callback():
    error = request.args.get('error')
    if error:
        return jsonify({'success': False, 'error': f'OAuth错误: {error}'}), 400
    code = request.args.get('code')
    state = request.args.get('state')
    if not code or not state:
        return jsonify({'success': False, 'error': '缺少授权码或状态'}), 400
    stored_state = session.pop('oauth2_state', None)
    if state != stored_state:
        return jsonify({'success': False, 'error': '状态不匹配，可能存在CSRF攻击'}), 400
    oauth_settings = get_oauth_settings()
    nextcloud_url = oauth_settings.get('nextcloud_internal_url', 'http://nextcloud.example.com')
    redirect_uri = f'https://{request.host}/oauth/callback'
    token_url = f"{nextcloud_url}{oauth_settings.get('token_url', '/apps/oauth2/api/v1/token')}"
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri,
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
    }
    try:
        resp = requests.post(token_url, data=data, auth=(oauth_settings.get('client_id'), oauth_settings.get('client_secret')), headers=headers, timeout=10)
        if resp.status_code == 200:
            token_data = resp.json()
            access_token = token_data.get('access_token')
            if access_token:
                user_info = get_user_info(access_token)
                if user_info:
                    session['oauth2_user'] = user_info
                    session['oauth2_token'] = access_token
                    if is_user_allowed(user_info.get('id')):
                        return redirect('/admin/index.html')
                    else:
                        return redirect(f'/unauthorized.html?user_id={user_info.get("id")}')
        return jsonify({'success': False, 'error': '获取访问令牌失败', 'details': resp.text, 'status': resp.status_code}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/oauth/logout')
def oauth_logout():
    session.pop('oauth2_user', None)
    session.pop('oauth2_token', None)
    session.pop('oauth2_state', None)
    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="2;url=/">
    <title>已登出 - 星社</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #f8f9fa;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            margin: 0;
        }
        .container {
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        .icon {
            width: 60px;
            height: 60px;
            margin-bottom: 20px;
        }
        h1 { color: #28a745; margin-bottom: 16px; }
        p { color: #6c757d; margin-bottom: 20px; }
        a { color: #005a8c; text-decoration: none; }
    </style>
</head>
<body>
    <div class="container">
        <svg class="icon" viewBox="0 0 60 60" fill="none">
            <circle cx="30" cy="30" r="28" stroke="#28a745" stroke-width="3" fill="#28a74520"/>
            <path d="M18 30l8 8 16-16" stroke="#28a745" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" fill="none"/>
        </svg>
        <h1>已成功登出</h1>
        <p>正在跳转至首页...</p>
        <a href="/">点击这里立即跳转</a>
    </div>
</body>
</html>'''
    return Response(html, mimetype='text/html')

@app.route('/oauth/status')
def oauth_status():
    user = session.get('oauth2_user')
    if user and is_user_allowed(user.get('id')):
        return jsonify({'success': True, 'authenticated': True, 'user': user})
    return jsonify({'success': True, 'authenticated': False})

@app.route('/api/auth/check', methods=['GET'])
def auth_check():
    user = get_current_user()
    if not user:
        return jsonify({'success': False, 'authenticated': False, 'error': '未登录'}), 401
    if not is_user_allowed(user.get('id')):
        return jsonify({'success': False, 'authenticated': True, 'allowed': False, 'user': user, 'error': '无权访问'}), 403
    return jsonify({'success': True, 'authenticated': True, 'allowed': True, 'user': user})

# ==================== 用户管理 API ====================

@app.route('/api/admin/users', methods=['GET'])
@require_auth
def get_allowed_users_api():
    return jsonify({'success': True, 'users': get_allowed_users()})

@app.route('/api/admin/users', methods=['POST'])
@require_auth
def add_allowed_user():
    try:
        data = request.get_json()
        user_id = data.get('user_id', '').strip()
        if not user_id:
            return jsonify({'success': False, 'error': '用户ID不能为空'}), 400
        users = get_allowed_users()
        if user_id in users:
            return jsonify({'success': False, 'error': '用户已在白名单中'}), 400
        users.append(user_id)
        save_allowed_users(users)
        add_operation_log('user_management', 'add_user', f'添加用户: {user_id}')
        return jsonify({'success': True, 'message': f'已添加用户 {user_id}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/users/<user_id>', methods=['DELETE'])
@require_auth
def remove_allowed_user(user_id):
    try:
        users = get_allowed_users()
        if user_id not in users:
            return jsonify({'success': False, 'error': '用户不在白名单中'}), 404
        if user_id == 'admin':
            return jsonify({'success': False, 'error': '不能删除admin账号'}), 400
        if len(users) <= 1:
            return jsonify({'success': False, 'error': '白名单至少需要保留一个账号'}), 400
        users.remove(user_id)
        save_allowed_users(users)
        add_operation_log('user_management', 'remove_user', f'移除用户: {user_id}')
        return jsonify({'success': True, 'message': f'已移除用户 {user_id}'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/admin/users/search', methods=['GET'])
@require_auth
def search_nextcloud_users():
    import xml.etree.ElementTree as ET
    query = request.args.get('query', '').strip()
    if not query:
        return jsonify({'success': True, 'users': []})
    oauth_settings = get_oauth_settings()
    nextcloud_url = oauth_settings.get('nextcloud_internal_url', 'http://nextcloud.example.com')
    access_token = session.get('oauth2_token')
    if not access_token:
        return jsonify({'success': False, 'error': '未登录'}), 401
    headers = {'Authorization': f'Bearer {access_token}', 'OCS-APIRequest': 'true'}
    try:
        search_url = f'{nextcloud_url}/ocs/v2.php/cloud/users?search={urllib.parse.quote(query)}'
        resp = requests.get(search_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            root = ET.fromstring(resp.text)
            users_elem = root.find('.//users')
            users_list = []
            if users_elem is not None:
                for user in users_elem.findall('element'):
                    users_list.append({'id': user.text})
            return jsonify({'success': True, 'users': users_list})
        return jsonify({'success': False, 'error': '搜索失败'}), 400
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# ==================== 静态文件服务 ====================

@app.route('/login.html')
def login_page():
    """登录页面"""
    user = get_current_user()
    if user and is_user_allowed(user.get('id')):
        return redirect('/admin/index.html')

    html = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>管理后台登录 - 星社</title>
    <style>
        :root {
            --primary-color: #005a8c;
            --secondary-color: #4285f4;
            --accent-color: #34a853;
            --text-dark: #202124;
            --text-light: #5f6368;
            --text-white: #ffffff;
            --bg-white: #ffffff;
            --bg-gray: #f8f9fa;
            --border-color: #dadce0;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        .login-container {
            background: var(--bg-white);
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
            padding: 48px 40px;
            width: 100%;
            max-width: 420px;
            text-align: center;
        }
        .logo {
            width: 80px;
            height: 80px;
            margin-bottom: 24px;
        }
        h1 {
            color: var(--text-dark);
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 8px;
        }
        .subtitle {
            color: var(--text-light);
            font-size: 14px;
            margin-bottom: 32px;
        }
        .btn-login {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            width: 100%;
            padding: 14px 24px;
            background: var(--primary-color);
            color: var(--text-white);
            border: none;
            border-radius: 8px;
            font-size: 16px;
            font-weight: 500;
            cursor: pointer;
            transition: background 0.2s, transform 0.1s;
            text-decoration: none;
        }
        .btn-login:hover {
            background: #004c8a;
            transform: translateY(-1px);
        }
        .btn-login:active {
            transform: translateY(0);
        }
        .btn-login svg {
            width: 20px;
            height: 20px;
        }
        .footer {
            margin-top: 32px;
            font-size: 12px;
            color: var(--text-light);
        }
        .footer a {
            color: var(--primary-color);
            text-decoration: none;
        }
        ::-webkit-scrollbar { width: 8px; height: 8px; }
        ::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 4px; }
        ::-webkit-scrollbar-thumb { background: var(--border-color); border-radius: 4px; }
        ::-webkit-scrollbar-thumb:hover { background: #bbb; }
    </style>
</head>
<body>
    <div class="login-container">
        <svg class="logo" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="80" height="80" rx="16" fill="#005a8c"/>
            <path d="M20 40 L35 55 L60 25" stroke="white" stroke-width="8" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <h1>管理后台</h1>
        <p class="subtitle">星社</p>
        <a href="/oauth/login" class="btn-login">
            <svg viewBox="0 0 24 24" fill="currentColor">
                <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-2 15l-5-5 1.41-1.41L10 14.17l7.59-7.59L19 8l-9 9z"/>
            </svg>
            使用 Nextcloud 账号登录
        </a>
        <p class="footer">登录后将验证您是否有权访问管理后台</p>
    </div>
</body>
</html>'''
    return Response(html, mimetype='text/html')

@app.route('/unauthorized.html')
def unauthorized_page():
    """无权限访问页面"""
    user = get_current_user()
    user_id = request.args.get('user_id') or (user.get('id', 'unknown') if user else 'unknown')

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>无权访问 - 星社</title>
    <style>
        :root {{
            --primary-color: #005a8c;
            --danger-color: #dc3545;
            --text-dark: #202124;
            --text-light: #5f6368;
            --text-white: #ffffff;
            --bg-white: #ffffff;
            --bg-gray: #f8f9fa;
            --border-color: #dadce0;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: var(--bg-gray);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .container {{
            background: var(--bg-white);
            border-radius: 12px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
            padding: 48px 40px;
            width: 100%;
            max-width: 480px;
            text-align: center;
        }}
        .icon {{
            width: 80px;
            height: 80px;
            margin-bottom: 24px;
        }}
        h1 {{
            color: var(--danger-color);
            font-size: 24px;
            font-weight: 600;
            margin-bottom: 16px;
        }}
        .message {{
            color: var(--text-light);
            font-size: 14px;
            line-height: 1.6;
            margin-bottom: 24px;
        }}
        .user-id {{
            background: var(--bg-gray);
            padding: 12px 16px;
            border-radius: 8px;
            font-family: monospace;
            font-size: 13px;
            color: var(--text-dark);
            margin-bottom: 24px;
            word-break: break-all;
        }}
        .btn-group {{
            display: flex;
            gap: 12px;
        }}
        .btn {{
            flex: 1;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            text-decoration: none;
            border: none;
        }}
        .btn-primary {{
            background: var(--primary-color);
            color: var(--text-white);
        }}
        .btn-primary:hover {{
            background: #004c8a;
        }}
        .btn-secondary {{
            background: var(--bg-gray);
            color: var(--text-dark);
            border: 1px solid var(--border-color);
        }}
        .btn-secondary:hover {{
            background: #e8eaed;
        }}
        ::-webkit-scrollbar {{ width: 8px; height: 8px; }}
        ::-webkit-scrollbar-track {{ background: #f1f1f1; border-radius: 4px; }}
        ::-webkit-scrollbar-thumb {{ background: var(--border-color); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: #bbb; }}
    </style>
</head>
<body>
    <div class="container">
        <svg class="icon" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
            <circle cx="40" cy="40" r="36" fill="#dc3545" opacity="0.1"/>
            <circle cx="40" cy="40" r="36" stroke="#dc3545" stroke-width="4"/>
            <line x1="28" y1="28" x2="52" y2="52" stroke="#dc3545" stroke-width="4" stroke-linecap="round"/>
            <line x1="52" y1="28" x2="28" y2="52" stroke="#dc3545" stroke-width="4" stroke-linecap="round"/>
        </svg>
        <h1>无权访问</h1>
        <p class="message">您的账号 <strong>{user_id}</strong> 无权访问管理后台，请联系管理员。</p>
        <div class="user-id">用户ID: {user_id}</div>
        <div class="btn-group">
            <a href="/oauth/logout" class="btn btn-secondary">退出登录</a>
            <a href="/" class="btn btn-primary">返回首页</a>
        </div>
    </div>
</body>
</html>'''
    return Response(html, mimetype='text/html')

@app.route('/')
def index():
    return serve_file('index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return serve_file(filename)

# 支持 pages/ 子目录的详情页路由
@app.route('/pages/<path:filename>')
def serve_pages(filename):
    """处理 pages/ 子目录下的详情页请求"""
    # 检查是否匹配详情页文件名
    if filename.endswith('.html'):
        site_data = get_site_data()
        for i, page in enumerate(site_data.get('detailPages', [])):
            page_filename = page.get('filename', f'detail-{i}.html')
            if page_filename == filename:
                return serve_detail_page(i, in_pages_dir=True)
    return serve_file(f'pages/{filename}')

def serve_file(filename):
    """手动读取文件返回，强制禁用缓存"""
    if filename.startswith('admin/'):
        user = get_current_user()
        if not user or not is_user_allowed(user.get('id')):
            return redirect('/oauth/login')

    # 处理详情页动态路由：detail-N.html 或自定义文件名（兼容旧链接，重定向到 pages/）
    detail_match = re.match(r'^detail-(\d+)\.html$', filename)
    if detail_match:
        return serve_detail_page(int(detail_match.group(1)), in_pages_dir=False)

    # 检查是否匹配自定义详情页文件名（根目录下的旧链接兼容）
    if filename.endswith('.html') and not filename.startswith('admin/'):
        site_data = get_site_data()
        for i, page in enumerate(site_data.get('detailPages', [])):
            if page.get('filename') == filename:
                return serve_detail_page(i, in_pages_dir=False)

    filepath = os.path.join(SITE_ROOT, filename)
    if not os.path.isfile(filepath):
        return "Not Found", 404

    with open(filepath, 'rb') as f:
        content = f.read()

    # 根据扩展名确定Content-Type
    ext = os.path.splitext(filename)[1].lower()
    mime_types = {
        '.html': 'text/html',
        '.css': 'text/css',
        '.js': 'application/javascript',
        '.json': 'application/json',
        '.png': 'image/png',
        '.jpg': 'image/jpeg',
        '.gif': 'image/gif',
        '.svg': 'image/svg+xml',
        '.ico': 'image/x-icon',
    }
    content_type = mime_types.get(ext, 'application/octet-stream')

    response = Response(content, mimetype=content_type)
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


# ==================== API 接口 ====================

@app.route('/api/data', methods=['GET'])
def get_all_data():
    """获取所有数据"""
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                return jsonify({'success': True, 'data': json.load(f)})
        except json.JSONDecodeError as e:
            return jsonify({'success': False, 'error': f'JSON解析错误: {str(e)}'}), 500
    return jsonify({'success': False, 'error': '数据文件不存在'}), 404


@app.route('/api/field/<field>', methods=['GET'])
def get_data_field(field):
    """获取指定字段"""
    data = get_site_data()
    if field in data:
        return jsonify({'success': True, 'data': data[field]})
    return jsonify({'success': False, 'error': f'字段 {field} 不存在'}), 404


@app.route('/api/save', methods=['POST'])
def save_data():
    """保存数据"""
    try:
        payload = request.get_json()
        action = payload.get('action', '')

        if action == 'add_item':
            field = payload.get('field', '')
            item = payload.get('item', {})
            return add_data_item(field, item)
        elif action == 'delete_item':
            field = payload.get('field', '')
            index = payload.get('index', -1)
            return delete_data_item(field, index)
        elif action in ('update_activity', 'update_item'):
            field = payload.get('field', '')
            index = payload.get('index', -1)
            item = payload.get('item', {})
            return update_data_item(field, index, item)
        elif action == 'update_text':
            field = payload.get('field', '')
            value = payload.get('value', '')
            return update_text_field(field, value)
        elif action == 'sort_items':
            # 拖拽排序
            field = payload.get('field', '')
            ordered_ids = payload.get('orderedIds', [])
            return sort_data_items(field, ordered_ids)
        else:
            section = payload.get('section', 'all')
            data = payload.get('data', {})
            return save_section(section, data)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def get_site_data():
    """获取站点数据字典"""
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_site_data(data):
    """保存完整数据"""
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_operation_log():
    """获取操作日志"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []


def save_operation_log(logs):
    """保存操作日志"""
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def add_operation_log(module, action, title):
    """添加操作日志"""
    logs = get_operation_log()
    new_log = {
        'module': module,
        'action': action,
        'title': title,
        'time': datetime.datetime.now().isoformat()
    }
    logs.insert(0, new_log)
    if len(logs) > 100:
        logs = logs[:100]
    save_operation_log(logs)
    return new_log


def add_data_item(field, item):
    """添加数据项"""
    site_data = get_site_data()
    if field not in site_data or not isinstance(site_data[field], list):
        site_data[field] = []
    site_data[field].append(item)
    save_site_data(site_data)
    return jsonify({'success': True, 'message': f'已添加新项目到 {field}'})


def update_data_item(field, index, item):
    """更新数据项"""
    site_data = get_site_data()
    if field not in site_data or not isinstance(site_data[field], list):
        return jsonify({'success': False, 'error': f'{field} 不是数组'}), 400
    if index < 0 or index >= len(site_data[field]):
        return jsonify({'success': False, 'error': '索引超出范围'}), 400
    site_data[field][index] = item
    save_site_data(site_data)
    return jsonify({'success': True, 'message': '更新成功'})


def update_text_field(field, value):
    """更新文本字段（如星社机制介绍）"""
    site_data = get_site_data()
    site_data[field] = value
    save_site_data(site_data)
    return jsonify({'success': True, 'message': '文本已更新'})


def delete_data_item(field, index):
    """删除数据项"""
    site_data = get_site_data()
    if field not in site_data or not isinstance(site_data[field], list):
        return jsonify({'success': False, 'error': f'{field} 不是数组'}), 400
    if index < 0 or index >= len(site_data[field]):
        return jsonify({'success': False, 'error': '索引超出范围'}), 400
    deleted_item = site_data[field].pop(index)
    save_site_data(site_data)
    return jsonify({'success': True, 'message': '删除成功', 'deleted': deleted_item})


@app.route('/api/operation-log', methods=['POST'])
def create_operation_log():
    """记录操作日志"""
    try:
        data = request.get_json()
        module = data.get('module', '')
        action = data.get('action', '')
        title = data.get('title', '')
        add_operation_log(module, action, title)
        return jsonify({'success': True, 'message': '日志已记录'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/operation-log', methods=['GET'])
def get_operation_log_api():
    """获取操作日志"""
    logs = get_operation_log()
    return jsonify({'success': True, 'logs': logs})


@app.route('/api/batch-import', methods=['POST'])
def batch_import():
    """批量导入数据（CSV格式）"""
    import csv
    import io

    try:
        data = request.get_json()
        field = data.get('field', '')
        csv_content = data.get('csv', '')

        if not field:
            return jsonify({'success': False, 'error': '未指定导入字段'}), 400
        if not csv_content:
            return jsonify({'success': False, 'error': 'CSV内容为空'}), 400

        # 移除 UTF-8 BOM
        if csv_content.startswith('\ufeff'):
            csv_content = csv_content[1:]

        site_data = get_site_data()
        if field not in site_data or not isinstance(site_data[field], list):
            return jsonify({'success': False, 'error': f'{field} 不是数组类型'}), 400

        # 解析 CSV
        reader = csv.DictReader(io.StringIO(csv_content))
        rows = list(reader)

        if not rows:
            return jsonify({'success': False, 'error': 'CSV内容为空或格式错误'}), 400

        added_count = 0
        errors = []

        if field == 'members':
            for i, row in enumerate(rows):
                try:
                    name = row.get('姓名', '').strip()
                    if not name:
                        errors.append(f'第{i+2}行：姓名为空')
                        continue
                    member = {
                        'name': name,
                        'grade': row.get('加入年份', '').strip(),
                        'field': row.get('方向', '').strip(),
                        'bio': row.get('简介', '').strip(),
                        'photo': row.get('照片URL', '').strip(),
                        'link': row.get('个人链接', '').strip(),
                        'visible': row.get('显示', 'true').strip().lower() != 'false'
                    }
                    site_data['members'].append(member)
                    added_count += 1
                except Exception as e:
                    errors.append(f'第{i+2}行：{str(e)}')

        elif field == 'resources':
            for i, row in enumerate(rows):
                try:
                    title = row.get('标题', '').strip()
                    if not title:
                        errors.append(f'第{i+2}行：标题为空')
                        continue
                    resource = {
                        'icon': row.get('图标', '📚').strip(),
                        'title': title,
                        'desc': row.get('描述', '').strip(),
                        'category': row.get('分类', '').strip(),
                        'link': row.get('链接', '').strip(),
                        'visible': row.get('显示', 'true').strip().lower() != 'false'
                    }
                    site_data['resources'].append(resource)
                    added_count += 1
                except Exception as e:
                    errors.append(f'第{i+2}行：{str(e)}')

        else:
            return jsonify({'success': False, 'error': f'不支持的字段: {field}'}), 400

        save_site_data(site_data)

        result_msg = f'成功导入 {added_count} 条数据'
        if errors:
            result_msg += f'，{len(errors)} 条错误'
        return jsonify({
            'success': True,
            'message': result_msg,
            'added': added_count,
            'errors': errors[:20]
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def sort_data_items(field, ordered_ids):
    """拖拽排序数据项"""
    site_data = get_site_data()
    if field not in site_data or not isinstance(site_data[field], list):
        return jsonify({'success': False, 'error': f'{field} 不是数组'}), 400

    items = site_data[field]

    # ordered_ids 是新的排序顺序（元素索引数组）
    # 例如 [2, 0, 1] 表示原来索引2的元素排第一，索引0的排第二，索引1的排第三
    if not ordered_ids or not isinstance(ordered_ids, list):
        return jsonify({'success': False, 'error': '排序顺序无效'}), 400

    # 检查是否所有ID都在范围内
    if len(ordered_ids) != len(items):
        return jsonify({'success': False, 'error': '排序数量与实际数据不匹配'}), 400

    if any(not isinstance(i, int) or i < 0 or i >= len(items) for i in ordered_ids):
        return jsonify({'success': False, 'error': '排序索引超出范围'}), 400

    # 按照新的顺序重新排列
    new_items = [items[i] for i in ordered_ids]
    site_data[field] = new_items
    save_site_data(site_data)

    return jsonify({'success': True, 'message': '排序已更新'})


def save_section(section, data):
    """保存指定部分"""
    site_data = get_site_data()

    if section == 'hero':
        # 构建核心共创数组（从 activityIcon1~4, activityTitle1~4, activityDesc1~4, activityLink1~4）
        coreActivities = []
        for i in range(1, 5):
            icon = data.get(f'activityIcon{i}', '')
            title = data.get(f'activityTitle{i}', '')
            desc = data.get(f'activityDesc{i}', '')
            link = data.get(f'activityLink{i}', '')
            if title:
                coreActivities.append({
                    'icon': icon,
                    'title': title,
                    'desc': desc,
                    'link': link
                })

        site_data['hero'] = {
            'title': data.get('heroTitle', ''),
            'subtitle': data.get('heroSubtitle', ''),
            'desc': data.get('heroDesc', ''),
            'btn1Text': data.get('heroBtn1Text', ''),
            'btn1Link': data.get('heroBtn1Link', ''),
            'btn2Text': data.get('heroBtn2Text', ''),
            'btn2Link': data.get('heroBtn2Link', '')
        }
        if coreActivities:
            site_data['coreActivities'] = coreActivities
    elif section == 'stats':
        site_data['stats'] = {
            'foundedYear': data.get('foundedYear', ''),
            'memberCount': data.get('memberCount', ''),
            'activityCount': data.get('activityCount', ''),
            'foundedYearLabel': data.get('foundedYearLabel', '成立年份'),
            'memberCountLabel': data.get('memberCountLabel', '成员总数'),
            'activityCountLabel': data.get('activityCountLabel', '共创项目')
        }
    elif section == 'about':
        site_data['about'] = {
            'title': data.get('aboutTitle', ''),
            'subtitle': data.get('aboutSubtitle', ''),
            'content': data.get('aboutContent', ''),
            'vision': data.get('aboutVision', '')
        }
        values = []
        for i in range(1, 4):
            title = data.get(f'valueTitle{i}', '')
            if title:
                values.append({
                    'icon': data.get(f'valueIcon{i}', ''),
                    'title': title,
                    'desc': data.get(f'valueDesc{i}', '')
                })
        site_data['about']['values'] = values
    elif section == 'advisor':
        # 处理研究方向（每行一条）
        research_areas = []
        research_text = data.get('advisorResearchAreas', '')
        if research_text:
            research_areas = [line.strip() for line in research_text.split('\n') if line.strip()]

        site_data['advisor'] = {
            'name': data.get('advisorName', ''),
            'title': data.get('advisorTitle', '指导老师'),
            'titleFull': data.get('advisorTitleFull', ''),
            'photo': data.get('advisorPhoto', ''),
            'bio': data.get('advisorBio', ''),
            'link': data.get('advisorLink', ''),
            'researchAreas': research_areas
        }
    elif section == 'contact':
        site_data['contact'] = {
            'qqGroup': data.get('contactQqGroup', ''),
            'wechat': data.get('contactWechat', ''),
            'email': data.get('contactEmail', ''),
            'location': data.get('contactLocation', ''),
            'github': data.get('contactGithub', '')
        }
    elif section == 'join':
        # 处理加入要求和收益（每行一条）
        requirements = []
        benefits = []

        req_text = data.get('joinRequirements', '')
        if req_text:
            requirements = [line.strip() for line in req_text.split('\n') if line.strip()]

        benefit_text = data.get('joinBenefits', '')
        if benefit_text:
            benefits = [line.strip() for line in benefit_text.split('\n') if line.strip()]

        # 处理FAQ数据
        faq = data.get('faq', [])
        if isinstance(faq, list):
            # 过滤掉空的问题或回答
            faq = [item for item in faq if item.get('question') or item.get('answer')]

        site_data['join'] = {
            'qqGroup': data.get('joinQqGroup', ''),
            'status': data.get('joinStatus', 'open'),
            'notice': data.get('joinNotice', ''),
            'requirements': requirements,
            'benefits': benefits,
            'time': data.get('joinTime', ''),
            'location': data.get('joinLocation', ''),
            'link': data.get('joinLink', ''),
            'faq': faq
        }
    elif section == 'footer':
        # 处理页脚子项
        column1Items = []
        column2Items = []
        column3Items = []

        # 如果直接传了 column1Items 数组（从 collectFooterItems 来的）
        if isinstance(data.get('column1Items'), list):
            column1Items = data.get('column1Items', [])
        if isinstance(data.get('column2Items'), list):
            column2Items = data.get('column2Items', [])
        if isinstance(data.get('column3Items'), list):
            column3Items = data.get('column3Items', [])

        site_data['footer'] = {
            'copyright': data.get('footerCopyright', ''),
            'icp': data.get('footerIcp', ''),
            'github': data.get('footerGithub', ''),
            'column1Title': data.get('column1Title', '关于星社'),
            'column1Items': column1Items,
            'column2Title': data.get('column2Title', '快速链接'),
            'column2Items': column2Items,
            'column3Title': data.get('column3Title', '联系我们'),
            'column3Items': column3Items
        }
    elif section == 'all':
        # 扁平化数据更新
        if any(k.startswith('hero') for k in data.keys()):
            site_data['hero'] = {
                'title': data.get('heroTitle', site_data.get('hero', {}).get('title', '')),
                'subtitle': data.get('heroSubtitle', site_data.get('hero', {}).get('subtitle', '')),
                'desc': data.get('heroDesc', site_data.get('hero', {}).get('desc', '')),
                'btn1Text': data.get('heroBtn1Text', site_data.get('hero', {}).get('btn1Text', '')),
                'btn1Link': data.get('heroBtn1Link', site_data.get('hero', {}).get('btn1Link', '')),
                'btn2Text': data.get('heroBtn2Text', site_data.get('hero', {}).get('btn2Text', '')),
                'btn2Link': data.get('heroBtn2Link', site_data.get('hero', {}).get('btn2Link', ''))
            }
        if any(k in ['foundedYear', 'memberCount', 'activityCount'] for k in data.keys()):
            site_data['stats'] = {
                'foundedYear': data.get('foundedYear', site_data.get('stats', {}).get('foundedYear', '')),
                'memberCount': data.get('memberCount', site_data.get('stats', {}).get('memberCount', '')),
                'activityCount': data.get('activityCount', site_data.get('stats', {}).get('activityCount', ''))
            }

    save_site_data(site_data)
    return jsonify({'success': True, 'message': f'{section} 保存成功'})


# ==================== 文件管理 API ====================

@app.route('/api/files', methods=['GET'])
@app.route('/api/files/<category>', methods=['GET'])
def get_file_list(category=None):
    """获取上传文件列表"""
    uploads_dir = os.path.join(SITE_ROOT, 'uploads')

    # 定义分类及对应扩展名
    categories = {
        'images': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico'],
        'documents': ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx', '.txt'],
        'videos': ['.mp4', '.webm', '.ogg', '.avi', '.mov'],
        'audios': ['.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma'],
        'avatars': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
        'other': []
    }

    def get_file_category(filename):
        """根据文件名判断分类"""
        ext = os.path.splitext(filename)[1].lower()
        for cat, exts in categories.items():
            if ext in exts:
                return cat
        return 'other'

    all_files = []

    if category and category in categories:
        # 获取指定分类
        cat_dir = os.path.join(uploads_dir, category)
        if os.path.exists(cat_dir):
            for f in os.listdir(cat_dir):
                fpath = os.path.join(cat_dir, f)
                if os.path.isfile(fpath):
                    all_files.append({
                        'name': f,
                        'path': f'uploads/{category}/{f}',
                        'size': os.path.getsize(fpath),
                        'modified': os.path.getmtime(fpath),
                        'category': category
                    })
        # 根目录文件也显示在对应分类中（兼容旧数据）
        for f in os.listdir(uploads_dir):
            fpath = os.path.join(uploads_dir, f)
            if os.path.isfile(fpath):
                file_cat = get_file_category(f)
                if file_cat == category:
                    all_files.append({
                        'name': f,
                        'path': f'uploads/{f}',
                        'size': os.path.getsize(fpath),
                        'modified': os.path.getmtime(fpath),
                        'category': file_cat
                    })
    else:
        # 获取所有文件（包括根目录和子目录）
        # 先遍历子目录
        for cat in categories.keys():
            cat_dir = os.path.join(uploads_dir, cat)
            if os.path.exists(cat_dir):
                for f in os.listdir(cat_dir):
                    fpath = os.path.join(cat_dir, f)
                    if os.path.isfile(fpath):
                        all_files.append({
                            'name': f,
                            'path': f'uploads/{cat}/{f}',
                            'size': os.path.getsize(fpath),
                            'modified': os.path.getmtime(fpath),
                            'category': cat
                        })
        # 再遍历根目录（旧文件兼容）
        if os.path.exists(uploads_dir):
            for f in os.listdir(uploads_dir):
                fpath = os.path.join(uploads_dir, f)
                if os.path.isfile(fpath):
                    all_files.append({
                        'name': f,
                        'path': f'uploads/{f}',
                        'size': os.path.getsize(fpath),
                        'modified': os.path.getmtime(fpath),
                        'category': get_file_category(f)
                    })

    # 去重（根目录文件已在子目录中出现则跳过）
    seen = set()
    unique_files = []
    for f in all_files:
        if f['path'] not in seen:
            seen.add(f['path'])
            unique_files.append(f)

    # 按修改时间倒序
    unique_files.sort(key=lambda x: x['modified'], reverse=True)

    return jsonify({
        'success': True,
        'files': unique_files,
        'categories': list(categories.keys())
    })


@app.route('/api/files/upload', methods=['POST'])
def upload_file():
    """上传文件"""
    uploads_dir = os.path.join(SITE_ROOT, 'uploads')

    if 'file' not in request.files:
        return jsonify({'success': False, 'error': '没有文件'}), 400

    file = request.files['file']
    category = request.form.get('category', 'images')  # 默认上传到 images

    if file.filename == '':
        return jsonify({'success': False, 'error': '文件名为空'}), 400

    # 安全检查：只允许特定字符
    filename = os.path.basename(file.filename)
    if not filename.replace('_', '').replace('-', '').replace('.', '').replace(' ', '').isalnum():
        return jsonify({'success': False, 'error': '文件名包含非法字符'}), 400

    # 确保分类目录存在
    cat_dir = os.path.join(uploads_dir, category)
    if not os.path.exists(cat_dir):
        os.makedirs(cat_dir)

    # 处理重名文件
    filepath = os.path.join(cat_dir, filename)
    if os.path.exists(filepath):
        name, ext = os.path.splitext(filename)
        filename = f"{name}_{int(os.path.getmtime(filepath))}{ext}"
        filepath = os.path.join(cat_dir, filename)

    file.save(filepath)

    return jsonify({
        'success': True,
        'message': '上传成功',
        'file': {
            'name': filename,
            'path': f'uploads/{category}/{filename}',
            'size': os.path.getsize(filepath)
        }
    })


@app.route('/api/files/rename', methods=['POST'])
def rename_file():
    """重命名文件"""
    import uuid
    data = request.get_json()
    old_path = data.get('path', '')
    new_name = data.get('newName', '').strip()

    if not old_path:
        return jsonify({'success': False, 'error': '文件路径为空'}), 400
    if not new_name:
        return jsonify({'success': False, 'error': '新文件名不能为空'}), 400

    # 安全检查：只允许 uploads 目录下的文件
    full_path = os.path.join(SITE_ROOT, old_path)
    if not full_path.startswith(os.path.join(SITE_ROOT, 'uploads')):
        return jsonify({'success': False, 'error': '非法路径'}), 400

    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return jsonify({'success': False, 'error': '文件不存在'}), 404

    # 安全检查：新文件名只允许特定字符
    new_name = os.path.basename(new_name)
    if not new_name.replace('_', '').replace('-', '').replace('.', '').replace(' ', '').isalnum():
        return jsonify({'success': False, 'error': '文件名包含非法字符'}), 400

    # 保留扩展名：如果新名字没有扩展名，使用原扩展名
    old_ext = os.path.splitext(os.path.basename(full_path))[1].lower()
    new_ext = os.path.splitext(new_name)[1].lower()
    if not new_ext and old_ext:
        new_name += old_ext

    # 构建新路径（保持在同一目录）
    dir_path = os.path.dirname(full_path)
    new_full_path = os.path.join(dir_path, new_name)

    # 检查重名
    if os.path.exists(new_full_path) and os.path.abspath(new_full_path) != os.path.abspath(full_path):
        return jsonify({'success': False, 'error': '同名文件已存在'}), 400

    try:
        os.rename(full_path, new_full_path)
        # 计算新的相对路径
        new_rel_path = os.path.relpath(new_full_path, SITE_ROOT).replace('\\', '/')
        return jsonify({
            'success': True,
            'message': '重命名成功',
            'newPath': new_rel_path,
            'newName': new_name
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'重命名失败: {str(e)}'}), 500


@app.route('/api/files/random-name', methods=['POST'])
def random_name_file():
    """将文件重命名为随机名称"""
    import uuid
    data = request.get_json()
    old_path = data.get('path', '')

    if not old_path:
        return jsonify({'success': False, 'error': '文件路径为空'}), 400

    # 安全检查：只允许 uploads 目录下的文件
    full_path = os.path.join(SITE_ROOT, old_path)
    if not full_path.startswith(os.path.join(SITE_ROOT, 'uploads')):
        return jsonify({'success': False, 'error': '非法路径'}), 400

    if not os.path.exists(full_path) or not os.path.isfile(full_path):
        return jsonify({'success': False, 'error': '文件不存在'}), 404

    # 生成随机名称，保留原扩展名
    ext = os.path.splitext(os.path.basename(full_path))[1].lower()
    random_name = uuid.uuid4().hex[:12] + ext

    dir_path = os.path.dirname(full_path)
    new_full_path = os.path.join(dir_path, random_name)

    # 极小概率冲突，确保不重名
    while os.path.exists(new_full_path):
        random_name = uuid.uuid4().hex[:12] + ext
        new_full_path = os.path.join(dir_path, random_name)

    try:
        os.rename(full_path, new_full_path)
        new_rel_path = os.path.relpath(new_full_path, SITE_ROOT).replace('\\', '/')
        return jsonify({
            'success': True,
            'message': '已随机命名',
            'newPath': new_rel_path,
            'newName': random_name
        })
    except Exception as e:
        return jsonify({'success': False, 'error': f'重命名失败: {str(e)}'}), 500


@app.route('/api/files/delete', methods=['POST'])
def delete_file():
    """删除文件"""
    data = request.get_json()
    filepath = data.get('path', '')

    if not filepath:
        return jsonify({'success': False, 'error': '文件路径为空'}), 400

    # 安全检查：只允许 uploads 目录下的文件
    full_path = os.path.join(SITE_ROOT, filepath)
    if not full_path.startswith(os.path.join(SITE_ROOT, 'uploads')):
        return jsonify({'success': False, 'error': '非法路径'}), 400

    if os.path.exists(full_path) and os.path.isfile(full_path):
        os.remove(full_path)
        return jsonify({'success': True, 'message': '删除成功'})

    return jsonify({'success': False, 'error': '文件不存在'}), 404


# ==================== 详情页 API ====================

def slugify(text):
    """将中文标题转为URL友好的slug"""
    if not text:
        return 'page'
    text = text.strip()
    # 去除特殊字符，保留中文、字母、数字、连字符
    text = re.sub(r'[^\u4e00-\u9fff\w\s-]', '', text)
    text = re.sub(r'[\s_]+', '-', text)
    text = text.strip('-')
    if not text:
        return 'page'
    return text

def render_markdown_content(text):
    """将Markdown渲染为HTML"""
    if not text:
        return ''
    try:
        return md.markdown(text, extensions=['extra', 'codehilite', 'toc', 'tables', 'fenced_code'])
    except Exception:
        pass


@app.route('/api/detail-pages', methods=['GET'])
def get_detail_pages():
    """获取所有详情页（按最近编辑时间倒序）"""
    site_data = get_site_data()
    pages = site_data.get('detailPages', [])
    # 分离有时间和没有时间的页面
    with_time = [(i, p) for i, p in enumerate(pages) if p.get('updatedAt')]
    without_time = [(i, p) for i, p in enumerate(pages) if not p.get('updatedAt')]
    # 有 updatedAt 的按时间倒序
    with_time.sort(key=lambda x: x[1].get('updatedAt', ''), reverse=True)
    # 没有 updatedAt 的保持原顺序（按原始索引）
    without_time.sort(key=lambda x: x[0])
    # 有时间的排在前面，没时间的排在后面
    sorted_pages = [p for _, p in with_time] + [p for _, p in without_time]
    return jsonify({'success': True, 'pages': sorted_pages})


@app.route('/api/detail-pages', methods=['POST'])
def save_detail_page():
    """保存详情页（新建或更新）"""
    try:
        payload = request.get_json()
        page_data = payload.get('page', {})
        page_id = payload.get('id', None)

        site_data = get_site_data()
        if 'detailPages' not in site_data:
            site_data['detailPages'] = []

        # 预处理：为markdown类型板块渲染HTML
        if 'sections' in page_data:
            for section in page_data['sections']:
                if section.get('type') == 'markdown' and section.get('content'):
                    section['html'] = render_markdown_content(section['content'])

        now = datetime.datetime.now().isoformat()

        if page_id is not None:
            # 更新
            if isinstance(page_id, int) or (isinstance(page_id, str) and page_id.isdigit()):
                # 旧逻辑：通过数组索引更新
                idx = int(page_id)
                if 0 <= idx < len(site_data['detailPages']):
                    page_data['updatedAt'] = now
                    site_data['detailPages'][idx] = page_data
                else:
                    return jsonify({'success': False, 'error': '索引超出范围'}), 400
            else:
                # 新逻辑：通过 filename 查找并更新
                filename = page_id
                found = False
                for i, p in enumerate(site_data['detailPages']):
                    if p.get('filename') == filename:
                        page_data['updatedAt'] = now
                        site_data['detailPages'][i] = page_data
                        found = True
                        break
                if not found:
                    return jsonify({'success': False, 'error': '页面不存在'}), 404
        else:
            # 新建
            page_data['createdAt'] = now
            page_data['updatedAt'] = now
            site_data['detailPages'].append(page_data)

        save_site_data(site_data)
        return jsonify({'success': True, 'message': '详情页保存成功'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/detail-pages/<identifier>', methods=['DELETE'])
def delete_detail_page(identifier):
    """删除详情页（支持索引或文件名）"""
    site_data = get_site_data()
    pages = site_data.get('detailPages', [])

    deleted = None
    delete_index = -1

    # 判断是索引还是文件名
    if identifier.isdigit():
        idx = int(identifier)
        if 0 <= idx < len(pages):
            delete_index = idx
            deleted = pages[idx]
    else:
        # 通过 filename 查找
        for i, p in enumerate(pages):
            if p.get('filename') == identifier:
                delete_index = i
                deleted = p
                break

    if delete_index < 0 or deleted is None:
        return jsonify({'success': False, 'error': '页面不存在'}), 404

    pages.pop(delete_index)
    site_data['detailPages'] = pages
    save_site_data(site_data)
    return jsonify({'success': True, 'message': '详情页已删除', 'deleted': deleted})


@app.route('/api/detail-pages/generate/<int:index>', methods=['POST'])
def generate_detail_page(index):
    """生成详情页HTML文件到项目根目录 pages/ 目录"""
    site_data = get_site_data()
    pages = site_data.get('detailPages', [])
    if index < 0 or index >= len(pages):
        return jsonify({'success': False, 'error': '索引超出范围'}), 400

    page = pages[index]
    filename = page.get('filename', f'detail-{index}.html')

    try:
        # 预处理markdown
        for section in page.get('sections', []):
            if section.get('type') == 'markdown' and section.get('content'):
                section['html'] = render_markdown_content(section['content'])

        # 生成到项目根目录的 pages/ 子目录
        pages_dir = os.path.join(SITE_ROOT, 'pages')
        os.makedirs(pages_dir, exist_ok=True)

        result = _generate_detail_page_file(page, filename, pages_dir)

        if result:
            return jsonify({'success': True, 'message': '详情页已生成', 'filename': f'pages/{filename}'})
        else:
            return jsonify({'success': False, 'error': '渲染失败'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def _render_footer_html(footer_data):
    """渲染页脚HTML"""
    if not footer_data:
        return ''

    col1_title = footer_data.get('column1Title', '关于星社')
    col2_title = footer_data.get('column2Title', '快速链接')
    col3_title = footer_data.get('column3Title', '联系我们')
    copyright_text = footer_data.get('copyright', '')
    github = footer_data.get('github', '')

    html = ''

    # 第一列
    html += f'<h4>{col1_title}</h4><ul class="footer-links">'
    for item in (footer_data.get('column1Items') or []):
        link = item.get('link', '#')
        text = item.get('text', '')
        html += f'<li><a href="{link}">{text}</a></li>'
    html += '</ul>'

    # 第二列
    html += f'<h4>{col2_title}</h4><ul class="footer-links">'
    for item in (footer_data.get('column2Items') or []):
        link = item.get('link', '#')
        text = item.get('text', '')
        html += f'<li><a href="{link}">{text}</a></li>'
    html += '</ul>'

    # 第三列
    html += f'<h4>{col3_title}</h4><ul class="footer-links">'
    for item in (footer_data.get('column3Items') or []):
        link = item.get('link', '#')
        text = item.get('text', '')
        html += f'<li><a href="{link}">{text}</a></li>'
    if github:
        html += f'<li><a href="{github}" class="footer-github" target="_blank"><svg width="16" height="16" viewBox="0 0 24 24" style="vertical-align: middle; margin-right: 4px;"><path fill="currentColor" d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>GitHub</a></li>'
    html += '</ul>'

    return html


def _generate_detail_page_file(page, filename, pages_dir):
    """生成详情页HTML文件到指定目录"""
    try:
        template_path = os.path.join(SITE_ROOT, 'detail-template.html')
        if not os.path.exists(template_path):
            return False

        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()

        # 替换标题
        html = html.replace('<h1 class="page-title">详情页</h1>',
                           f'<h1 class="page-title">{page.get("title", "详情页")}</h1>')
        if page.get('subtitle'):
            html = html.replace('<p class="page-subtitle"></p>',
                              f'<p class="page-subtitle">{page["subtitle"]}</p>')
        html = html.replace('<title>详情页 - 星社</title>',
                          f'<title>{page.get("title", "详情页")} - 星社</title>')

        # 预处理markdown板块（避免修改原始page数据）
        for section in page.get('sections', []):
            if section.get('type') == 'markdown' and section.get('content'):
                section['html'] = render_markdown_content(section['content'])

        # 渲染sections内容
        sections_html = render_detail_sections(page)
        html = html.replace('<!-- 由 data-loader.js 动态渲染 -->', sections_html)

        # 渲染页脚数据
        site_data = get_site_data()
        footer = site_data.get('footer', {})
        # 替换页脚标题
        if footer.get('column1Title'):
            html = html.replace('<h4 id="footerCol1Title">关于星社</h4>',
                              f'<h4>{footer["column1Title"]}</h4>')
        if footer.get('column2Title'):
            html = html.replace('<h4 id="footerCol2Title">快速链接</h4>',
                              f'<h4>{footer["column2Title"]}</h4>')
        if footer.get('column3Title'):
            html = html.replace('<h4 id="footerCol3Title">联系我们</h4>',
                              f'<h4>{footer["column3Title"]}</h4>')
        # 渲染页脚链接
        col1_links = ''.join(f'<li><a href="{item.get("link", "#")}">{item.get("text", "")}</a></li>'
                            for item in (footer.get('column1Items') or []))
        col2_links = ''.join(f'<li><a href="{item.get("link", "#")}">{item.get("text", "")}</a></li>'
                            for item in (footer.get('column2Items') or []))
        col3_links = ''.join(f'<li><a href="{item.get("link", "#")}">{item.get("text", "")}</a></li>'
                            for item in (footer.get('column3Items') or []))
        if footer.get('github'):
            col3_links += f'<li><a href="{footer["github"]}" class="footer-github" target="_blank"><svg width="16" height="16" viewBox="0 0 24 24" style="vertical-align: middle; margin-right: 4px;"><path fill="currentColor" d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>GitHub</a></li>'
        html = html.replace('<ul class="footer-links" id="footerCol1Links"></ul>',
                          f'<ul class="footer-links">{col1_links}</ul>')
        html = html.replace('<ul class="footer-links" id="footerCol2Links"></ul>',
                          f'<ul class="footer-links">{col2_links}</ul>')
        html = html.replace('<ul class="footer-links" id="footerCol3Links"></ul>',
                          f'<ul class="footer-links">{col3_links}</ul>')
        # 版权信息
        if footer.get('copyright'):
            html = html.replace('<p id="footerCopyright">&copy; 星社. All rights reserved.</p>',
                              f'<p>&copy; {footer["copyright"]} 星社. All rights reserved.</p>')

        # 移除data-loader（内容已内嵌）
        html = html.replace('<script src="js/data-loader.js"></script>\n', '')

        # 修正资源路径（pages/ 子目录需要 ../ 前缀）
        html = _fix_resource_paths_for_pages(html)

        # 处理内容中的内部资源路径（uploads/ -> ../uploads/）
        html = _fix_internal_paths_in_content(html)

        output_path = os.path.join(pages_dir, filename)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        return True
    except Exception as e:
        print(f"生成详情页失败: {e}")
        return False


def _fix_resource_paths_for_pages(html):
    """修正模板结构中的资源路径（pages/ 子目录需要 ../ 前缀）"""
    html = html.replace('href="static/', 'href="../static/')
    html = html.replace('src="static/', 'src="../static/')
    html = html.replace('href="css/', 'href="../css/')
    html = html.replace('href="js/', 'href="../js/')
    html = html.replace('src="js/', 'src="../js/')
    html = html.replace('href="index.html"', 'href="../index.html"')
    html = html.replace('href="about.html"', 'href="../about.html"')
    html = html.replace('href="activities.html"', 'href="../activities.html"')
    html = html.replace('href="resources.html"', 'href="../resources.html"')
    html = html.replace('href="members.html"', 'href="../members.html"')
    html = html.replace('href="join.html"', 'href="../join.html"')
    html = html.replace('href="contact.html"', 'href="../contact.html"')
    return html


def _fix_internal_paths_in_content(html):
    """处理内容中的内部资源路径，确保在 pages/ 子目录下可正确访问"""
    # 将 src="uploads/..." 替换为 src="../uploads/..."
    # 但不替换已经是绝对路径或已有 ../ 前缀的
    import re
    # 匹配 src="uploads/..." 或 src="/uploads/..." 但不匹配 src="../uploads/..."
    html = re.sub(r'(src|href)="(uploads/)', r'\1="../\2', html)
    html = re.sub(r'(src|href)="(/uploads/)', r'\1="../uploads/', html)
    return html


def render_detail_sections(page):
    """将详情页sections渲染为HTML字符串"""
    sections_html = ''
    for section in page.get('sections', []):
        sections_html += '<div class="detail-section">'

        if section.get('type') == 'heading':
            content = section.get('content', '')
            sections_html += f'<h2 class="detail-section-heading">{content}</h2>'

        elif section.get('type') == 'text':
            content = section.get('content', '')
            sections_html += f'<div class="detail-section-text">{content}</div>'

        elif section.get('type') == 'cards' and section.get('items'):
            sections_html += '<div class="detail-cards-grid">'
            for card in section['items']:
                link = card.get('link', '')
                is_external = link.startswith('http') if link else False
                target_attr = ' target="_blank"' if is_external else ''
                if link:
                    sections_html += f'<a href="{link}" class="detail-card"{target_attr}>'
                else:
                    sections_html += '<div class="detail-card">'
                if card.get('icon'):
                    sections_html += f'<div class="detail-card-icon">{card["icon"]}</div>'
                if card.get('title'):
                    sections_html += f'<div class="detail-card-title">{card["title"]}</div>'
                if card.get('desc'):
                    sections_html += f'<div class="detail-card-desc">{card["desc"]}</div>'
                if link:
                    sections_html += '<span class="detail-card-link">查看详情 →</span></a>'
                else:
                    sections_html += '</div>'
            sections_html += '</div>'

        elif section.get('type') == 'image':
            sections_html += '<div class="detail-section-image">'
            src = section.get('src', '')
            alt = section.get('alt', '')
            if src:
                sections_html += f'<img src="{src}" alt="{alt}" loading="lazy">'
            caption = section.get('caption', '')
            if caption:
                sections_html += f'<div class="media-caption">{caption}</div>'
            sections_html += '</div>'

        elif section.get('type') == 'video':
            sections_html += '<div class="detail-section-video">'
            embed = section.get('embed', '')
            video_src = section.get('src', '')
            poster = section.get('poster', '')
            if embed:
                sections_html += f'<iframe src="{embed}" frameborder="0" allowfullscreen style="aspect-ratio:16/9;min-height:360px;" allow="accelerometer;autoplay;clipboard-write;encrypted-media;gyroscope;picture-in-picture"></iframe>'
            elif video_src:
                poster_attr = f' poster="{poster}"' if poster else ''
                sections_html += f'<video controls preload="metadata"{poster_attr}><source src="{video_src}" type="video/mp4">您的浏览器不支持视频播放</video>'
            caption = section.get('caption', '')
            if caption:
                sections_html += f'<div class="media-caption">{caption}</div>'
            sections_html += '</div>'

        elif section.get('type') == 'audio':
            sections_html += '<div class="detail-section-audio">'
            audio_src = section.get('src', '')
            if audio_src:
                sections_html += f'<audio controls preload="metadata" style="width:100%;"><source src="{audio_src}" type="audio/mpeg">您的浏览器不支持音频播放</audio>'
            caption = section.get('caption', '')
            if caption:
                sections_html += f'<div class="media-caption">{caption}</div>'
            sections_html += '</div>'

        elif section.get('type') == 'html':
            content = section.get('content', '')
            sections_html += f'<div class="detail-section-html">{content}</div>'

        elif section.get('type') == 'markdown':
            html_content = section.get('html', '') or section.get('content', '')
            sections_html += f'<div class="detail-section-markdown">{html_content}</div>'

        sections_html += '</div>'

    return sections_html


def serve_detail_page(index, in_pages_dir=False):
    """动态渲染详情页（由serve_file调用）"""
    site_data = get_site_data()
    pages = site_data.get('detailPages', [])
    if index < 0 or index >= len(pages):
        return "Not Found", 404

    page = pages[index]

    # 预处理markdown板块
    for section in page.get('sections', []):
        if section.get('type') == 'markdown' and section.get('content'):
            section['html'] = render_markdown_content(section['content'])

    # 读取详情页模板
    template_path = os.path.join(SITE_ROOT, 'detail-template.html')
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            html = f.read()

        # 替换标题
        html = html.replace('<h1 class="page-title">详情页</h1>',
                           f'<h1 class="page-title">{page.get("title", "详情页")}</h1>')
        if page.get('subtitle'):
            html = html.replace('<p class="page-subtitle"></p>',
                              f'<p class="page-subtitle">{page["subtitle"]}</p>')
        html = html.replace('<title>详情页 - 星社</title>',
                          f'<title>{page.get("title", "详情页")} - 星社</title>')

        # 渲染sections内容
        sections_html = render_detail_sections(page)
        html = html.replace('<!-- 由 data-loader.js 动态渲染 -->', sections_html)

        # 渲染页脚数据
        footer = site_data.get('footer', {})
        if footer.get('column1Title'):
            html = html.replace('<h4 id="footerCol1Title">关于星社</h4>',
                              f'<h4>{footer["column1Title"]}</h4>')
        if footer.get('column2Title'):
            html = html.replace('<h4 id="footerCol2Title">快速链接</h4>',
                              f'<h4>{footer["column2Title"]}</h4>')
        if footer.get('column3Title'):
            html = html.replace('<h4 id="footerCol3Title">联系我们</h4>',
                              f'<h4>{footer["column3Title"]}</h4>')
        col1_links = ''.join(f'<li><a href="{item.get("link", "#")}">{item.get("text", "")}</a></li>'
                            for item in (footer.get('column1Items') or []))
        col2_links = ''.join(f'<li><a href="{item.get("link", "#")}">{item.get("text", "")}</a></li>'
                            for item in (footer.get('column2Items') or []))
        col3_links = ''.join(f'<li><a href="{item.get("link", "#")}">{item.get("text", "")}</a></li>'
                            for item in (footer.get('column3Items') or []))
        if footer.get('github'):
            col3_links += f'<li><a href="{footer["github"]}" class="footer-github" target="_blank"><svg width="16" height="16" viewBox="0 0 24 24" style="vertical-align: middle; margin-right: 4px;"><path fill="currentColor" d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z"/></svg>GitHub</a></li>'
        html = html.replace('<ul class="footer-links" id="footerCol1Links"></ul>',
                          f'<ul class="footer-links">{col1_links}</ul>')
        html = html.replace('<ul class="footer-links" id="footerCol2Links"></ul>',
                          f'<ul class="footer-links">{col2_links}</ul>')
        html = html.replace('<ul class="footer-links" id="footerCol3Links"></ul>',
                          f'<ul class="footer-links">{col3_links}</ul>')
        if footer.get('copyright'):
            html = html.replace('<p id="footerCopyright">&copy; 星社. All rights reserved.</p>',
                              f'<p>&copy; {footer["copyright"]} 星社. All rights reserved.</p>')

        # 静态页面不需要data-loader.js（内容已内嵌）
        html = html.replace('<script src="js/data-loader.js"></script>\n', '')

        # 如果详情页在 pages/ 子目录下，修正资源路径
        if in_pages_dir:
            html = _fix_resource_paths_for_pages(html)
            html = _fix_internal_paths_in_content(html)

        response = Response(html, mimetype='text/html')
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        return response

    return "详情页模板未找到", 500


# ==================== 静态导出 API ====================

if EXPORTER_AVAILABLE:
    # 导出路由登记
    add_export_routes(app)

    @app.route('/api/export/status', methods=['GET'])
    def export_status():
        """获取导出模块状态"""
        return jsonify({
            'available': True,
            'data_file': DATA_FILE,
            'data_exists': os.path.exists(DATA_FILE)
        })
else:
    @app.route('/api/export/status', methods=['GET'])
    def export_status_unavailable():
        return jsonify({
            'available': False,
            'message': '导出模块未安装，请运行: pip install jinja2'
        }), 503

    @app.route('/api/export', methods=['POST'])
    @app.route('/api/export/<page>', methods=['POST'])
    def export_disabled(page=None):
        return jsonify({
            'success': False,
            'error': '导出模块未安装'
        }), 503

    @app.route('/api/export/download', methods=['GET'])
    def download_export_disabled():
        return jsonify({
            'success': False,
            'error': '导出模块未安装'
        }), 503


# ==================== 启动服务器 ====================

def run_server(port=10240):
    """运行服务器"""
    # 确保 data 目录存在
    data_dir = os.path.join(SITE_ROOT, 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
        print(f"  已创建数据目录: {data_dir}")

    if not os.path.exists(DATA_FILE):
        print(f"  警告: 数据文件不存在，将使用默认数据")

    export_info = "[ON]" if EXPORTER_AVAILABLE else "[OFF] pip install jinja2"

    print(f"===========================================")
    print(f"  StarClub Website Admin v0.9")
    print(f"===========================================")
    print(f"  Frontend:   http://localhost:{port}/")
    print(f"  Backend:    http://localhost:{port}/admin/index.html")
    print(f"  Data File:  {DATA_FILE}")
    print(f"  Exporter:   {export_info}")
    print(f"===========================================")
    print(f"  Press Ctrl+C to stop")
    print(f"===========================================")

    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)


if __name__ == '__main__':
    import sys

    port = 10240
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"无效的端口号: {sys.argv[1]}，使用默认端口 {port}")

    run_server(port)
