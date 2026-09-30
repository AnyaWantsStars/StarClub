# -*- coding: utf-8 -*-
import os
import json
import secrets
import base64
import time
import requests
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session, make_response
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
app.secret_key = Config.SECRET_KEY

DATA_DIR = Config.DATA_DIR
USERS_FILE = Config.USERS_FILE
SERVICES_FILE = Config.SERVICES_FILE
MODULES_FILE = os.path.join(DATA_DIR, 'modules.json')
SETTINGS_FILE = os.path.join(DATA_DIR, 'settings.json')

# 一次性交换码存储（code → {token, expires}），60秒过期
auth_codes = {}

def cleanup_expired_auth_codes():
    """清理过期的交换码"""
    now = time.time()
    expired = [code for code, entry in auth_codes.items() if entry['expires'] < now]
    for code in expired:
        del auth_codes[code]

os.makedirs(DATA_DIR, exist_ok=True)

def get_allowed_origins():
    """从 services.json 动态获取允许跨域的子服务来源"""
    origins = set()
    services = load_json(SERVICES_FILE, [])
    for s in services:
        url = s.get('url', '')
        if url:
            # 解析 URL 获取 origin (protocol://host:port)
            from urllib.parse import urlparse
            parsed = urlparse(url)
            if parsed.netloc:
                origin = f"{parsed.scheme}://{parsed.netloc}"
                origins.add(origin)
    return list(origins)

@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin', '')
    allowed_origins = get_allowed_origins()
    if origin in allowed_origins:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

def is_allowed_next_url(next_url):
    """校验 next_url 是否属于已登记的子服务，防止开放重定向攻击"""
    if not next_url:
        return True
    from urllib.parse import urlparse
    parsed = urlparse(next_url)
    if not parsed.netloc:
        return True  # 相对路径，允许
    # 允许当前服务自身
    if parsed.netloc in ('127.0.0.1:10241', 'localhost:10241', 'service.starclub.example.com'):
        return True
    # 检查是否在已登记子服务列表中
    services = load_json(SERVICES_FILE, [])
    for s in services:
        s_url = s.get('url', '')
        if s_url:
            s_parsed = urlparse(s_url)
            if s_parsed.netloc == parsed.netloc:
                return True
    return False

def get_visible_services(user):
    """根据用户身份过滤可见服务列表（公共逻辑）"""
    services = load_json(SERVICES_FILE, [])
    modules = load_json(MODULES_FILE, [])
    visible_services = []

    for s in services:
        if not s.get('display', True):
            continue
        # 检查所属模块是否允许显示
        module_id = s.get('module_id')
        if module_id:
            module = next((m for m in modules if m['id'] == module_id), None)
            if module and not module.get('display', True):
                continue
            if module and module.get('type') == 'private':
                if not user or (user['user_type'] != 'super_admin' and user['id'] not in module.get('visible_to', [])):
                    continue
            elif module and module.get('type') == 'internal':
                if not user:
                    continue

        if s['type'] == 'public':
            visible_services.append(s)
        elif user:
            if s['type'] == 'internal':
                visible_services.append(s)
            elif s['type'] == 'private':
                if user['id'] in s.get('visible_to', []) or user['user_type'] == 'super_admin':
                    visible_services.append(s)

    visible_services.sort(key=lambda x: x.get('order', 0))
    return visible_services

@app.route('/api/jwt/sign', methods=['OPTIONS'])
@app.route('/api/user/info', methods=['OPTIONS'])
@app.route('/api/jwt/verify', methods=['OPTIONS'])
def handle_options():
    origin = request.headers.get('Origin', '')
    allowed_origins = get_allowed_origins()
    if origin in allowed_origins:
        response = make_response('', 204)
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, POST, OPTIONS'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        return response
    return '', 204

@app.route('/api/health')
def api_health():
    return jsonify({'status': 'ok', 'service': 'service-portal'})

def load_json(filepath, default):
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        app.logger.error(f'加载 JSON 文件失败 {filepath}: {e}')
    return default

def save_json(filepath, data):
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except IOError as e:
        app.logger.error(f'保存 JSON 文件失败 {filepath}: {e}')
        raise

def get_current_user():
    if 'user_id' in session:
        users = load_json(USERS_FILE, [])
        for user in users:
            if user['id'] == session['user_id']:
                if user.get('banned'):
                    return None
                return user
    return None

