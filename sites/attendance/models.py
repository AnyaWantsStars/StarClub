import json
import os
import uuid
from datetime import datetime
from config import Config

class JSONStore:
    @staticmethod
    def load(filepath):
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []

    @staticmethod
    def save(filepath, data):
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

class User:
    STATUS_NORMAL = 'normal'
    STATUS_LOCKED = 'locked'
    STATUS_DISABLED = 'disabled'

    TYPE_REGULAR = 'regular'
    TYPE_ADMIN = 'admin'
    TYPE_SUPER_ADMIN = 'super_admin'

    def __init__(self, user_id, username, user_type=TYPE_REGULAR, status=STATUS_NORMAL, oauth_id=None, email=None, created_at=None):
        self.user_id = user_id
        self.username = username
        self.user_type = user_type
        self.status = status
        self.oauth_id = oauth_id
        self.email = email
        self.created_at = created_at or datetime.now().isoformat()

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

    @classmethod
    def from_dict(cls, data):
        return cls(
            user_id=data['user_id'],
            username=data['username'],
            user_type=data.get('user_type', cls.TYPE_REGULAR),
            status=data.get('status', cls.STATUS_NORMAL),
            oauth_id=data.get('oauth_id'),
            email=data.get('email'),
            created_at=data.get('created_at')
        )

class UserManager:
    def __init__(self):
        self.users_file = Config.USERS_FILE
        self.users = []
        self.load()

    def load(self):
        data = JSONStore.load(self.users_file)
        self.users = [User.from_dict(u) for u in data]

    def save(self):
        JSONStore.save(self.users_file, [u.to_dict() for u in self.users])

    def find_by_oauth_id(self, oauth_id):
        for u in self.users:
            if u.oauth_id == oauth_id:
                return u
        return None

    def find_by_user_id(self, user_id):
        for u in self.users:
            if u.user_id == user_id:
                return u
        return None

    def find_by_username(self, username):
        for u in self.users:
            if u.username == username and u.oauth_id is None:
                return u
        return None

    def create_user(self, user_id, username, oauth_id, email=None, user_type=User.TYPE_REGULAR):
        user = User(user_id, username, user_type, User.STATUS_NORMAL, oauth_id, email)
        self.users.append(user)
        self.save()
        return user

    def update_user(self, user):
        for i, u in enumerate(self.users):
            if u.user_id == user.user_id:
                self.users[i] = user
                self.save()
                return True
        return False

    def get_all_users(self):
        return self.users

class AttendanceRecord:
    STATUS_VALID = 'valid'
    STATUS_INVALID = 'invalid'

    def __init__(self, record_id, user_id, username, check_in, check_out=None, status=STATUS_VALID, created_at=None):
        self.record_id = record_id
        self.user_id = user_id
        self.username = username
        self.check_in = check_in
        self.check_out = check_out
        self.status = status
        self.created_at = created_at or datetime.now().isoformat()

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

    @classmethod
    def from_dict(cls, data):
        return cls(
            record_id=data['record_id'],
            user_id=data['user_id'],
            username=data['username'],
            check_in=data['check_in'],
            check_out=data.get('check_out'),
            status=data.get('status', cls.STATUS_VALID),
            created_at=data.get('created_at')
        )

    def get_duration_minutes(self):
        if self.check_in and self.check_out:
            try:
                start = datetime.fromisoformat(self.check_in)
                end = datetime.fromisoformat(self.check_out)
                return round((end - start).total_seconds() / 60, 2)
            except:
                return 0
        return 0

class AttendanceManager:
    def __init__(self):
        self.attendance_file = Config.ATTENDANCE_FILE
        self.records = []
        self.load()

    def load(self):
        data = JSONStore.load(self.attendance_file)
        self.records = [AttendanceRecord.from_dict(r) for r in data]

    def save(self):
        JSONStore.save(self.attendance_file, [r.to_dict() for r in self.records])

    def generate_record_id(self):
        return f"ATT{uuid.uuid4().hex[:16].upper()}"

    def add_record(self, record):
        self.records.append(record)
        self.save()

    def get_record_by_id(self, record_id):
        for r in self.records:
            if r.record_id == record_id:
                return r
        return None

    def update_record(self, record):
        for i, r in enumerate(self.records):
            if r.record_id == record.record_id:
                self.records[i] = record
                self.save()
                return True
        return False

    def get_records_by_user(self, user_id):
        return [r for r in self.records if r.user_id == user_id]

    def get_all_records(self):
        return self.records

    def get_online_users(self):
        online = []
        for r in self.records:
            if r.status == AttendanceRecord.STATUS_VALID and r.check_out is None:
                online.append(r)
        return online

