"""
签到相关路由
- 签到/签退
- 在线用户
- 举报/申诉
- 图片上传
- 签到排行
- 公示查看
"""
from flask import Blueprint, request, session, jsonify, render_template, current_app
from datetime import datetime, timedelta
import os
import uuid

from db import (
    User, AttendanceRecord, Report, Appeal,
    user_find_by_user_id,
    record_add, record_get_by_user, record_get_by_id, record_get_all, record_get_online,
    record_update,
    generate_record_id, generate_report_id, report_add,
    generate_appeal_id, appeal_add, appeal_get_by_record_id,
    pub_get_active, pub_get_by_id,
)
from services.ranking import compute_ranking, filter_records_for_ranking
from tool_func import (
    login_required, ip_required, get_current_user,
    get_week_range, get_month_range, get_semester_range,
    filter_user_for_ranking, parse_datetime
)

attendance_bp = Blueprint('attendance', __name__)


# ── 签到主页 ──

@attendance_bp.route('/attendance')
@login_required
def attendance_page():
    system_config = current_app.config.get('system_config')
    user = get_current_user()
    if user.status == User.STATUS_DISABLED:
        return render_template('disabled.html')

    now = datetime.now()
    week_day = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日'][now.weekday()]
    current_date = now.strftime('%Y年%m月%d日')
    current_time = now.strftime('%H:%M:%S')

    user_records = record_get_by_user(user.user_id)
    current_status = 'offline'
    current_record = None

    for r in reversed(user_records):
        if r.check_out is None and r.status == AttendanceRecord.STATUS_VALID:
            current_status = 'online'
            current_record = r
            break

    start_h, start_m = map(int, system_config.attendance_start_time.split(':'))
    end_h, end_m = map(int, system_config.attendance_end_time.split(':'))

    is_within_hours = ((now.hour > start_h or (now.hour == start_h and now.minute >= start_m)) and
                       (now.hour < end_h or (now.hour == end_h and now.minute <= end_m)))

    return render_template('attendance.html',
                           current_date=current_date,
                           week_day=week_day,
                           current_time=current_time,
                           current_status=current_status,
                           current_record=current_record,
                           is_within_hours=is_within_hours,
                           can_action=True,
                           interval_seconds=system_config.attendance_interval_seconds,
                           is_admin=user.user_type in [User.TYPE_ADMIN, User.TYPE_SUPER_ADMIN],
                           has_email=bool(user.email))


# ── 签到签退 ──

@attendance_bp.route('/api/attendance/check_in', methods=['POST'])
@login_required
@ip_required
def api_check_in():
    system_config = current_app.config.get('system_config')
    user = get_current_user()

    if user.status == User.STATUS_LOCKED:
        return jsonify({'success': False, 'message': '账号已锁定，无法签到'}), 403

    now = datetime.now()
    start_h, start_m = map(int, system_config.attendance_start_time.split(':'))
    end_h, end_m = map(int, system_config.attendance_end_time.split(':'))

    if not ((now.hour > start_h or (now.hour == start_h and now.minute >= start_m)) and
            (now.hour < end_h or (now.hour == end_h and now.minute <= end_m))):
        return jsonify({'success': False, 'message': '不在签到时间内'}), 400

    last_action = session.get('last_attendance_action')
    if last_action:
        last_dt = datetime.fromisoformat(last_action)
        elapsed = (now - last_dt).total_seconds()
        if elapsed < system_config.attendance_interval_seconds:
            return jsonify({'success': False,
                            'message': f'操作过于频繁，请{int(system_config.attendance_interval_seconds - elapsed)}秒后再试'}), 429

    records = record_get_by_user(user.user_id)
    for r in reversed(records):
        if r.check_out is None and r.status == AttendanceRecord.STATUS_VALID:
            return jsonify({'success': False, 'message': '您已签到，请先签退'}), 400

    rec = AttendanceRecord(
        record_id=generate_record_id(),
        user_id=user.user_id,
        username=user.username,
        check_in=now.isoformat(),
        status=AttendanceRecord.STATUS_VALID
    )
    record_add(rec)
    session['last_attendance_action'] = now.isoformat()
    return jsonify({'success': True, 'message': '签到成功', 'record': rec.to_dict()})