def require_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'message': '请先登录'}), 401
        return f(*args, **kwargs)
    return decorated_function

def require_user_type(*user_types):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = get_current_user()
            if not user:
                return jsonify({'success': False, 'message': '请先登录'}), 401
            if user['user_type'] not in user_types and user['user_type'] != 'super_admin':
                return jsonify({'success': False, 'message': '权限不足'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

USER_TYPES = {
    'regular': '普通用户',
    'service_manager': '服务管理',
    'user_manager': '用户管理',
    'platform_manager': '平台管理',
    'super_admin': '超级管理'
}

SERVICE_TYPES = {
    'public': '公开服务',
    'internal': '内部服务',
    'private': '专属服务'
}

MODULE_TYPES = {
    'public': '公开模块',
    'internal': '内部模块',
    'private': '专属模块'
}

def load_settings():
    default = {'jwt_expiration_hours': 6}
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, 'r', encoding='utf-8') as f:
            settings = json.load(f)
            for k, v in default.items():
                if k not in settings:
                    settings[k] = v
            return settings
    return default

def save_settings(data):
    with open(SETTINGS_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

@app.route('/')
def index():
    user = get_current_user()
    visible_services = get_visible_services(user)
    return render_template('index.html', user=user, services=visible_services,
                           user_types=USER_TYPES, service_types=SERVICE_TYPES)

@app.route('/service/<path:embed_path>')
def service_embed(embed_path):
    """子服务全屏嵌入页：通过嵌入路径名查找对应服务，以全屏 iframe 展示"""
    services = load_json(SERVICES_FILE, [])
    service = next((s for s in services if s.get('embed_path') == embed_path and s.get('embed', True)), None)
    if not service:
        return render_template('index.html', user=None, services=[], error='服务不存在或未启用嵌入'), 404
    return render_template('service_embed.html', service_name=service['name'], service_url=service['url'])

@app.route('/login')
def login():
    """OAuth 登录入口，直接跳转到 Nextcloud 进行授权"""
    next_url = request.args.get('next', '')
    error = request.args.get('error', '')

    # 校验 next_url 白名单，防止开放重定向攻击
    if not is_allowed_next_url(next_url):
        next_url = ''

    # 如果有错误信息（来自 callback 失败），显示登录页让用户看到错误并重试
    if error:
        return render_template('login.html', oauth_enabled=Config.NEXTCLOUD_OAUTH_ENABLED, next=next_url, error=error)

    # 已登录 + 有 next_url → 签发一次性交换码后跳转子服务
    if Config.NEXTCLOUD_OAUTH_ENABLED and next_url:
        user = get_current_user()
        if user and not user.get('banned'):
            from jwt_utils import generate_token
            jwt_token = generate_token(user['id'], user.get('display_name', user['username']), user['user_type'], user.get('email', ''))
            code = secrets.token_urlsafe(32)
            auth_codes[code] = {'token': jwt_token, 'expires': time.time() + 60}
            separator = '&' if '?' in next_url else '?'
            return render_template('auth_loading.html',
                                   redirect_url=f"{next_url}{separator}code={code}",
                                   title='认证完成',
                                   message='正在跳转回服务页面...')

    if Config.NEXTCLOUD_OAUTH_ENABLED:
        state_token = secrets.token_urlsafe(32)
        state_data = json.dumps({'t': state_token, 'n': next_url})
        state = base64.urlsafe_b64encode(state_data.encode()).decode()
        session['oauth_state'] = state_token
        authorize_url = (f"{Config.NEXTCLOUD_OAUTH_AUTHORIZE_URL}"
                        f"?client_id={Config.NEXTCLOUD_OAUTH_CLIENT_ID}"
                        f"&redirect_uri={url_for('auth_callback', _external=True)}"
                        f"&response_type=code"
                        f"&scope=openid"
                        f"&state={state}")
        return render_template('auth_loading.html',
                               redirect_url=authorize_url,
                               title='正在跳转认证服务',
                               message='即将跳转至 Nextcloud 进行身份验证...')
    return render_template('login.html', oauth_enabled=Config.NEXTCLOUD_OAUTH_ENABLED, next=next_url)

@app.route('/oauth/callback')
def auth_callback():
    """OAuth 回调处理，完成用户认证后重定向"""
    next_url = ''

    # 从 state 中提取 next_url（state 格式: base64(json{t: token, n: next_url})）
    state_raw = request.args.get('state', '')
    try:
        state_data = json.loads(base64.urlsafe_b64decode(state_raw.encode()))
        state_token = state_data.get('t', '')
        next_url = state_data.get('n', '')
    except Exception:
        state_token = state_raw

    if not is_allowed_next_url(next_url):
        next_url = ''

    def _fail(msg):
        """失败时重定向回登录入口，保留 next 参数和错误信息"""
        return redirect(url_for('login', error=msg, next=next_url))

    if not Config.NEXTCLOUD_OAUTH_ENABLED:
        return _fail('OAuth未启用')

    state = request.args.get('state')
    code = request.args.get('code')
    error = request.args.get('error')

    if error:
        return _fail(f'OAuth错误: {error}')

    if state_token != session.get('oauth_state'):
        return _fail('状态验证失败，请重新登录')

    try:
        token_response = requests.post(
            Config.NEXTCLOUD_OAUTH_TOKEN_URL,
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': url_for('auth_callback', _external=True),
            },
            auth=(Config.NEXTCLOUD_OAUTH_CLIENT_ID, Config.NEXTCLOUD_OAUTH_CLIENT_SECRET),
            headers={'Accept': 'application/json'}
        )

        if token_response.status_code != 200:
            return _fail(f'Token请求失败 (HTTP {token_response.status_code})')

        try:
            token_data = token_response.json()
        except Exception:
            return _fail('Token响应解析失败')

        if 'access_token' not in token_data:
            return _fail(f'获取访问令牌失败: {token_data.get("error", "unknown")}')

        access_token = token_data['access_token']
        headers = {'Authorization': f'Bearer {access_token}', 'OCS-APIRequest': 'true'}
        user_response = requests.get(Config.NEXTCLOUD_OAUTH_USERINFO_URL, headers=headers)

        if user_response.status_code != 200:
            return _fail(f'用户信息请求失败 (HTTP {user_response.status_code})')

        try:
            user_ocs = user_response.json()
        except Exception:
            return _fail('用户信息解析失败')

        if user_ocs.get('ocs', {}).get('meta', {}).get('status') != 'ok':
            return _fail('获取用户信息失败')

        user_data = user_ocs['ocs']['data']
        oauth_id = user_data.get('id', '')
        username = user_data.get('id', '')
        display_name = user_data.get('display-name', username)
        email = user_data.get('email', '')

        users = load_json(USERS_FILE, [])
        user_obj = None

        for u in users:
            if u.get('oauth_id') == oauth_id:
                user_obj = u
                # 每次 OAuth 登录时同步 Nextcloud 的用户信息
                updated = False
                if display_name and display_name != u.get('display_name', ''):
                    u['display_name'] = display_name
                    updated = True
                if email and email != u.get('email', ''):
                    u['email'] = email
                    updated = True
                if updated:
                    save_json(USERS_FILE, users)
                break

        if not user_obj:
            for u in users:
                if u.get('username') == username and u.get('oauth_id') is None:
                    user_obj = u
                    user_obj['oauth_id'] = oauth_id
                    user_obj['display_name'] = display_name
                    user_obj['email'] = email
                    save_json(USERS_FILE, users)
                    break

        if not user_obj:
            existing_ids = [u['id'] for u in users]
            new_id = oauth_id
            counter = 1
            while new_id in existing_ids:
                new_id = f"{oauth_id}_{counter}"
                counter += 1

            # 只有第一个 username 为 'admin' 的用户才会被识别为超级管理员
            has_existing_super_admin = any(u.get('user_type') == 'super_admin' for u in users)
            user_type = 'super_admin' if (username == 'admin' and not has_existing_super_admin) else 'regular'

            user_obj = {
                'id': new_id,
                'username': username,
                'display_name': display_name,
                'email': email,
                'user_type': user_type,
                'banned': False,
                'allowed_services': [],
                'created_at': datetime.now().isoformat(),
                'oauth_id': oauth_id
            }
            users.append(user_obj)
            save_json(USERS_FILE, users)

        if user_obj.get('banned'):
            return _fail('该用户已被禁用')

        session['user_id'] = user_obj['id']
        session.pop('oauth_state', None)

        # 生成 JWT，用一次性交换码替代直接放 URL（避免个人信息泄露）
        from jwt_utils import generate_token
        jwt_token = generate_token(user_obj['id'], user_obj.get('display_name', user_obj['username']), user_obj['user_type'], user_obj.get('email', ''))
        code = secrets.token_urlsafe(32)
        auth_codes[code] = {'token': jwt_token, 'expires': time.time() + 60}

        if next_url:
            separator = '&' if '?' in next_url else '?'
            return render_template('auth_loading.html',
                                   redirect_url=f"{next_url}{separator}code={code}",
                                   title='认证完成',
                                   message='正在跳转回服务页面...')
        return render_template('auth_loading.html',
                               redirect_url=url_for('index', _external=True),
                               title='认证完成',
                               message='正在跳转至首页...')

    except Exception as e:
        return _fail(f'认证失败: {str(e)[:100]}')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/api/auth/exchange', methods=['POST'])
def api_auth_exchange():
    """子服务后端用一次性交换码换取 JWT（code 用完即销毁）"""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'message': '请求参数无效'}), 400

    code = data.get('code', '')
    if not code:
        return jsonify({'success': False, 'message': '缺少 code 参数'}), 400

    cleanup_expired_auth_codes()
    entry = auth_codes.pop(code, None)
    if not entry:
        return jsonify({'success': False, 'message': '交换码无效或已被使用'}), 400

    if time.time() > entry['expires']:
        return jsonify({'success': False, 'message': '交换码已过期'}), 400

    return jsonify({'success': True, 'token': entry['token']})

