# -*- coding: utf-8 -*-
import os
import secrets
import requests
from flask import Flask, render_template, jsonify, request
import jwt

app = Flask(__name__)
app.secret_key = os.environ.get('SUB_SERVICE_SECRET_KEY', secrets.token_hex(32))  # 生产环境必须通过环境变量注入
from config import CONFIG

# Service Portal 配置
PORTAL_URL = CONFIG['portal_url']
JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', '')
JWT_ALGORITHM = 'HS256'

def verify_token(token):
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

@app.route('/')
def index():
    return render_template('sub_service_index.html')

@app.route('/api/jwt/verify', methods=['POST'])
def api_jwt_verify():
    """调用 Portal 的 JWT 验证接口"""
    data = request.get_json()
    token = data.get('token')

    if not token:
        return jsonify({'success': False, 'message': '缺少 token 参数'}), 400

    try:
        response = requests.post(
            f'{PORTAL_URL}/api/jwt/verify',
            json={'token': token},
            timeout=5
        )
        result = response.json()
        return jsonify(result)
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'message': '无法连接到 Portal 服务'}), 503
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/jwt/verify/local', methods=['POST'])
def api_jwt_verify_local():
    """本地验证 JWT（使用相同的密钥）"""
    data = request.get_json()
    token = data.get('token')

    if not token:
        return jsonify({'success': False, 'message': '缺少 token 参数'}), 400

    payload = verify_token(token)
    if payload:
        return jsonify({'success': True, 'payload': payload, 'method': 'local'})
    else:
        return jsonify({'success': False, 'message': 'token 无效或已过期', 'method': 'local'}), 400

@app.route('/api/auth/exchange', methods=['POST'])
def api_auth_exchange():
    """用一次性交换码向 Portal 换取 JWT"""
    data = request.get_json()
    code = data.get('code')

    if not code:
        return jsonify({'success': False, 'message': '缺少 code 参数'}), 400

    try:
        response = requests.post(
            f'{PORTAL_URL}/api/auth/exchange',
            json={'code': code},
            timeout=5
        )
        return jsonify(response.json())
    except requests.exceptions.ConnectionError:
        return jsonify({'success': False, 'message': '无法连接到 Portal 服务'}), 503
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

if __name__ == '__main__':
    print('=' * 50)
    print('JWT 认证测试子服务')
    print('=' * 50)
    print(f'访问地址: http://localhost:10241')
    print(f'Portal 地址: {PORTAL_URL}')
    print('=' * 50)
    app.run(host='0.0.0.0', port=10241, debug=True)
