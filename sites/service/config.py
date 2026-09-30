"""
配置加载器 - 从 config.json 读取所有配置
"""
import os
import json
import secrets

_CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.json')
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
_SECRET_KEY_FILE = os.path.join(_DATA_DIR, '.secret_key')


def _load_json_config():
    if os.path.exists(_CONFIG_FILE):
        try:
            with open(_CONFIG_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"[CONFIG] 读取 config.json 失败: {e}")
    return {}


def _load_secret_key():
    key = os.environ.get('SECRET_KEY')
    if key:
        return key
    try:
        with open(_SECRET_KEY_FILE, 'r') as f:
            return f.read().strip()
    except FileNotFoundError:
        key = secrets.token_hex(32)
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_SECRET_KEY_FILE, 'w') as f:
            f.write(key)
        return key


_cfg = _load_json_config()
_oauth = _cfg.get('oauth', {})
_jwt_cfg = _cfg.get('jwt', {})


class Config:
    PORT = _cfg.get('port', 10241)
    SECRET_KEY = _cfg.get('secret_key') or _load_secret_key()
    DATA_DIR = _DATA_DIR
    USERS_FILE = os.path.join(_DATA_DIR, 'users.json')
    SERVICES_FILE = os.path.join(_DATA_DIR, 'services.json')

    NEXTCLOUD_OAUTH_ENABLED = os.environ.get('NEXTCLOUD_OAUTH_ENABLED',
        str(_oauth.get('enabled', True))).lower() == 'true'
    NEXTCLOUD_OAUTH_CLIENT_ID = os.environ.get('NEXTCLOUD_OAUTH_CLIENT_ID',
        _oauth.get('client_id', ''))
    NEXTCLOUD_OAUTH_CLIENT_SECRET = os.environ.get('NEXTCLOUD_OAUTH_CLIENT_SECRET',
        _oauth.get('client_secret', ''))
    NEXTCLOUD_OAUTH_REDIRECT_URI = os.environ.get('NEXTCLOUD_OAUTH_REDIRECT_URI',
        _oauth.get('redirect_uri', ''))
    NEXTCLOUD_OAUTH_AUTHORIZE_URL = os.environ.get('NEXTCLOUD_OAUTH_AUTHORIZE_URL',
        _oauth.get('authorize_url', ''))
    NEXTCLOUD_OAUTH_TOKEN_URL = os.environ.get('NEXTCLOUD_OAUTH_TOKEN_URL',
        _oauth.get('token_url', ''))
    NEXTCLOUD_OAUTH_USERINFO_URL = os.environ.get('NEXTCLOUD_OAUTH_USERINFO_URL',
        _oauth.get('userinfo_url', ''))

    JWT_SECRET_KEY = _jwt_cfg.get('secret_key') or _load_secret_key()
    JWT_ALGORITHM = _jwt_cfg.get('algorithm', 'HS256')
    JWT_EXPIRATION_HOURS = _jwt_cfg.get('expiration_hours', 24)