@app.route('/admin')
@app.route('/admin/<section>')
def admin(section=None):
    user = get_current_user()
    if not user:
        return redirect(url_for('login'))
    if user['user_type'] not in ['service_manager', 'user_manager', 'platform_manager', 'super_admin']:
        return "无权限访问管理后台", 403
    users = load_json(USERS_FILE, [])
    services = load_json(SERVICES_FILE, [])
    return render_template('admin.html', user=user, users=users, services=services,
                           user_types=USER_TYPES, service_types=SERVICE_TYPES, module_types=MODULE_TYPES)

@app.route('/api/user/info')
@require_login
def api_user_info():
    user = get_current_user()
    return jsonify({'success': True, 'user': {
        'id': user['id'],
        'username': user['username'],
        'display_name': user.get('display_name', user['username']),
        'email': user.get('email', ''),
        'user_type': user['user_type'],
        'user_type_name': USER_TYPES.get(user['user_type'], user['user_type'])
    }})

@app.route('/api/users', methods=['GET'])
@require_login
def api_get_users():
    user = get_current_user()
    if user['user_type'] not in ['user_manager', 'platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    users = load_json(USERS_FILE, [])
    result = []
    for u in users:
        result.append({
            'id': u['id'],
            'username': u['username'],
            'display_name': u.get('display_name', u['username']),
            'user_type': u['user_type'],
            'user_type_name': USER_TYPES.get(u['user_type'], u['user_type']),
            'banned': u.get('banned', False),
            'created_at': u.get('created_at', '')
        })
    return jsonify({'success': True, 'users': result})

@app.route('/api/users', methods=['POST'])
@require_login
def api_create_user():
    user = get_current_user()
    if user['user_type'] not in ['user_manager', 'platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    data = request.get_json()
    username = data.get('username', '').strip()
    display_name = data.get('display_name', username)
    user_type = data.get('user_type', 'regular')
    allowed_user_types = ['regular']
    if user['user_type'] in ['user_manager']:
        allowed_user_types = ['regular']
    elif user['user_type'] in ['platform_manager']:
        allowed_user_types = ['regular', 'service_manager', 'user_manager']
    elif user['user_type'] == 'super_admin':
        allowed_user_types = ['regular', 'service_manager', 'user_manager', 'platform_manager']

    if user_type not in allowed_user_types:
        return jsonify({'success': False, 'message': '无权设置该用户类型'}), 403

    if not username:
        return jsonify({'success': False, 'message': '用户名不能为空'}), 400

    users = load_json(USERS_FILE, [])
    if any(u['username'] == username for u in users):
        return jsonify({'success': False, 'message': '用户名已存在'}), 400

    existing_ids = [u['id'] for u in users]
    new_id = username
    counter = 1
    while new_id in existing_ids:
        new_id = f"{username}_{counter}"
        counter += 1

    new_user = {
        'id': new_id,
        'username': username,
        'display_name': display_name,
        'user_type': user_type,
        'banned': False,
        'allowed_services': [],
        'created_at': datetime.now().isoformat(),
        'oauth_id': None
    }
    users.append(new_user)
    save_json(USERS_FILE, users)
    return jsonify({'success': True, 'message': '用户创建成功', 'user': new_user})

@app.route('/api/users/<user_id>', methods=['PUT'])
@require_login
def api_update_user(user_id):
    current_user = get_current_user()
    if current_user['user_type'] not in ['user_manager', 'platform_manager', 'super_admin'] and current_user['user_type'] != 'super_admin':
        return jsonify({'success': False, 'message': '权限不足'}), 403

    users = load_json(USERS_FILE, [])
    user_idx = None
    for i, u in enumerate(users):
        if u['id'] == user_id:
            user_idx = i
            break

    if user_idx is None:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    target_user = users[user_idx]

    if target_user['user_type'] == 'super_admin' and current_user['user_type'] != 'super_admin':
        return jsonify({'success': False, 'message': '无权修改超级管理员'}), 403

    if current_user['user_type'] == 'user_manager' and target_user['user_type'] != 'regular':
        return jsonify({'success': False, 'message': '权限不足'}), 403

    data = request.get_json()

    if 'display_name' in data:
        target_user['display_name'] = data['display_name'].strip()

    if 'banned' in data:
        if target_user['id'] == current_user['id']:
            return jsonify({'success': False, 'message': '不能禁用自己'}), 400
        target_user['banned'] = data['banned']

    if 'user_type' in data:
        new_type = data['user_type']
        if target_user['user_type'] == 'super_admin':
            return jsonify({'success': False, 'message': '不能修改超级管理员类型'}), 403

        if new_type == 'super_admin':
            return jsonify({'success': False, 'message': '无法将用户设为超级管理员'}), 403

        if current_user['user_type'] == 'user_manager' and new_type != 'regular':
            return jsonify({'success': False, 'message': '权限不足'}), 403

        allowed_types = []
        if current_user['user_type'] == 'super_admin':
            allowed_types = ['regular', 'service_manager', 'user_manager', 'platform_manager']
        elif current_user['user_type'] == 'platform_manager':
            allowed_types = ['regular', 'service_manager', 'user_manager', 'platform_manager']
        elif current_user['user_type'] == 'user_manager':
            allowed_types = ['regular']

        if new_type not in allowed_types:
            return jsonify({'success': False, 'message': '无权设置该用户类型'}), 403

        target_user['user_type'] = new_type

    save_json(USERS_FILE, users)
    return jsonify({'success': True, 'message': '用户更新成功'})

@app.route('/api/users/<user_id>', methods=['DELETE'])
@require_login
def api_delete_user(user_id):
    current_user = get_current_user()
    if current_user['user_type'] not in ['user_manager', 'platform_manager', 'super_admin'] and current_user['user_type'] != 'super_admin':
        return jsonify({'success': False, 'message': '权限不足'}), 403

    users = load_json(USERS_FILE, [])
    user_idx = None
    for i, u in enumerate(users):
        if u['id'] == user_id:
            user_idx = i
            break

    if user_idx is None:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    target_user = users[user_idx]

    if target_user['user_type'] == 'super_admin':
        return jsonify({'success': False, 'message': '不能删除超级管理员'}), 403

    if current_user['user_type'] == 'user_manager' and target_user['user_type'] != 'regular':
        return jsonify({'success': False, 'message': '权限不足'}), 403

    users.pop(user_idx)
    save_json(USERS_FILE, users)
    return jsonify({'success': True, 'message': '用户删除成功'})

@app.route('/api/users/<user_id>/ban', methods=['PUT'])
@require_login
def api_ban_user(user_id):
    current_user = get_current_user()
    if current_user['user_type'] not in ['user_manager', 'platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    users = load_json(USERS_FILE, [])
    user_idx = None
    for i, u in enumerate(users):
        if u['id'] == user_id:
            user_idx = i
            break

    if user_idx is None:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    target_user = users[user_idx]

    if target_user['user_type'] == 'super_admin':
        return jsonify({'success': False, 'message': '不能禁用超级管理员'}), 403

    if target_user['id'] == current_user['id']:
        return jsonify({'success': False, 'message': '不能禁用自己'}), 400

    if current_user['user_type'] == 'user_manager' and target_user['user_type'] != 'regular':
        return jsonify({'success': False, 'message': '权限不足'}), 403

    data = request.get_json()
    users[user_idx]['banned'] = data.get('banned', False)
    save_json(USERS_FILE, users)
    return jsonify({'success': True, 'message': '操作成功'})

@app.route('/api/services', methods=['GET'])
def api_get_services():
    user = get_current_user()
    visible_services = get_visible_services(user)
    visible_module_ids = set(s.get('module_id') for s in visible_services if s.get('module_id'))
    modules = load_json(MODULES_FILE, [])
    visible_modules = [m for m in modules if m['id'] in visible_module_ids and m.get('display', True)]
    visible_modules.sort(key=lambda x: x.get('order', 0))

    for m in visible_modules:
        m['services'] = [s for s in visible_services if s.get('module_id') == m['id']]

    unmodule_services = [s for s in visible_services if not s.get('module_id')]

    return jsonify({'success': True, 'services': visible_services, 'modules': visible_modules, 'unmodule_services': unmodule_services})

@app.route('/api/admin/services', methods=['GET'])
@require_login
def api_admin_get_services():
    user = get_current_user()
    if user['user_type'] not in ['service_manager', 'platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    services = load_json(SERVICES_FILE, [])
    return jsonify({'success': True, 'services': services})

@app.route('/api/admin/services', methods=['POST'])
@require_login
def api_create_service():
    user = get_current_user()
    if user['user_type'] not in ['service_manager', 'platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '服务名称不能为空'}), 400

    services = load_json(SERVICES_FILE, [])
    service_id = f"service_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}"

    new_service = {
        'id': service_id,
        'name': name,
        'description': data.get('description', ''),
        'icon': data.get('icon', '🔗'),
        'url': data.get('url', '#'),
        'type': data.get('type', 'public'),
        'visible_to': data.get('visible_to', []),
        'display': True,
        'order': len(services) + 1,
        'module_id': data.get('module_id') or None,
        'embed': data.get('embed', True),
        'embed_path': data.get('embed_path', '').strip() or None,
        'created_at': datetime.now().isoformat()
    }
    services.append(new_service)
    save_json(SERVICES_FILE, services)
    return jsonify({'success': True, 'message': '服务创建成功', 'service': new_service})

@app.route('/api/admin/services/<service_id>', methods=['PUT'])
@require_login
def api_update_service(service_id):
    user = get_current_user()
    if user['user_type'] not in ['service_manager', 'platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    services = load_json(SERVICES_FILE, [])
    service_idx = None
    for i, s in enumerate(services):
        if s['id'] == service_id:
            service_idx = i
            break

    if service_idx is None:
        return jsonify({'success': False, 'message': '服务不存在'}), 404

    data = request.get_json()
    service = services[service_idx]

    if 'name' in data:
        service['name'] = data['name'].strip()
    if 'description' in data:
        service['description'] = data['description']
    if 'icon' in data:
        service['icon'] = data['icon']
    if 'url' in data:
        service['url'] = data['url']
    if 'type' in data:
        service['type'] = data['type']
    if 'visible_to' in data:
        service['visible_to'] = data['visible_to']
    if 'display' in data:
        service['display'] = data['display']
    if 'order' in data:
        service['order'] = data['order']
    if 'module_id' in data:
        service['module_id'] = data['module_id'] or None
    if 'embed' in data:
        service['embed'] = data['embed']
    if 'embed_path' in data:
        service['embed_path'] = data['embed_path'].strip() or None

    save_json(SERVICES_FILE, services)
    return jsonify({'success': True, 'message': '服务更新成功'})

@app.route('/api/admin/services/<service_id>', methods=['DELETE'])
@require_login
def api_delete_service(service_id):
    user = get_current_user()
    if user['user_type'] not in ['service_manager', 'platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    services = load_json(SERVICES_FILE, [])
    service_idx = None
    for i, s in enumerate(services):
        if s['id'] == service_id:
            service_idx = i
            break

    if service_idx is None:
        return jsonify({'success': False, 'message': '服务不存在'}), 404

    services.pop(service_idx)
    save_json(SERVICES_FILE, services)
    return jsonify({'success': True, 'message': '服务删除成功'})

@app.route('/api/admin/services/reorder', methods=['PUT'])
@require_login
def api_reorder_services():
    user = get_current_user()
    if user['user_type'] not in ['service_manager', 'platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    data = request.get_json()
    ordered_ids = data.get('order', [])

    services = load_json(SERVICES_FILE, [])
    for i, sid in enumerate(ordered_ids):
        for s in services:
            if s['id'] == sid:
                s['order'] = i
                break
    save_json(SERVICES_FILE, services)
    return jsonify({'success': True, 'message': '排序更新成功'})

@app.route('/api/admin/modules', methods=['GET'])
@require_login
def api_get_modules():
    user = get_current_user()
    if user['user_type'] not in ['service_manager', 'platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    modules = load_json(MODULES_FILE, [])
    modules.sort(key=lambda x: x.get('order', 0))
    return jsonify({'success': True, 'modules': modules})

@app.route('/api/admin/modules', methods=['POST'])
@require_login
def api_create_module():
    user = get_current_user()
    if user['user_type'] not in ['service_manager', 'platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    data = request.get_json()
    name = data.get('name', '').strip()
    if not name:
        return jsonify({'success': False, 'message': '模块名称不能为空'}), 400

    modules = load_json(MODULES_FILE, [])
    module_id = f"module_{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}"

    new_module = {
        'id': module_id,
        'name': name,
        'icon': data.get('icon', '📁'),
        'order': len(modules) + 1,
        'type': data.get('type', 'public'),
        'display': data.get('display', True),
        'visible_to': data.get('visible_to', [])
    }
    modules.append(new_module)
    save_json(MODULES_FILE, modules)
    return jsonify({'success': True, 'message': '模块创建成功', 'module': new_module})

@app.route('/api/admin/modules/<module_id>', methods=['PUT'])
@require_login
def api_update_module(module_id):
    user = get_current_user()
    if user['user_type'] not in ['service_manager', 'platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    modules = load_json(MODULES_FILE, [])
    module_idx = None
    for i, m in enumerate(modules):
        if m['id'] == module_id:
            module_idx = i
            break

    if module_idx is None:
        return jsonify({'success': False, 'message': '模块不存在'}), 404

    data = request.get_json()
    module = modules[module_idx]

    if 'name' in data:
        module['name'] = data['name'].strip()
    if 'icon' in data:
        module['icon'] = data['icon']
    if 'order' in data:
        module['order'] = data['order']
    if 'type' in data:
        module['type'] = data['type']
    if 'display' in data:
        module['display'] = data['display']
    if 'visible_to' in data:
        module['visible_to'] = data['visible_to']

    save_json(MODULES_FILE, modules)
    return jsonify({'success': True, 'message': '模块更新成功'})

@app.route('/api/admin/modules/<module_id>', methods=['DELETE'])
@require_login
def api_delete_module(module_id):
    user = get_current_user()
    if user['user_type'] not in ['service_manager', 'platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    modules = load_json(MODULES_FILE, [])
    module_idx = None
    for i, m in enumerate(modules):
        if m['id'] == module_id:
            module_idx = i
            break

    if module_idx is None:
        return jsonify({'success': False, 'message': '模块不存在'}), 404

    modules.pop(module_idx)
    save_json(MODULES_FILE, modules)

    services = load_json(SERVICES_FILE, [])
    for s in services:
        if s.get('module_id') == module_id:
            s['module_id'] = None
    save_json(SERVICES_FILE, services)

    return jsonify({'success': True, 'message': '模块删除成功'})

@app.route('/api/admin/modules/reorder', methods=['PUT'])
@require_login
def api_reorder_modules():
    user = get_current_user()
    if user['user_type'] not in ['service_manager', 'platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    data = request.get_json()
    ordered_ids = data.get('order', [])

    modules = load_json(MODULES_FILE, [])
    for i, mid in enumerate(ordered_ids):
        for m in modules:
            if m['id'] == mid:
                m['order'] = i
                break
    save_json(MODULES_FILE, modules)
    return jsonify({'success': True, 'message': '排序更新成功'})

@app.route('/api/jwt/sign', methods=['POST'])
@require_login
def api_jwt_sign():
    user = get_current_user()
    if user.get('banned'):
        return jsonify({'success': False, 'message': '用户已被禁用'}), 403

    from jwt_utils import generate_token, get_expiration_hours
    settings = load_settings()
    hours = get_expiration_hours(settings)
    token = generate_token(user['id'], user.get('display_name', user['username']), user['user_type'], user.get('email', ''), hours)
    return jsonify({'success': True, 'token': token})

@app.route('/api/jwt/verify', methods=['POST'])
def api_jwt_verify():
    data = request.get_json()
    token = data.get('token')

    if not token:
        return jsonify({'success': False, 'message': '缺少token参数'}), 400

    from jwt_utils import verify_token
    payload = verify_token(token)

    if not payload:
        return jsonify({'success': False, 'message': 'token无效或已过期'}), 401

    return jsonify({'success': True, 'payload': payload})

@app.route('/api/permission/check', methods=['POST'])
def api_permission_check():
    """检查用户是否有权限访问指定服务（子服务后端调用）"""
    data = request.get_json()
    token = data.get('token')
    service_port = data.get('service_port')

    if not token:
        return jsonify({'success': False, 'message': '缺少 token 参数'}), 400
    if not service_port:
        return jsonify({'success': False, 'message': '缺少 service_port 参数'}), 400

    from jwt_utils import verify_token
    payload = verify_token(token)
    if not payload:
        return jsonify({'success': False, 'message': 'token 无效或已过期'}), 401

    user_id = payload.get('user_id')
    user_type = payload.get('user_type')

    users = load_json(USERS_FILE, [])
    user = None
    for u in users:
        if u['id'] == user_id:
            user = u
            break

    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404
    if user.get('banned'):
        return jsonify({'success': False, 'message': '用户已被禁用'}), 403

    services = load_json(SERVICES_FILE, [])
    from urllib.parse import urlparse
    try:
        target_port = int(service_port)
    except (ValueError, TypeError):
        return jsonify({'success': False, 'message': '无效的 service_port 参数'}), 400
    target_service = None
    for s in services:
        # 优先匹配 service_port 字段
        if s.get('service_port') == target_port:
            target_service = s
            break
        # 兜底：从 URL 解析端口
        url = s.get('url', '')
        if url:
            parsed = urlparse(url)
            if parsed.port == target_port:
                target_service = s
                break

    if not target_service:
        return jsonify({'success': False, 'message': '服务不存在'}), 404

    service_type = target_service.get('type', 'public')
    visible_to = target_service.get('visible_to', [])

    if service_type == 'public':
        allowed = True
    elif service_type == 'internal':
        allowed = True
    elif service_type == 'private':
        allowed = user['id'] in visible_to or user_type == 'super_admin'
    else:
        allowed = False

    return jsonify({
        'success': True,
        'allowed': allowed,
        'service': {
            'id': target_service['id'],
            'name': target_service.get('name', ''),
            'type': service_type
        },
        'user': {
            'id': user_id,
            'user_type': user_type
        }
    })

@app.route('/api/users/list')
@require_login
def api_users_list():
    user = get_current_user()
    users = load_json(USERS_FILE, [])
    result = []
    for u in users:
        if not u.get('banned', False):
            result.append({
                'id': u['id'],
                'username': u['username'],
                'display_name': u.get('display_name', u['username']),
                'user_type': u.get('user_type', 'regular'),
                'email': u.get('email', '')
            })
    return jsonify({'success': True, 'users': result})

@app.route('/api/admin/settings', methods=['GET'])
@require_login
def api_get_settings():
    current_user = get_current_user()
    if current_user['user_type'] not in ['platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    settings = load_settings()
    return jsonify({'success': True, 'settings': settings})

@app.route('/api/admin/settings', methods=['PUT'])
@require_login
def api_update_settings():
    current_user = get_current_user()
    if current_user['user_type'] not in ['platform_manager', 'super_admin']:
        return jsonify({'success': False, 'message': '权限不足'}), 403
    data = request.get_json()
    settings = load_settings()
    if 'jwt_expiration_hours' in data:
        hours = data['jwt_expiration_hours']
        if not isinstance(hours, (int, float)) or hours <= 0:
            return jsonify({'success': False, 'message': '有效期必须为正数'}), 400
        settings['jwt_expiration_hours'] = hours
    save_settings(settings)
    return jsonify({'success': True, 'message': '设置已保存', 'settings': settings})

if __name__ == '__main__':
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else Config.PORT
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
