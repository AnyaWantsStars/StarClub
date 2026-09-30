"""
共享工具模块
- IP 工具函数
- 通用装饰器 (login_required, admin_required, ip_required)
- 日期范围工具函数
"""
import ipaddress
import re
from functools import wraps
from datetime import datetime, timedelta

from flask import request, session, jsonify, redirect, current_app
from db import user_find_by_user_id, User


# ── IP 工具 ──

def get_client_ip():
    """获取客户端真实IP"""
    if request.headers.get('X-Forwarded-For'):
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    return request.remote_addr


def is_ip_allowed(ip, system_config):
    """检查IP是否在允许的范围内"""
    if not system_config.allowed_ip_ranges:
        return True

    allowed_ranges = [r.strip() for r in system_config.allowed_ip_ranges.split(',') if r.strip()]
    if not allowed_ranges:
        return True

    client_ip_parts = ip.split('.')
    if len(client_ip_parts) != 4:
        return False

    for range_pattern in allowed_ranges:
        range_pattern = range_pattern.strip()

        if '/' in range_pattern:
            try:
                network = ipaddress.IPv4Network(range_pattern, strict=False)
                if ipaddress.IPv4Address(ip) in network:
                    return True
            except (ValueError, ipaddress.AddressValueError):
                continue
        elif range_pattern == ip:
            return True
        elif 'x' in range_pattern.lower():
            pattern = range_pattern.replace('.', '\\.').replace('x', '(\\d{1,3})')
            if re.match(f'^{pattern}$', ip):
                return True

    return False


# ── 通用装饰器 ──

def get_current_user():
    """获取当前登录用户（支持 session 和 JWT Bearer）"""
    if 'user_id' in session:
        session.permanent = True
        return user_find_by_user_id(session['user_id'])

    # 尝试从 JWT Bearer token 获取
    from flask import request
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        import requests as _req
        try:
            r = _req.post(current_app.config['portal_url'] + '/api/jwt/verify', json={'token': token}, timeout=10)
            result = r.json()
            if result.get('success'):
                payload = result['payload']
                user = user_find_by_user_id(payload['user_id'])
                if user:
                    # 每次认证同步用户信息：email 和 username
                    email = payload.get('email', '')
                    if email and email != user.email:
                        user_update(user, email=email)
                    session['user_id'] = user.user_id
                    session.permanent = True
                    return user
        except Exception:
            pass
    return None


def login_required(f):
    """登录验证装饰器：支持 session 和 JWT Bearer"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'message': '请先登录'}), 401
            # 保留 query string 以便传递 code 等参数
            qs = request.query_string.decode('utf-8')
            target = '/login' + ('?' + qs if qs else '')
            return redirect(target)
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """管理员权限验证装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user = get_current_user()
        if not user or user.user_type not in [User.TYPE_ADMIN, User.TYPE_SUPER_ADMIN]:
            return jsonify({'success': False, 'message': '需要管理员权限'}), 403
        return f(*args, **kwargs)
    return decorated


def ip_required(f):
    """IP限制装饰器"""
    @wraps(f)
    def decorated(*args, **kwargs):
        system_config = current_app.config.get('system_config')
        client_ip = get_client_ip()
        if not is_ip_allowed(client_ip, system_config):
            return jsonify({'success': False, 'message': '当前不在签到范围内'}), 403
        return f(*args, **kwargs)
    return decorated


# ── 日期范围工具 ──

def get_week_range():
    today = datetime.now()
    start = today - timedelta(days=today.weekday())
    end = start + timedelta(days=6)
    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


def get_month_range():
    today = datetime.now()
    start = today.replace(day=1)
    if today.month == 12:
        end = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        end = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return start.strftime('%Y-%m-%d'), end.strftime('%Y-%m-%d')


def get_semester_range():
    import calendar
    today = datetime.now()
    year = today.year
    month = today.month
    if month >= 8:
        start_year, start_month = year, 8
        end_year, end_month = year + 1, 1
    elif month >= 2:
        start_year, start_month = year, 2
        end_year, end_month = year, 7
    else:
        start_year, start_month = year - 1, 8
        end_year, end_month = year, 1
    start_date = f"{start_year}-{start_month:02d}-01"
    last_day = calendar.monthrange(end_year, end_month)[1]
    end_date = f"{end_year}-{end_month:02d}-{last_day:02d}"
    return start_date, end_date


# ── 日期时间解析 ──

def parse_datetime(dt_str):
    """兼容多种日期时间格式 (T分隔 和 空格分隔)"""
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(dt_str)


# ── 排名用户过滤 ──

def filter_user_for_ranking(user_id):
    """检查用户是否应该出现在排名中（排除不存在/禁用/锁定/管理员）"""
    user = user_find_by_user_id(user_id)
    if not user:
        return False
    if user.status in [User.STATUS_DISABLED, User.STATUS_LOCKED]:
        return False
    if user.user_type in [User.TYPE_ADMIN, User.TYPE_SUPER_ADMIN]:
        return False
    return True