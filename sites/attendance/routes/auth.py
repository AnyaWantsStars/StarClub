"""
认证相关路由 - JWT认证
- 自动重定向到Portal（无需点击）
- JWT exchange/verify
- 首次登录引导填写真实姓名
- 登出 / 当前用户信息
"""
from flask import Blueprint, request, redirect, session, jsonify, render_template
from datetime import datetime
import requests

from config import SystemConfig
from db import (
    User, user_find_by_oauth_id, user_find_by_user_id, user_create, user_update,
    record_get_by_user, record_update, AttendanceRecord
)
from tool_func import get_current_user

auth_bp = Blueprint('auth', __name__)

_sys_cfg = SystemConfig()
PORTAL_URL = _sys_cfg.portal_url
SERVICE_PORT = _sys_cfg.service_port


# ── JWT 工具函数 ──

def verify_jwt(token):
    """向 Portal 验证 JWT Token"""
    try:
        r = requests.post(f'{PORTAL_URL}/api/jwt/verify', json={'token': token}, timeout=10)
        return r.json()
    except Exception as e:
        return {'success': False, 'message': f'无法连接到 Portal: {type(e).__name__}'}


def check_permission(token):
    """向 Portal 检查平台权限"""
    try:
        r = requests.post(f'{PORTAL_URL}/api/permission/check',
                          json={'token': token, 'service_port': SERVICE_PORT}, timeout=10)
        return r.json()
    except Exception as e:
        return {'success': False, 'allowed': False, 'message': f'无法连接到 Portal: {type(e).__name__}'}


def register_or_update_user(payload):
    """从JWT payload登记或同步用户信息
    - 新用户：username 用 user_id 占位，需后续填写真实姓名
    - 已存在用户：仅同步 email（displayName 不是真实姓名，不同步 username）
    """
    user_id = payload['user_id']
    email = payload.get('email', '')
    user_type = 'super_admin' if user_id == 'admin' else 'regular'

    user = user_find_by_user_id(user_id)

    if not user:
        # 新用户：username 用 user_id 占位，提醒填写真实姓名
        user_create(
            user_id=user_id,
            username=user_id,  # 占位，后续引导填写真实姓名
            oauth_id=user_id,
            email=email,
            user_type=user_type
        )
    else:
        # 已存在用户：每次登录同步 email，不同步 username（displayName != 真实姓名）
        if email and email != user.email:
            user_update(user, email=email)

    return user_find_by_user_id(user_id)


# ── 路由 ──

@auth_bp.route('/login')
def login_page():
    """登录：自动重定向到 Portal 统一认证（无需用户点击）"""
    if 'user_id' in session:
        return redirect('/attendance')

    # 处理 Portal 回调的 code 参数（服务端 exchange）
    code = request.args.get('code', '')
    if code:
        try:
            resp = requests.post(f'{PORTAL_URL}/api/auth/exchange',
                                 json={'code': code}, timeout=10)
            if resp.text:
                exchange_result = resp.json()
                if exchange_result.get('success') and exchange_result.get('token'):
                    token = exchange_result['token']
                    result = verify_jwt(token)
                    if result.get('success'):
                        payload = result['payload']
                        user = register_or_update_user(payload)
                        if user.status != User.STATUS_DISABLED:
                            session['user_id'] = user.user_id
                            session['jwt_token'] = token
                            session.permanent = True
                            # 检查是否需要填写真实姓名
                            if user.username == user.user_id:
                                return redirect('/set_name')
                            return redirect('/attendance')
        except Exception:
            pass

    # 无 code：自动重定向到 Portal
    return redirect(f'{PORTAL_URL}/login?next={request.host_url}attendance')


@auth_bp.route('/set_name', methods=['GET', 'POST'])
def set_name_page():
    """首次登录引导填写真实姓名"""
    if 'user_id' not in session:
        return redirect('/login')

    user = user_find_by_user_id(session['user_id'])
    if not user:
        return redirect('/login')

    # 如果已有真实姓名，跳过
    if user.username and user.username != user.user_id:
        return redirect('/attendance')

    if request.method == 'POST':
        real_name = request.form.get('real_name', '').strip()
        if real_name:
            user_update(user, username=real_name)
            return redirect('/attendance')
        return render_template('set_name.html', user_id=user.user_id, error='请输入真实姓名')

    return render_template('set_name.html', user_id=user.user_id, error='')