@attendance_bp.route('/api/attendance/check_out', methods=['POST'])
@login_required
@ip_required
def api_check_out():
    system_config = current_app.config.get('system_config')
    user = get_current_user()

    if user.status == User.STATUS_LOCKED:
        return jsonify({'success': False, 'message': '账号已锁定，无法签退'}), 403

    now = datetime.now()

    # 频率限制（与签到一致）
    last_action = session.get('last_attendance_action')
    if last_action:
        last_dt = datetime.fromisoformat(last_action)
        elapsed = (now - last_dt).total_seconds()
        if elapsed < system_config.attendance_interval_seconds:
            return jsonify({'success': False,
                            'message': f'操作过于频繁，请{int(system_config.attendance_interval_seconds - elapsed)}秒后再试'}), 429

    # 签到时间检查：签退也需在签到时间范围内
    start_h, start_m = map(int, system_config.attendance_start_time.split(':'))
    end_h, end_m = map(int, system_config.attendance_end_time.split(':'))
    if not ((now.hour > start_h or (now.hour == start_h and now.minute >= start_m)) and
            (now.hour < end_h or (now.hour == end_h and now.minute <= end_m))):
        return jsonify({'success': False, 'message': '不在签到时间内'}), 400

    records = record_get_by_user(user.user_id)
    record = None
    for r in reversed(records):
        if r.check_out is None and r.status == AttendanceRecord.STATUS_VALID:
            record = r
            break

    if not record:
        return jsonify({'success': False, 'message': '您未签到'}), 400

    record.check_out = now.isoformat()
    record_update(record)
    session['last_attendance_action'] = now.isoformat()
    return jsonify({'success': True, 'message': '签退成功', 'record': record.to_dict()})


# ── 在线用户 ──

@attendance_bp.route('/api/attendance/online')
@login_required
def api_online_users():
    online = record_get_online()
    result = []
    for r in online:
        u = user_find_by_user_id(r.user_id)
        if u and u.status != User.STATUS_DISABLED:
            result.append({
                'user_id': r.user_id,
                'username': r.username,
                'check_in': r.check_in,
                'record_id': r.record_id
            })
    return jsonify({'success': True, 'online_users': result})


# ── 举报 ──

@attendance_bp.route('/api/attendance/report', methods=['POST'])
@login_required
@ip_required
def api_report():
    system_config = current_app.config.get('system_config')
    email_service = current_app.config.get('email_service')

    user = get_current_user()
    data = request.json

    reported_record_id = data.get('record_id')
    reason = data.get('reason', '')
    evidence_images = data.get('evidence_images', [])

    reported_record = record_get_by_id(reported_record_id) if reported_record_id else None

    # 根据记录状态判断举报类型
    if reported_record and reported_record.check_out is None:
        # 记录仍在线 → 在线举报
        report_type = Report.TYPE_ONLINE
    elif reported_record:
        # 记录已签退 → 排名举报（举报签到数据不实）
        report_type = Report.TYPE_RANKING
    else:
        # 没有记录 → 默认在线举报
        report_type = Report.TYPE_ONLINE

    report = Report(
        report_id=generate_report_id(),
        report_type=report_type,
        reporter_id=user.user_id,
        reporter_name=user.username,
        reported_id=data.get('reported_id', ''),
        reported_name=data.get('reported_name', ''),
        report_time=datetime.now().isoformat(),
        reason=reason,
        evidence_images=evidence_images,
        status=Report.STATUS_PENDING,
        reported_record_id=reported_record_id,
        check_out_time=reported_record.check_out if reported_record else None
    )
    report_add(report)

    if report_type == Report.TYPE_ONLINE and reported_record:
        reported_record.check_out = datetime.now().isoformat()
        reported_record.status = AttendanceRecord.STATUS_INVALID
        record_update(reported_record)

        reported_user = user_find_by_user_id(report.reported_id)
        if reported_user and reported_user.email and system_config.email_enabled:
            email_service.send_report_notification(reported_user.email, reported_user.username, reason)

    if system_config.email_enabled:
        details = f"""
        <p><strong>举报类型：</strong>{'在线举报' if report_type == Report.TYPE_ONLINE else '排名举报'}</p>
        <p><strong>被举报人：</strong>{report.reported_name} ({report.reported_id})</p>
        <p><strong>举报人：</strong>{report.reporter_name}</p>
        <p><strong>举报时间：</strong>{report.report_time}</p>
        <p><strong>举报原因：</strong>{reason if reason else '未填写'}</p>
        """
        email_service.send_admin_notification(system_config.admin_email, '举报事件', details)

    return jsonify({'success': True, 'message': '举报已提交', 'report': report.to_dict()})


# ── 我的记录 ──

@attendance_bp.route('/api/attendance/my_records')
@login_required
def api_my_records():
    user = get_current_user()
    records = record_get_by_user(user.user_id)

    one_week_ago = datetime.now() - timedelta(days=7)
    recent = []
    for r in records:
        check_in_dt = parse_datetime(r.check_in)
        if check_in_dt >= one_week_ago:
            appeals = appeal_get_by_record_id(r.record_id)
            appeal_info = appeals[0].to_dict() if appeals else None
            recent.append({**r.to_dict(), 'duration_minutes': r.get_duration_minutes(), 'appeal': appeal_info})

    all_records = sorted(records, key=lambda x: x.check_in, reverse=True)
    all_with_appeals = []
    for r in all_records:
        appeals = appeal_get_by_record_id(r.record_id)
        appeal_info = appeals[0].to_dict() if appeals else None
        all_with_appeals.append({**r.to_dict(), 'duration_minutes': r.get_duration_minutes(), 'appeal': appeal_info})

    return jsonify({'success': True, 'recent_records': recent, 'all_records': all_with_appeals})


# ── 申诉 ──