class Report:
    TYPE_ONLINE = 'online'
    TYPE_RANKING = 'ranking'

    STATUS_PENDING = 'pending'
    STATUS_VALID = 'valid'
    STATUS_INVALID = 'invalid'
    STATUS_PROCESSED = 'processed'

    def __init__(self, report_id, report_type, reporter_id, reporter_name, reported_id, reported_name,
                 report_time, reason=None, evidence_images=None, status=STATUS_PENDING,
                 processed_by=None, processed_at=None, process_result=None, check_out_time=None):
        self.report_id = report_id
        self.report_type = report_type
        self.reporter_id = reporter_id
        self.reporter_name = reporter_name
        self.reported_id = reported_id
        self.reported_name = reported_name
        self.report_time = report_time
        self.reason = reason
        self.evidence_images = evidence_images or []
        self.status = status
        self.processed_by = processed_by
        self.processed_at = processed_at
        self.process_result = process_result
        self.check_out_time = check_out_time

    def to_dict(self):
        return {
            'report_id': self.report_id,
            'report_type': self.report_type,
            'reporter_id': self.reporter_id,
            'reporter_name': self.reporter_name,
            'reported_id': self.reported_id,
            'reported_name': self.reported_name,
            'report_time': self.report_time,
            'reason': self.reason,
            'evidence_images': self.evidence_images,
            'status': self.status,
            'processed_by': self.processed_by,
            'processed_at': self.processed_at,
            'process_result': self.process_result,
            'check_out_time': self.check_out_time
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            report_id=data['report_id'],
            report_type=data['report_type'],
            reporter_id=data['reporter_id'],
            reporter_name=data['reporter_name'],
            reported_id=data['reported_id'],
            reported_name=data['reported_name'],
            report_time=data['report_time'],
            reason=data.get('reason'),
            evidence_images=data.get('evidence_images', []),
            status=data.get('status', cls.STATUS_PENDING),
            processed_by=data.get('processed_by'),
            processed_at=data.get('processed_at'),
            process_result=data.get('process_result'),
            check_out_time=data.get('check_out_time')
        )

class ReportManager:
    def __init__(self):
        self.reports_file = Config.REPORTS_FILE
        self.reports = []
        self.load()

    def load(self):
        data = JSONStore.load(self.reports_file)
        self.reports = [Report.from_dict(r) for r in data]

    def save(self):
        JSONStore.save(self.reports_file, [r.to_dict() for r in self.reports])

    def generate_report_id(self):
        return f"REP{uuid.uuid4().hex[:16].upper()}"

    def add_report(self, report):
        self.reports.append(report)
        self.save()

    def get_report_by_id(self, report_id):
        for r in self.reports:
            if r.report_id == report_id:
                return r
        return None

    def update_report(self, report):
        for i, r in enumerate(self.reports):
            if r.report_id == report.report_id:
                self.reports[i] = report
                self.save()
                return True
        return False

    def get_all_reports(self):
        return self.reports

class Appeal:
    STATUS_PENDING = 'pending'
    STATUS_VALID = 'valid'
    STATUS_INVALID = 'invalid'
    STATUS_PROCESSED = 'processed'

    def __init__(self, appeal_id, record_id, user_id, username, appeal_time,
                 original_check_in, original_check_out, reason=None, evidence_images=None,
                 status=STATUS_PENDING, processed_by=None, processed_at=None,
                 process_result=None, new_check_out=None):
        self.appeal_id = appeal_id
        self.record_id = record_id
        self.user_id = user_id
        self.username = username
        self.appeal_time = appeal_time
        self.original_check_in = original_check_in
        self.original_check_out = original_check_out
        self.reason = reason
        self.evidence_images = evidence_images or []
        self.status = status
        self.processed_by = processed_by
        self.processed_at = processed_at
        self.process_result = process_result
        self.new_check_out = new_check_out

    def to_dict(self):
        return {
            'appeal_id': self.appeal_id,
            'record_id': self.record_id,
            'user_id': self.user_id,
            'username': self.username,
            'appeal_time': self.appeal_time,
            'original_check_in': self.original_check_in,
            'original_check_out': self.original_check_out,
            'reason': self.reason,
            'evidence_images': self.evidence_images,
            'status': self.status,
            'processed_by': self.processed_by,
            'processed_at': self.processed_at,
            'process_result': self.process_result,
            'new_check_out': self.new_check_out
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            appeal_id=data['appeal_id'],
            record_id=data['record_id'],
            user_id=data['user_id'],
            username=data['username'],
            appeal_time=data['appeal_time'],
            original_check_in=data['original_check_in'],
            original_check_out=data['original_check_out'],
            reason=data.get('reason'),
            evidence_images=data.get('evidence_images', []),
            status=data.get('status', cls.STATUS_PENDING),
            processed_by=data.get('processed_by'),
            processed_at=data.get('processed_at'),
            process_result=data.get('process_result'),
            new_check_out=data.get('new_check_out')
        )