@auth_bp.route('/api/auth/exchange', methods=['POST'])
def api_auth_exchange():
    """用一次性交换码向 Portal 换取 JWT"""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'message': '请求参数无效'}), 400
    code = data.get('code', '')
    if not code:
        return jsonify({'success': False, 'message': '缺少 code 参数'}), 400
    try:
        resp = requests.post(f'{PORTAL_URL}/api/auth/exchange', json={'code': code}, timeout=10)
        if not resp.text:
            return jsonify({'success': False, 'message': 'Portal 返回空响应'}), 502
        result = resp.json()
        return jsonify(result)
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'message': '无法连接到 Portal 服务'}), 503
    except Exception as e:
        return jsonify({'success': False, 'message': 'Portal 响应异常，请稍后重试'}), 502


@auth_bp.route('/api/auth/verify', methods=['POST'])
def api_auth_verify():
    """验证 JWT 并返回用户信息"""
    data = request.get_json()
    token = data.get('token', '')
    if not token:
        return jsonify({'success': False, 'message': '缺少 Token'}), 400

    result = verify_jwt(token)
    if not result.get('success'):
        return jsonify(result), 401

    payload = result['payload']
    user = register_or_update_user(payload)

    if user.status == User.STATUS_DISABLED:
        return jsonify({'success': False, 'message': '用户已被禁用'}), 403

    # 设置 session
    session['user_id'] = user.user_id
    session['jwt_token'] = token
    session.permanent = True

    perm = check_permission(token)
    user_info = {
        'user_id': user.user_id,
        'username': user.username,
        'email': user.email or '',
        'user_type': user.user_type,
        'is_admin': user.user_type in [User.TYPE_ADMIN, User.TYPE_SUPER_ADMIN],
        'is_super_admin': user.user_type == User.TYPE_SUPER_ADMIN,
        'need_set_name': user.username == user.user_id,
    }
    return jsonify({
        'success': True,
        'has_permission': perm.get('allowed', False),
        'user': user_info
    })


@auth_bp.route('/api/auth/update_name', methods=['POST'])
def api_update_name():
    """更新用户真实姓名"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '请先登录'}), 401

    data = request.get_json(silent=True)
    if not data:
        return jsonify({'success': False, 'message': '请求参数无效'}), 400
    real_name = data.get('real_name', '').strip()
    if not real_name:
        return jsonify({'success': False, 'message': '请输入真实姓名'}), 400

    user = user_find_by_user_id(session['user_id'])
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    user_update(user, username=real_name)
    return jsonify({'success': True, 'message': '姓名已更新'})


@auth_bp.route('/logout')
def logout():
    """退出登录"""
    user = get_current_user()
    if user:
        records = record_get_by_user(user.user_id)
        for record in reversed(records):
            if record.check_out is None and record.status == AttendanceRecord.STATUS_VALID:
                record.check_out = datetime.now().isoformat()
                record_update(record)

    session.clear()
    return redirect(f'{PORTAL_URL}/logout')


@auth_bp.route('/api/current_user')
def api_current_user():
    """获取当前用户信息（支持 session 和 JWT Bearer）"""
    if 'user_id' in session:
        user = user_find_by_user_id(session['user_id'])
        if user:
            if user.status == User.STATUS_DISABLED:
                return jsonify({'success': False, 'message': '用户已被禁用'}), 403
            return jsonify({
                'success': True,
                'user': {
                    'user_id': user.user_id,
                    'username': user.username,
                    'email': user.email or '',
                    'user_type': user.user_type,
                    'is_admin': user.user_type in [User.TYPE_ADMIN, User.TYPE_SUPER_ADMIN],
                    'is_super_admin': user.user_type == User.TYPE_SUPER_ADMIN,
                    'need_set_name': user.username == user.user_id,
                }
            })

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        result = verify_jwt(token)
        if result.get('success'):
            payload = result['payload']
            user = register_or_update_user(payload)
            if user.status == User.STATUS_DISABLED:
                return jsonify({'success': False, 'message': '用户已被禁用'}), 403
            return jsonify({
                'success': True,
                'user': {
                    'user_id': user.user_id,
                    'username': user.username,
                    'email': user.email or '',
                    'user_type': user.user_type,
                    'is_admin': user.user_type in [User.TYPE_ADMIN, User.TYPE_SUPER_ADMIN],
                    'is_super_admin': user.user_type == User.TYPE_SUPER_ADMIN,
                    'need_set_name': user.username == user.user_id,
                }
            })

    return jsonify({'success': False, 'message': '请先登录'}), 401