@attendance_bp.route('/api/attendance/appeal', methods=['POST'])
@login_required
def api_appeal():
    system_config = current_app.config.get('system_config')
    email_service = current_app.config.get('email_service')

    user = get_current_user()
    if user.status == User.STATUS_LOCKED:
        return jsonify({'success': False, 'message': '账号已锁定，无法申诉'}), 403

    data = request.json
    record_id = data.get('record_id')
    reason = data.get('reason', '')
    new_check_out = data.get('new_check_out')
    evidence_images = data.get('evidence_images', [])

    record = record_get_by_id(record_id)
    if not record:
        return jsonify({'success': False, 'message': '记录不存在'}), 404
    if record.user_id != user.user_id:
        return jsonify({'success': False, 'message': '无权申诉此记录'}), 403

    existing = appeal_get_by_record_id(record_id)
    if existing:
        return jsonify({'success': False, 'message': '该记录已提交过申诉'}), 400

    appeal = Appeal(
        appeal_id=generate_appeal_id(),
        record_id=record_id,
        user_id=user.user_id,
        username=user.username,
        appeal_time=datetime.now().isoformat(),
        original_check_in=record.check_in,
        original_check_out=record.check_out,
        reason=reason,
        evidence_images=evidence_images,
        new_check_out=new_check_out,
        status=Appeal.STATUS_PENDING
    )
    appeal_add(appeal)

    if system_config.email_enabled:
        details = f"""
        <p><strong>申诉人：</strong>{user.username} ({user.user_id})</p>
        <p><strong>申诉时间：</strong>{appeal.appeal_time}</p>
        <p><strong>原始签退时间：</strong>{record.check_out if record.check_out else '未签退'}</p>
        <p><strong>申诉签退时间：</strong>{new_check_out}</p>
        <p><strong>申诉理由：</strong>{reason if reason else '未填写'}</p>
        """
        email_service.send_admin_notification(system_config.admin_email, '申诉事件', details)

    return jsonify({'success': True, 'message': '申诉已提交', 'appeal': appeal.to_dict()})


# ── 图片上传 ──

@attendance_bp.route('/api/upload/image', methods=['POST'])
@login_required
def api_upload_image():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'}), 400

    file = request.files['file']
    if not file.filename:
        return jsonify({'success': False, 'message': '没有选择文件'}), 400

    allowed = {'jpg', 'jpeg', 'png', 'gif', 'webp'}
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in allowed:
        return jsonify({'success': False, 'message': '不支持的图片格式'}), 400

    file.seek(0, 2)
    file_size = file.tell()
    file.seek(0)
    if file_size > 5 * 1024 * 1024:
        return jsonify({'success': False, 'message': '图片大小不能超过5MB'}), 400

    random_name = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(os.path.dirname(__file__), '..', 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, random_name)
    file.save(filepath)

    return jsonify({'success': True, 'message': '上传成功', 'url': f'/static/uploads/{random_name}'})


# ── 签到排行 ──

@attendance_bp.route('/api/attendance/rankings')
@login_required
def api_rankings():
    system_config = current_app.config.get('system_config')

    period = request.args.get('period', 'week')
    if period == 'week':
        start_date, end_date = get_week_range()
    elif period == 'month':
        start_date, end_date = get_month_range()
    else:
        start_date, end_date = get_semester_range()

    ranking_include = system_config.ranking_include_users if system_config.ranking_include_users else None
    is_explicit = ranking_include is not None

    all_records = record_get_all()
    filtered = filter_records_for_ranking(
        all_records,
        start_date=start_date,
        end_date=end_date,
        valid_only=True,
        include_users=ranking_include,
        exclude_users=None
    )

    if not is_explicit:
        filtered = [r for r in filtered if filter_user_for_ranking(r['user_id'])]

    rankings = compute_ranking(filtered, show_records=False)
    return jsonify({'success': True, 'rankings': rankings, 'period': period})


# ── 公示 ──

@attendance_bp.route('/api/attendance/publications')
@login_required
def api_publications():
    pubs = pub_get_active()
    return jsonify({'success': True, 'publications': [p.to_dict() for p in pubs]})


@attendance_bp.route('/api/attendance/publication/<pub_id>')
@login_required
def api_publication_detail(pub_id):
    pub = pub_get_by_id(pub_id)
    if not pub:
        return jsonify({'success': False, 'message': '公示不存在'}), 404

    all_records = record_get_all()
    filtered = filter_records_for_ranking(
        all_records,
        start_date=pub.start_date,
        end_date=pub.end_date,
        valid_only=not pub.show_invalid_records,
        include_users=pub.include_users if pub.include_users else None,
        exclude_users=pub.exclude_users if pub.exclude_users else None
    )

    # 公示不强制排除管理员，由 include_users 控制参与范围
    filtered = [
        r for r in filtered
        if user_find_by_user_id(r['user_id']) and user_find_by_user_id(r['user_id']).status not in [User.STATUS_DISABLED, User.STATUS_LOCKED]
    ]

    rankings = compute_ranking(filtered, show_records=pub.show_records)
    return jsonify({'success': True, 'publication': pub.to_dict(), 'rankings': rankings})