class AppealManager:
    def __init__(self):
        self.appeals_file = Config.APPEALS_FILE
        self.appeals = []
        self.load()

    def load(self):
        data = JSONStore.load(self.appeals_file)
        self.appeals = [Appeal.from_dict(a) for a in data]

    def save(self):
        JSONStore.save(self.appeals_file, [a.to_dict() for a in self.appeals])

    def generate_appeal_id(self):
        return f"APL{uuid.uuid4().hex[:16].upper()}"

    def add_appeal(self, appeal):
        self.appeals.append(appeal)
        self.save()

    def get_appeal_by_id(self, appeal_id):
        for a in self.appeals:
            if a.appeal_id == appeal_id:
                return a
        return None

    def update_appeal(self, appeal):
        for i, a in enumerate(self.appeals):
            if a.appeal_id == appeal.appeal_id:
                self.appeals[i] = appeal
                self.save()
                return True
        return False

    def get_all_appeals(self):
        return self.appeals

    def get_appeals_by_record_id(self, record_id):
        return [a for a in self.appeals if a.record_id == record_id]

class Publication:
    def __init__(self, pub_id, name, start_date, end_date, created_at=None,
                 include_users=None, exclude_users=None, is_active=True,
                 show_records=True, show_invalid_records=False):
        self.pub_id = pub_id
        self.name = name
        self.start_date = start_date
        self.end_date = end_date
        self.created_at = created_at or datetime.now().isoformat()
        self.include_users = include_users or []
        self.exclude_users = exclude_users or []
        self.is_active = is_active
        self.show_records = show_records
        self.show_invalid_records = show_invalid_records

    def to_dict(self):
        return {
            'pub_id': self.pub_id,
            'name': self.name,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'created_at': self.created_at,
            'include_users': self.include_users,
            'exclude_users': self.exclude_users,
            'is_active': self.is_active,
            'show_records': self.show_records,
            'show_invalid_records': self.show_invalid_records
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            pub_id=data['pub_id'],
            name=data['name'],
            start_date=data['start_date'],
            end_date=data['end_date'],
            created_at=data.get('created_at'),
            include_users=data.get('include_users', []),
            exclude_users=data.get('exclude_users', []),
            is_active=data.get('is_active', True),
            show_records=data.get('show_records', True),
            show_invalid_records=data.get('show_invalid_records', False)
        )

class PublicationManager:
    def __init__(self):
        self.publications_file = Config.PUBLICATIONS_FILE
        self.publications = []
        self.load()

    def load(self):
        data = JSONStore.load(self.publications_file)
        self.publications = [Publication.from_dict(p) for p in data]

    def save(self):
        JSONStore.save(self.publications_file, [p.to_dict() for p in self.publications])

    def generate_pub_id(self):
        return f"PUB{uuid.uuid4().hex[:16].upper()}"

    def add_publication(self, pub):
        self.publications.insert(0, pub)
        self.save()

    def get_pub_by_id(self, pub_id):
        for p in self.publications:
            if p.pub_id == pub_id:
                return p
        return None

    def update_publication(self, pub):
        for i, p in enumerate(self.publications):
            if p.pub_id == pub.pub_id:
                self.publications[i] = pub
                self.save()
                return True
        return False

    def delete_publication(self, pub_id):
        self.publications = [p for p in self.publications if p.pub_id != pub_id]
        self.save()

    def get_all_publications(self):
        return self.publications

    def get_active_publications(self):
        return [p for p in self.publications if p.is_active]
