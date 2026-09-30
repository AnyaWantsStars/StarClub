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


class Config:
    DATA_DIR = _DATA_DIR
    SECRET_KEY_FILE = _SECRET_KEY_FILE
    SECRET_KEY = _load_secret_key()

    HOST = '0.0.0.0'
    PORT = _cfg.get('port', 10242)

    USERS_FILE = os.path.join(_DATA_DIR, 'users.json')
    ATTENDANCE_FILE = os.path.join(_DATA_DIR, 'attendance.json')
    REPORTS_FILE = os.path.join(_DATA_DIR, 'reports.json')
    APPEALS_FILE = os.path.join(_DATA_DIR, 'appeals.json')
    PUBLICATIONS_FILE = os.path.join(_DATA_DIR, 'publications.json')
    SYSTEM_CONFIG_FILE = os.path.join(_DATA_DIR, 'system_config.json')

    os.makedirs(_DATA_DIR, exist_ok=True)


class SystemConfig:
    def __init__(self):
        att = _cfg.get('attendance', {})
        mail = _cfg.get('email', {})

        self.attendance_start_time = att.get('start_time', '06:00')
        self.attendance_end_time = att.get('end_time', '23:30')
        self.attendance_interval_seconds = att.get('interval_seconds', 15)
        self.attendance_reminder_minutes = att.get('reminder_minutes', 30)

        self.session_expire_seconds = _cfg.get('session_expire_seconds', 30 * 24 * 3600)

        self.email_enabled = mail.get('enabled', True)
        self.email_time_start = mail.get('time_start', '06:00')
        self.email_time_end = mail.get('time_end', '23:59')
        self.admin_email = mail.get('admin_email', 'notify@example.com')
        self.sender_address = mail.get('sender_address', 'notify@example.com')
        self.sender_name = mail.get('sender_name', 'StarClub | 星社出勤')
        self.smtp_username = mail.get('smtp_username', 'notify@example.com')
        self.smtp_password = mail.get('smtp_password', '')
        self.smtp_host = mail.get('smtp_host', 'smtp.example.com')
        self.smtp_port = mail.get('smtp_port', 465)

        self.portal_url = _cfg.get('portal_url', '')
        self.service_port = _cfg.get('service_port', 10241)

        self.allowed_ip_ranges = _cfg.get('allowed_ip_ranges', '192.168.0.0/24,192.168.1.x')
        self.ranking_include_users = _cfg.get('ranking_include_users', [])

        # OAuth 已废弃，保留属性兼容旧代码
        self.oauth_enabled = False
        self.oauth_client_id = ''
        self.oauth_client_secret = ''
        self.oauth_redirect_uri = ''
        self.oauth_authorize_url = ''
        self.oauth_token_url = ''
        self.oauth_userinfo_url = ''

    def to_dict(self):
        return {
            'attendance_start_time': self.attendance_start_time,
            'attendance_end_time': self.attendance_end_time,
            'attendance_interval_seconds': self.attendance_interval_seconds,
            'attendance_reminder_minutes': self.attendance_reminder_minutes,
            'session_expire_seconds': self.session_expire_seconds,
            'email_enabled': self.email_enabled,
            'email_time_start': self.email_time_start,
            'email_time_end': self.email_time_end,
            'admin_email': self.admin_email,
            'sender_address': self.sender_address,
            'sender_name': self.sender_name,
            'smtp_username': self.smtp_username,
            'smtp_password': self.smtp_password,
            'smtp_host': self.smtp_host,
            'smtp_port': self.smtp_port,
            'portal_url': self.portal_url,
            'service_port': self.service_port,
            'allowed_ip_ranges': self.allowed_ip_ranges,
            'ranking_include_users': self.ranking_include_users,
            'oauth_enabled': self.oauth_enabled,
            'oauth_client_id': self.oauth_client_id,
            'oauth_client_secret': self.oauth_client_secret,
            'oauth_redirect_uri': self.oauth_redirect_uri,
            'oauth_authorize_url': self.oauth_authorize_url,
            'oauth_token_url': self.oauth_token_url,
            'oauth_userinfo_url': self.oauth_userinfo_url
        }

    @classmethod
    def from_dict(cls, data):
        config = cls()
        if data:
            config.attendance_start_time = data.get('attendance_start_time',
                f"{data.get('attendance_start_hour', 6):02d}:{data.get('attendance_start_minute', 0):02d}")
            config.attendance_end_time = data.get('attendance_end_time',
                f"{data.get('attendance_end_hour', 23):02d}:{data.get('attendance_end_minute', 30):02d}")
            config.attendance_interval_seconds = data.get('attendance_interval_seconds', 15)
            config.attendance_reminder_minutes = data.get('attendance_reminder_minutes', 30)
            secs = data.get('session_expire_seconds')
            if secs is not None:
                config.session_expire_seconds = int(secs)
            elif 'session_expire_days' in data:
                config.session_expire_seconds = int(data['session_expire_days']) * 24 * 3600
            config.email_enabled = data.get('email_enabled', True)
            config.email_time_start = data.get('email_time_start', '06:00')
            config.email_time_end = data.get('email_time_end', '23:59')
            config.admin_email = data.get('admin_email', 'admin@example.com')
            config.sender_address = data.get('sender_address', 'notify@example.com')
            config.sender_name = data.get('sender_name', 'StarClub | 星社出勤')
            config.smtp_username = data.get('smtp_username', 'notify@example.com')
            config.smtp_password = data.get('smtp_password', '')
            config.smtp_host = data.get('smtp_host', 'smtp.example.com')
            config.smtp_port = data.get('smtp_port', 465)
            config.portal_url = data.get('portal_url', '')
            config.service_port = data.get('service_port', 10241)
            config.allowed_ip_ranges = data.get('allowed_ip_ranges', '192.168.0.x,192.168.1.x')
            config.ranking_include_users = data.get('ranking_include_users', [])
            config.oauth_enabled = data.get('oauth_enabled', False)
            config.oauth_client_id = data.get('oauth_client_id', '')
            config.oauth_client_secret = data.get('oauth_client_secret', '')
            config.oauth_redirect_uri = data.get('oauth_redirect_uri', '')
            config.oauth_authorize_url = data.get('oauth_authorize_url', '')
            config.oauth_token_url = data.get('oauth_token_url', '')
            config.oauth_userinfo_url = data.get('oauth_userinfo_url', '')
        return config