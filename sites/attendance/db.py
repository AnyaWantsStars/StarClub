"""
数据库层 - SQLite (WAL模式)
替代原有的 JSON 文件存储，支持并发读取。
"""
import sqlite3
import os
import json
import uuid
from datetime import datetime
from config import Config

DB_PATH = os.path.join(Config.DATA_DIR, 'attendance.db')


def get_db():
    """获取数据库连接（WAL模式，支持并发读）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """初始化数据库表结构"""
    conn = get_db()
    conn.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT UNIQUE NOT NULL,
            username TEXT NOT NULL,
            user_type TEXT NOT NULL DEFAULT 'regular',
            status TEXT NOT NULL DEFAULT 'normal',
            oauth_id TEXT UNIQUE,
            email TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS attendance_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT UNIQUE NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            check_in TEXT NOT NULL,
            check_out TEXT,
            status TEXT NOT NULL DEFAULT 'valid',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_id TEXT UNIQUE NOT NULL,
            report_type TEXT NOT NULL,
            reporter_id TEXT NOT NULL,
            reporter_name TEXT NOT NULL,
            reported_id TEXT NOT NULL,
            reported_name TEXT NOT NULL,
            reported_record_id TEXT,
            report_time TEXT NOT NULL,
            reason TEXT DEFAULT '',
            evidence_images TEXT DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'pending',
            processed_by TEXT,
            processed_at TEXT,
            process_result TEXT,
            check_out_time TEXT
        );

        CREATE TABLE IF NOT EXISTS appeals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            appeal_id TEXT UNIQUE NOT NULL,
            record_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            username TEXT NOT NULL,
            appeal_time TEXT NOT NULL,
            original_check_in TEXT,
            original_check_out TEXT,
            reason TEXT DEFAULT '',
            evidence_images TEXT DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'pending',
            processed_by TEXT,
            processed_at TEXT,
            process_result TEXT,
            new_check_out TEXT
        );

        CREATE TABLE IF NOT EXISTS publications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pub_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            created_at TEXT NOT NULL,
            include_users TEXT DEFAULT '[]',
            exclude_users TEXT DEFAULT '[]',
            is_active INTEGER NOT NULL DEFAULT 1,
            show_records INTEGER NOT NULL DEFAULT 1,
            show_invalid_records INTEGER NOT NULL DEFAULT 0
        );

        CREATE INDEX IF NOT EXISTS idx_records_user_id ON attendance_records(user_id);
        CREATE INDEX IF NOT EXISTS idx_records_check_in ON attendance_records(check_in);
        CREATE INDEX IF NOT EXISTS idx_records_status ON attendance_records(status);
        CREATE INDEX IF NOT EXISTS idx_reports_reported_id ON reports(reported_id);
        CREATE INDEX IF NOT EXISTS idx_appeals_record_id ON appeals(record_id);
    ''')
    # 迁移：为旧数据库添加 reported_record_id 列
    try:
        conn.execute("ALTER TABLE reports ADD COLUMN reported_record_id TEXT")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # 列已存在
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────────────────────
# 数据模型（与旧 models.py 保持相同的 to_dict 接口）
# ──────────────────────────────────────────────────────────────────

class User:
    STATUS_NORMAL = 'normal'
    STATUS_LOCKED = 'locked'
    STATUS_DISABLED = 'disabled'
    TYPE_REGULAR = 'regular'
    TYPE_ADMIN = 'admin'
    TYPE_SUPER_ADMIN = 'super_admin'

    def __init__(self, **kwargs):
        self.user_id = kwargs.get('user_id')
        self.username = kwargs.get('username')
        self.user_type = kwargs.get('user_type', self.TYPE_REGULAR)
        self.status = kwargs.get('status', self.STATUS_NORMAL)
        self.oauth_id = kwargs.get('oauth_id')
        self.email = kwargs.get('email', '')
        self.created_at = kwargs.get('created_at', datetime.now().isoformat())

    def to_dict(self):
        return {
            'user_id': self.user_id,
            'username': self.username,
            'user_type': self.user_type,
            'status': self.status,
            'oauth_id': self.oauth_id,
            'email': self.email,
            'created_at': self.created_at
        }


# ──────────────────────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────────────────────

def _parse_dt(dt_str):
    """兼容 T 分隔和空格分隔的日期时间格式 (避免循环导入 tool_func)"""
    for fmt in ('%Y-%m-%dT%H:%M:%S', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M'):
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            continue
    return datetime.fromisoformat(dt_str)


class AttendanceRecord:
    STATUS_VALID = 'valid'
    STATUS_INVALID = 'invalid'

    def __init__(self, **kwargs):
        self.record_id = kwargs.get('record_id')
        self.user_id = kwargs.get('user_id')
        self.username = kwargs.get('username')
        self.check_in = kwargs.get('check_in')
        self.check_out = kwargs.get('check_out')
        self.status = kwargs.get('status', self.STATUS_VALID)
        self.created_at = kwargs.get('created_at', datetime.now().isoformat())

    def to_dict(self):
        return {
            'record_id': self.record_id,
            'user_id': self.user_id,
            'username': self.username,
            'check_in': self.check_in,
            'check_out': self.check_out,
            'status': self.status,
            'created_at': self.created_at
        }

    def get_duration_minutes(self):
        if self.check_in and self.check_out:
            try:
                start = _parse_dt(self.check_in)
                end = _parse_dt(self.check_out)
                return round((end - start).total_seconds() / 60, 2)
            except Exception:
                return 0
        return 0


class Report:
    TYPE_ONLINE = 'online'
    TYPE_RANKING = 'ranking'
    STATUS_PENDING = 'pending'
    STATUS_VALID = 'valid'
    STATUS_INVALID = 'invalid'
    STATUS_PROCESSED = 'processed'

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        d = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        # 确保 evidence_images 是列表
        if isinstance(d.get('evidence_images'), str):
            try:
                d['evidence_images'] = json.loads(d['evidence_images'])
            except (json.JSONDecodeError, TypeError):
                d['evidence_images'] = []
        return d


class Appeal:
    STATUS_PENDING = 'pending'
    STATUS_VALID = 'valid'
    STATUS_INVALID = 'invalid'
    STATUS_PROCESSED = 'processed'

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        d = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        if isinstance(d.get('evidence_images'), str):
            try:
                d['evidence_images'] = json.loads(d['evidence_images'])
            except (json.JSONDecodeError, TypeError):
                d['evidence_images'] = []
        return d


class Publication:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)

    def to_dict(self):
        d = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        for field in ['include_users', 'exclude_users']:
            if isinstance(d.get(field), str):
                try:
                    d[field] = json.loads(d[field])
                except (json.JSONDecodeError, TypeError):
                    d[field] = []
        d['is_active'] = bool(d.get('is_active', True))
        d['show_records'] = bool(d.get('show_records', True))
        d['show_invalid_records'] = bool(d.get('show_invalid_records', False))
        return d


# ──────────────────────────────────────────────────────────────────
# CRUD 操作函数（直接操作 SQLite）
# ──────────────────────────────────────────────────────────────────

def _row_to_user(row):
    return User(**dict(row))

def _row_to_record(row):
    return AttendanceRecord(**dict(row))

def _row_to_report(row):
    return Report(**dict(row))

def _row_to_appeal(row):
    return Appeal(**dict(row))

def _row_to_publication(row):
    return Publication(**dict(row))


# ── User CRUD ──

def user_find_by_oauth_id(oauth_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE oauth_id = ?", (oauth_id,)).fetchone()
    return _row_to_user(row) if row else None

def user_find_by_user_id(user_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
    return _row_to_user(row) if row else None

def user_create(user_id, username, oauth_id, email='', user_type='regular'):
    now = datetime.now().isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO users (user_id, username, user_type, status, oauth_id, email, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (user_id, username, user_type, User.STATUS_NORMAL, oauth_id, email, now)
        )
        conn.commit()
    return user_find_by_user_id(user_id)

def user_update(user, **kwargs):
    """更新用户信息，支持传入 User 对象或关键字参数"""
    if kwargs:
        for k, v in kwargs.items():
            if hasattr(user, k):
                setattr(user, k, v)
            elif k in user:
                user[k] = v
    with get_db() as conn:
        username = user.username if hasattr(user, 'username') else user.get('username', '')
        user_type = user.user_type if hasattr(user, 'user_type') else user.get('user_type', 'regular')
        status = user.status if hasattr(user, 'status') else user.get('status', 'normal')
        oauth_id = user.oauth_id if hasattr(user, 'oauth_id') else user.get('oauth_id', '')
        email = user.email if hasattr(user, 'email') else user.get('email', '')
        uid = user.user_id if hasattr(user, 'user_id') else user.get('user_id', '')
        conn.execute(
            "UPDATE users SET username=?, user_type=?, status=?, oauth_id=?, email=? WHERE user_id=?",
            (username, user_type, status, oauth_id, email, uid)
        )
        conn.commit()

def user_get_all():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM users ORDER BY created_at").fetchall()
    return [_row_to_user(r) for r in rows]


# ── Attendance CRUD ──

def generate_record_id():
    return f"ATT{uuid.uuid4().hex[:16].upper()}"

def record_add(record):
    with get_db() as conn:
        conn.execute(
            "INSERT INTO attendance_records (record_id, user_id, username, check_in, check_out, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (record.record_id, record.user_id, record.username, record.check_in,
             record.check_out, record.status, record.created_at)
        )
        conn.commit()

def record_get_by_id(record_id):
    with get_db() as conn:
        row = conn.execute(
            "SELECT * FROM attendance_records WHERE record_id = ?", (record_id,)
        ).fetchone()
    return _row_to_record(row) if row else None

def record_update(record):
    with get_db() as conn:
        conn.execute(
            "UPDATE attendance_records SET check_in=?, check_out=?, status=? WHERE record_id=?",
            (record.check_in, record.check_out, record.status, record.record_id)
        )
        conn.commit()


def record_delete_by_year(year):
    """删除指定年份的所有签到记录，返回删除条数"""
    with get_db() as conn:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM attendance_records WHERE check_in LIKE ?",
            (f'{year}%',)
        )
        count = cursor.fetchone()[0]
        conn.execute(
            "DELETE FROM attendance_records WHERE check_in LIKE ?",
            (f'{year}%',)
        )
        conn.commit()
        return count

def record_get_by_user(user_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM attendance_records WHERE user_id = ? ORDER BY check_in DESC", (user_id,)
        ).fetchall()
    return [_row_to_record(r) for r in rows]

def record_get_all():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM attendance_records").fetchall()
    return [_row_to_record(r) for r in rows]

def record_get_online():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM attendance_records WHERE status = 'valid' AND check_out IS NULL"
        ).fetchall()
    return [_row_to_record(r) for r in rows]


# ── Report CRUD ──

def generate_report_id():
    return f"REP{uuid.uuid4().hex[:16].upper()}"

def report_add(report):
    d = report.__dict__.copy()
    if isinstance(d.get('evidence_images'), list):
        d['evidence_images'] = json.dumps(d['evidence_images'])
    with get_db() as conn:
        conn.execute(
            "INSERT INTO reports (report_id, report_type, reporter_id, reporter_name, "
            "reported_id, reported_name, reported_record_id, report_time, reason, evidence_images, status, "
            "processed_by, processed_at, process_result, check_out_time) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d.get('report_id'), d.get('report_type'), d.get('reporter_id'), d.get('reporter_name'),
             d.get('reported_id'), d.get('reported_name'), d.get('reported_record_id'),
             d.get('report_time'), d.get('reason', ''),
             d['evidence_images'], d.get('status', 'pending'), d.get('processed_by'),
             d.get('processed_at'), d.get('process_result'), d.get('check_out_time'))
        )
        conn.commit()

def report_get_by_id(report_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM reports WHERE report_id = ?", (report_id,)).fetchone()
    return _row_to_report(row) if row else None

def report_update(report):
    d = report.__dict__.copy()
    if isinstance(d.get('evidence_images'), list):
        d['evidence_images'] = json.dumps(d['evidence_images'])
    with get_db() as conn:
        conn.execute(
            "UPDATE reports SET reason=?, evidence_images=?, status=?, processed_by=?, "
            "processed_at=?, process_result=?, check_out_time=? WHERE report_id=?",
            (d.get('reason', ''), d['evidence_images'], d.get('status'), d.get('processed_by'),
             d.get('processed_at'), d.get('process_result'), d.get('check_out_time'), d.get('report_id'))
        )
        conn.commit()

def report_get_all():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM reports ORDER BY report_time DESC").fetchall()
    return [_row_to_report(r) for r in rows]


# ── Appeal CRUD ──

def generate_appeal_id():
    return f"APL{uuid.uuid4().hex[:16].upper()}"

def appeal_add(appeal):
    d = appeal.__dict__.copy()
    if isinstance(d.get('evidence_images'), list):
        d['evidence_images'] = json.dumps(d['evidence_images'])
    with get_db() as conn:
        conn.execute(
            "INSERT INTO appeals (appeal_id, record_id, user_id, username, appeal_time, "
            "original_check_in, original_check_out, reason, evidence_images, status, "
            "processed_by, processed_at, process_result, new_check_out) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d.get('appeal_id'), d.get('record_id'), d.get('user_id'), d.get('username'),
             d.get('appeal_time'), d.get('original_check_in'), d.get('original_check_out'),
             d.get('reason', ''), d['evidence_images'], d.get('status', 'pending'),
             d.get('processed_by'), d.get('processed_at'), d.get('process_result'),
             d.get('new_check_out'))
        )
        conn.commit()

def appeal_get_by_id(appeal_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM appeals WHERE appeal_id = ?", (appeal_id,)).fetchone()
    return _row_to_appeal(row) if row else None

def appeal_get_by_record_id(record_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM appeals WHERE record_id = ?", (record_id,)
        ).fetchall()
    return [_row_to_appeal(r) for r in rows]

def appeal_update(appeal):
    d = appeal.__dict__.copy()
    if isinstance(d.get('evidence_images'), list):
        d['evidence_images'] = json.dumps(d['evidence_images'])
    with get_db() as conn:
        conn.execute(
            "UPDATE appeals SET reason=?, evidence_images=?, status=?, processed_by=?, "
            "processed_at=?, process_result=?, new_check_out=? WHERE appeal_id=?",
            (d.get('reason', ''), d['evidence_images'], d.get('status'), d.get('processed_by'),
             d.get('processed_at'), d.get('process_result'), d.get('new_check_out'), d.get('appeal_id'))
        )
        conn.commit()

def appeal_get_all():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM appeals ORDER BY appeal_time DESC").fetchall()
    return [_row_to_appeal(r) for r in rows]


# ── Publication CRUD ──

def generate_pub_id():
    return f"PUB{uuid.uuid4().hex[:16].upper()}"

def pub_add(pub):
    d = {k: v for k, v in pub.__dict__.items() if not k.startswith('_')}
    for field in ['include_users', 'exclude_users']:
        if isinstance(d.get(field), list):
            d[field] = json.dumps(d[field])
    with get_db() as conn:
        conn.execute(
            "INSERT INTO publications (pub_id, name, start_date, end_date, created_at, "
            "include_users, exclude_users, is_active, show_records, show_invalid_records) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (d.get('pub_id'), d.get('name'), d.get('start_date'), d.get('end_date'),
             d.get('created_at', datetime.now().isoformat()), d.get('include_users', '[]'),
             d.get('exclude_users', '[]'), int(d.get('is_active', True)),
             int(d.get('show_records', True)), int(d.get('show_invalid_records', False)))
        )
        conn.commit()

def pub_get_by_id(pub_id):
    with get_db() as conn:
        row = conn.execute("SELECT * FROM publications WHERE pub_id = ?", (pub_id,)).fetchone()
    return _row_to_publication(row) if row else None

def pub_update(pub):
    d = {k: v for k, v in pub.__dict__.items() if not k.startswith('_')}
    for field in ['include_users', 'exclude_users']:
        if isinstance(d.get(field), list):
            d[field] = json.dumps(d[field])
    with get_db() as conn:
        conn.execute(
            "UPDATE publications SET name=?, start_date=?, end_date=?, is_active=?, include_users=?, exclude_users=?,"
            "show_records=?, show_invalid_records=? WHERE pub_id=?",
            (d.get('name'), d.get('start_date'), d.get('end_date'), int(d.get('is_active', True)),
             d.get('include_users', '[]'), d.get('exclude_users', '[]'),
             int(d.get('show_records', True)), int(d.get('show_invalid_records', False)),
             d.get('pub_id'))
        )
        conn.commit()

def pub_delete(pub_id):
    with get_db() as conn:
        conn.execute("DELETE FROM publications WHERE pub_id = ?", (pub_id,))
        conn.commit()

def pub_get_all():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM publications ORDER BY created_at DESC").fetchall()
    return [_row_to_publication(r) for r in rows]

def pub_get_active():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM publications WHERE is_active = 1 ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_publication(r) for r in rows]


# ── SystemConfig CRUD (JSON文件) ──

from config import SystemConfig as SysConfigClass


def sys_config_load():
    """从JSON文件加载系统配置，不存在则尝试从旧SQLite迁移"""
    config_path = Config.SYSTEM_CONFIG_FILE
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return SysConfigClass.from_dict(data)

    # 尝试从旧SQLite迁移
    try:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM system_config WHERE id = 1").fetchone()
        if row:
            d = dict(row)
            config = SysConfigClass()
            config.attendance_start_time = f"{d.get('attendance_start_hour', 6):02d}:{d.get('attendance_start_minute', 0):02d}"
            config.attendance_end_time = f"{d.get('attendance_end_hour', 23):02d}:{d.get('attendance_end_minute', 30):02d}"
            config.attendance_interval_seconds = d.get('attendance_interval_seconds', 15)
            config.attendance_reminder_minutes = d.get('attendance_reminder_minutes', 30)
            config.session_expire_days = d.get('session_expire_days', 30)
            config.email_enabled = bool(d.get('email_enabled', True))
            config.admin_email = d.get('admin_email', '')
            config.sender_address = d.get('sender_address', '')
            config.sender_name = d.get('sender_name', '')
            config.smtp_username = d.get('smtp_username', '')
            config.smtp_password = d.get('smtp_password', '')
            config.smtp_host = d.get('smtp_host', '')
            config.smtp_port = d.get('smtp_port', 465)
            config.oauth_enabled = bool(d.get('oauth_enabled', True))
            config.oauth_client_id = d.get('oauth_client_id', '')
            config.oauth_client_secret = d.get('oauth_client_secret', '')
            config.oauth_redirect_uri = d.get('oauth_redirect_uri', '')
            config.oauth_authorize_url = d.get('oauth_authorize_url', '')
            config.oauth_token_url = d.get('oauth_token_url', '')
            config.oauth_userinfo_url = d.get('oauth_userinfo_url', '')
            config.allowed_ip_ranges = d.get('allowed_ip_ranges', '')
            ranking_users = d.get('ranking_include_users', '[]')
            if isinstance(ranking_users, str):
                try:
                    config.ranking_include_users = json.loads(ranking_users)
                except (json.JSONDecodeError, TypeError):
                    config.ranking_include_users = []
            else:
                config.ranking_include_users = ranking_users
            sys_config_save(config)  # 保存为JSON
            return config
    except Exception:
        pass

    config = SysConfigClass()
    sys_config_save(config)
    return config


def sys_config_save(config):
    """保存系统配置到JSON文件"""
    os.makedirs(os.path.dirname(Config.SYSTEM_CONFIG_FILE), exist_ok=True)
    with open(Config.SYSTEM_CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config.to_dict(), f, ensure_ascii=False, indent=2)