"""
管理后台路由
- 签到记录管理
- 公示管理
- 举报/申诉处理
- 用户管理
- 系统配置
"""
from flask import Blueprint, request, jsonify, render_template, current_app
from datetime import datetime, timedelta
import csv
import io

from db import (
    User, AttendanceRecord, Report, Appeal, Publication,
    user_find_by_user_id, user_create, user_update, user_get_all,
    record_add, record_get_by_id, record_get_all, record_update,
    generate_record_id,
    report_get_all, report_get_by_id, report_update,
    appeal_get_all, appeal_get_by_id, appeal_update,
    pub_get_all, pub_get_by_id, pub_add, pub_update, pub_delete,
    generate_pub_id,
    sys_config_save,
)
from services.ranking import compute_ranking, filter_records_for_ranking
from tool_func import login_required, admin_required, get_current_user

management_bp = Blueprint('management', __name__)


# ── 管理主页 ──

@management_bp.route('/management')
@login_required
@admin_required
def management_page():
    return render_template('management.html',
                           is_super_admin=get_current_user().user_type == User.TYPE_SUPER_ADMIN)


# ── 签到记录管理 ──

@management_bp.route('/api/management/records')
@admin_required
def api_management_records():
    user_filter = request.args.get('user_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    records = record_get_all()

    if user_filter:
        records = [r for r in records if r.user_id == user_filter]
    if start_date:
        records = [r for r in records if r.check_in[:10] >= start_date]
    if end_date:
        records = [r for r in records if r.check_in[:10] <= end_date]

    records = sorted(records, key=lambda x: x.check_in, reverse=True)
    return jsonify({
        'success': True,
        'records': [{**r.to_dict(), 'duration_minutes': r.get_duration_minutes()} for r in records]
    })


@management_bp.route('/api/management/record', methods=['POST'])
@admin_required
def api_add_record():
    data = request.json
    user_id = data.get('user_id')
    check_in = data.get('check_in')
    check_out = data.get('check_out')

    user = user_find_by_user_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    check_out = normalize_check_out(check_in, check_out)

    record = AttendanceRecord(
        record_id=generate_record_id(),
        user_id=user_id,
        username=user.username,
        check_in=check_in,
        check_out=check_out,
        status=AttendanceRecord.STATUS_VALID
    )
    record_add(record)
    return jsonify({'success': True, 'message': '记录添加成功', 'record': record.to_dict()})


def normalize_check_out(check_in, check_out):
    """修正签退时间：若签退时间早于签到时间，自动推到次日"""
    if not check_in or not check_out:
        return check_out
    try:
        dt_in = datetime.strptime(check_in, '%Y-%m-%d %H:%M:%S')
        dt_out = datetime.strptime(check_out, '%Y-%m-%d %H:%M:%S')
        if dt_out < dt_in:
            dt_out += timedelta(days=1)
            return dt_out.strftime('%Y-%m-%d %H:%M:%S')
    except ValueError:
        pass
    return check_out


@management_bp.route('/api/management/record/<record_id>', methods=['PUT'])
@admin_required
def api_update_record(record_id):
    data = request.json
    record = record_get_by_id(record_id)
    if not record:
        return jsonify({'success': False, 'message': '记录不存在'}), 404

    if 'check_in' in data:
        record.check_in = data['check_in']
    if 'check_out' in data:
        record.check_out = data['check_out']
    if 'status' in data:
        record.status = data['status']

    record_update(record)
    return jsonify({'success': True, 'message': '记录更新成功', 'record': record.to_dict()})


def normalize_datetime(dt_str):
    """将各种时间格式统一为 YYYY-MM-DD HH:MM:SS，高容错"""
    if not dt_str:
        return None
    dt_str = dt_str.strip()
    if not dt_str:
        return None

    # 统一分隔符：/ 和 . 替换为 -；中文年月日替换
    for sep in ['/', '.', '年', '月']:
        dt_str = dt_str.replace(sep, '-')
    dt_str = dt_str.replace('日', '').replace('号', '')

    # 去掉多余的空白
    dt_str = ' '.join(dt_str.split())

    # 补全秒：如果时间只有 HH:MM，补 :00
    parts = dt_str.split(' ')
    if len(parts) == 2:
        time_part = parts[1]
        if time_part.count(':') == 1:
            dt_str = parts[0] + ' ' + time_part + ':00'

    formats = [
        '%Y-%m-%d %H:%M:%S',   # 2025-1-5 8:30:00
        '%Y-%m-%d %H:%M',      # 2025-1-5 8:30
        '%Y-%m-%dT%H:%M:%S',   # ISO without ms
        '%Y-%m-%dT%H:%M:%S.%f',# ISO with ms
        '%Y-%m-%dT%H:%M',      # ISO short
        '%Y%m%d %H:%M:%S',     # 20250105 08:30:00 (compact date)
        '%Y%m%dT%H:%M:%S',     # compact ISO
    ]
    for fmt in formats:
        try:
            return datetime.strptime(dt_str, fmt).strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            continue
    return None


@management_bp.route('/api/management/records/batch_create', methods=['POST'])
@admin_required
def api_batch_create():
    """批量创建记录（前端预览编辑后提交）"""
    data = request.json
    records = data.get('records', [])
    if not records:
        return jsonify({'success': False, 'message': '没有记录'}), 400

    added = 0
    skipped = 0
    for item in records:
        try:
            user_id = item.get('user_id', '').strip()
            username = item.get('username', '').strip()
            check_in = normalize_datetime(item.get('check_in', ''))
            check_out = normalize_datetime(item.get('check_out', ''))
            status = item.get('status', 'valid')

            if not user_id or not check_in:
                skipped += 1
                continue

            user = user_find_by_user_id(user_id)
            if not user:
                skipped += 1
                continue

            # 优先用前端传入的姓名，否则用数据库中的
            display_name = username if username else user.username

            check_out = normalize_check_out(check_in, check_out) if check_out else None
            if status not in ('valid', 'invalid'):
                status = 'valid'

            record = AttendanceRecord(
                record_id=generate_record_id(),
                user_id=user_id, username=display_name,
                check_in=check_in, check_out=check_out,
                status=status
            )
            record_add(record)
            added += 1
        except Exception:
            skipped += 1
            continue

    msg = f'成功导入 {added} 条记录'
    if skipped:
        msg += f'，跳过 {skipped} 条'
    return jsonify({'success': True, 'message': msg})


@management_bp.route('/api/management/records/batch_import', methods=['POST'])
@admin_required
def api_batch_import():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'}), 400

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'success': False, 'message': '只支持CSV文件'}), 400

    content = file.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))

    added_count = 0
    skip_count = 0
    for row in reader:
        try:
            user_id = row.get('user_id', '').strip()
            username = row.get('username', '').strip()
            check_in = normalize_datetime(row.get('check_in', ''))
            check_out = normalize_datetime(row.get('check_out', ''))
            check_out = normalize_check_out(check_in, check_out) if check_out else None

            # 读取状态字段，支持 valid/有效 或 invalid/无效
            raw_status = row.get('status', '').strip()
            if raw_status in ('有效', 'valid'):
                status = 'valid'
            elif raw_status in ('无效', 'invalid'):
                status = 'invalid'
            else:
                status = 'valid'

            if not user_id or not check_in:
                skip_count += 1
                continue
            user = user_find_by_user_id(user_id)
            if not user:
                skip_count += 1
                continue
            display_name = username if username else user.username
            record = AttendanceRecord(
                record_id=generate_record_id(),
                user_id=user_id, username=display_name,
                check_in=check_in, check_out=check_out,
                status=status
            )
            record_add(record)
            added_count += 1
        except Exception:
            skip_count += 1
            continue

    msg = f'成功导入{added_count}条记录'
    if skip_count > 0:
        msg += f'，跳过{skip_count}条格式有问题的记录'
    return jsonify({'success': True, 'message': msg})


@management_bp.route('/api/management/records/delete_by_year', methods=['POST'])
@admin_required
def api_delete_records_by_year():
    """删除指定年份的所有签到记录"""
    data = request.json
    year = data.get('year', '')
    if not year:
        return jsonify({'success': False, 'message': '请指定年份'}), 400
    deleted = record_delete_by_year(year)
    return jsonify({'success': True, 'message': f'已删除 {deleted} 条 {year} 年的签到记录'})


@management_bp.route('/api/management/records/export')
@admin_required
def api_export_records():
    user_filter = request.args.get('user_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    records = record_get_all()
    if user_filter:
        records = [r for r in records if r.user_id == user_filter]
    if start_date:
        records = [r for r in records if r.check_in[:10] >= start_date]
    if end_date:
        records = [r for r in records if r.check_in[:10] <= end_date]
    records = sorted(records, key=lambda x: x.check_in, reverse=True)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['record_id', 'user_id', 'username', 'check_in', 'check_out', 'status', 'duration_minutes'])
    for r in records:
        writer.writerow([r.record_id, r.user_id, r.username, r.check_in,
                         r.check_out if r.check_out else '', r.status, r.get_duration_minutes()])
    output.seek(0)

    return current_app.response_class(
        response='\ufeff' + output.getvalue(),
        status=200, mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=attendance_records.csv'}
    )


# ── 举报管理 ──

@management_bp.route('/api/management/reports')
@admin_required
def api_management_reports():
    reports = report_get_all()
    return jsonify({'success': True, 'reports': [r.to_dict() for r in reports]})


@management_bp.route('/api/management/report/<report_id>', methods=['PUT'])
@admin_required
def api_process_report(report_id):
    data = request.json
    user = get_current_user()

    report = report_get_by_id(report_id)
    if not report:
        return jsonify({'success': False, 'message': '举报不存在'}), 404

    action = data.get('action')

    if report.report_type == Report.TYPE_ONLINE:
        if action == 'valid':
            report.status = Report.STATUS_VALID
            report.processed_by = user.user_id
            report.processed_at = datetime.now().isoformat()
            report.process_result = '举报有效'
        elif action == 'invalid':
            report.status = Report.STATUS_INVALID
            report.processed_by = user.user_id
            report.processed_at = datetime.now().isoformat()
            report.process_result = data.get('process_result', '')
            # 恢复被举报的记录：使用 report 中存储的 reported_record_id
            if report.reported_record_id:
                record = record_get_by_id(report.reported_record_id)
                if record:
                    if report.check_out_time:
                        record.check_out = report.check_out_time
                    record.status = AttendanceRecord.STATUS_VALID
                    record_update(record)

    elif report.report_type == Report.TYPE_RANKING:
        if action == 'processed':
            report.status = Report.STATUS_PROCESSED
            report.processed_by = user.user_id
            report.processed_at = datetime.now().isoformat()
            report.process_result = '已处理'
        elif action == 'pending':
            report.status = Report.STATUS_PENDING
            report.processed_by = None
            report.processed_at = None
            report.process_result = ''

    report_update(report)
    return jsonify({'success': True, 'message': '处理成功', 'report': report.to_dict()})


# ── 申诉管理 ──

@management_bp.route('/api/management/appeals')
@admin_required
def api_management_appeals():
    appeals = appeal_get_all()
    return jsonify({'success': True, 'appeals': [a.to_dict() for a in appeals]})


@management_bp.route('/api/management/appeal/<appeal_id>', methods=['PUT'])
@admin_required
def api_process_appeal(appeal_id):
    data = request.json
    user = get_current_user()

    appeal = appeal_get_by_id(appeal_id)
    if not appeal:
        return jsonify({'success': False, 'message': '申诉不存在'}), 404

    action = data.get('action')

    if action == 'valid':
        appeal.status = Appeal.STATUS_VALID
        appeal.processed_by = user.user_id
        appeal.processed_at = datetime.now().isoformat()
        appeal.process_result = '申诉有效'
        record = record_get_by_id(appeal.record_id)
        if record:
            record.status = AttendanceRecord.STATUS_VALID
            if appeal.new_check_out:
                record.check_out = appeal.new_check_out
            record_update(record)
    elif action == 'invalid':
        appeal.status = Appeal.STATUS_INVALID
        appeal.processed_by = user.user_id
        appeal.processed_at = datetime.now().isoformat()
        appeal.process_result = data.get('process_result', '')

    appeal_update(appeal)
    return jsonify({'success': True, 'message': '处理成功', 'appeal': appeal.to_dict()})


# ── 用户管理 ──

@management_bp.route('/api/management/users')
@admin_required
def api_management_users():
    users = user_get_all()
    return jsonify({'success': True, 'users': [u.to_dict() for u in users]})


@management_bp.route('/api/management/user', methods=['POST'])
@admin_required
def api_add_user():
    data = request.json
    current_user = get_current_user()

    user_id = data.get('user_id')
    username = data.get('username')
    email = data.get('email', '')
    requested_type = data.get('user_type', User.TYPE_REGULAR)

    if user_find_by_user_id(user_id):
        return jsonify({'success': False, 'message': '用户已存在'}), 400

    if requested_type == User.TYPE_SUPER_ADMIN:
        if current_user.user_type != User.TYPE_SUPER_ADMIN:
            return jsonify({'success': False, 'message': '无权创建超管'}), 403
        user_type = User.TYPE_SUPER_ADMIN
    elif requested_type == User.TYPE_ADMIN:
        user_type = User.TYPE_ADMIN
    else:
        user_type = User.TYPE_REGULAR

    user = user_create(user_id=user_id, username=username, oauth_id=user_id,
                       email=email, user_type=user_type)
    return jsonify({'success': True, 'message': '用户添加成功', 'user': user.to_dict()})


@management_bp.route('/api/management/user/<user_id>', methods=['PUT'])
@admin_required
def api_update_user(user_id):
    data = request.json
    user = user_find_by_user_id(user_id)
    if not user:
        return jsonify({'success': False, 'message': '用户不存在'}), 404

    current_user = get_current_user()
    if user.user_type == User.TYPE_SUPER_ADMIN and current_user.user_type != User.TYPE_SUPER_ADMIN:
        return jsonify({'success': False, 'message': '无权修改超管'}), 403

    if 'username' in data:
        user.username = data['username']
    if 'status' in data:
        if user.user_type == User.TYPE_SUPER_ADMIN:
            return jsonify({'success': False, 'message': '超管状态不可修改'}), 403
        user.status = data['status']
    if 'user_type' in data:
        if user.user_type == User.TYPE_SUPER_ADMIN:
            return jsonify({'success': False, 'message': '超管类型不可修改'}), 403
        if data['user_type'] == User.TYPE_SUPER_ADMIN:
            return jsonify({'success': False, 'message': '无法设置为超管'}), 403
        user.user_type = data['user_type']
    if 'email' in data:
        user.email = data['email']

    user_update(user)
    return jsonify({'success': True, 'message': '用户更新成功', 'user': user.to_dict()})


@management_bp.route('/api/management/users/batch_import', methods=['POST'])
@admin_required
def api_users_batch_import():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '没有上传文件'}), 400

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({'success': False, 'message': '只支持CSV文件'}), 400

    current_user = get_current_user()
    content = file.read().decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(content))

    added_count = 0
    for row in reader:
        user_id = row.get('user_id')
        username = row.get('username')
        email = row.get('email', '')
        requested_type = row.get('user_type', User.TYPE_REGULAR)

        if user_find_by_user_id(user_id):
            continue

        if requested_type == User.TYPE_SUPER_ADMIN:
            if current_user.user_type != User.TYPE_SUPER_ADMIN:
                continue
            final_type = User.TYPE_SUPER_ADMIN
        elif requested_type == User.TYPE_ADMIN:
            final_type = User.TYPE_ADMIN
        else:
            final_type = User.TYPE_REGULAR

        user_create(user_id=user_id, username=username, oauth_id=user_id,
                    email=email, user_type=final_type)
        added_count += 1

    return jsonify({'success': True, 'message': f'成功导入{added_count}个用户'})


@management_bp.route('/api/management/users/export')
@admin_required
def api_export_users():
    users = user_get_all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['user_id', 'username', 'email', 'user_type', 'status'])
    for u in users:
        writer.writerow([u.user_id, u.username, u.email, u.user_type, u.status])
    output.seek(0)
    return current_app.response_class(
        response='\ufeff' + output.getvalue(),
        status=200, mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=users.csv'}
    )


# ── 公示管理 ──

def _is_user_active_for_pub(user_id):
    """检查用户是否可在公示中展示（排除不存在/禁用/锁定，但不排除管理员）"""
    user = user_find_by_user_id(user_id)
    if not user:
        return False
    if user.status in [User.STATUS_DISABLED, User.STATUS_LOCKED]:
        return False
    return True


@management_bp.route('/api/management/publications')
@admin_required
def api_management_publications():
    pubs = pub_get_all()
    return jsonify({'success': True, 'publications': [p.to_dict() for p in pubs]})


@management_bp.route('/api/management/publication', methods=['POST'])
@admin_required
def api_create_publication():
    data = request.json
    name = data.get('name')
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    include_users = data.get('include_users', [])
    exclude_users = data.get('exclude_users', [])
    show_records = data.get('show_records', True)
    show_invalid_records = data.get('show_invalid_records', False)

    if not name:
        name = f"{int(start_date[:4])}年{int(start_date[5:7])}月签到公示" if start_date else "签到公示"

    pub = Publication(
        pub_id=generate_pub_id(),
        name=name,
        start_date=start_date,
        end_date=end_date,
        created_at=datetime.now().isoformat(),
        include_users=include_users,
        exclude_users=exclude_users,
        is_active=True,
        show_records=show_records,
        show_invalid_records=show_invalid_records
    )
    pub_add(pub)
    return jsonify({'success': True, 'message': '公示创建成功', 'publication': pub.to_dict()})


@management_bp.route('/api/management/publication/<pub_id>', methods=['PUT'])
@admin_required
def api_update_publication(pub_id):
    data = request.json
    pub = pub_get_by_id(pub_id)
    if not pub:
        return jsonify({'success': False, 'message': '公示不存在'}), 404

    if 'name' in data:
        pub.name = data['name']
    if 'start_date' in data:
        pub.start_date = data['start_date']
    if 'end_date' in data:
        pub.end_date = data['end_date']
    if 'is_active' in data:
        pub.is_active = data['is_active']
    if 'include_users' in data:
        pub.include_users = data['include_users']
    if 'exclude_users' in data:
        pub.exclude_users = data.get('exclude_users', [])
    if 'show_records' in data:
        pub.show_records = data['show_records']
    if 'show_invalid_records' in data:
        pub.show_invalid_records = data['show_invalid_records']

    pub_update(pub)
    return jsonify({'success': True, 'message': '公示更新成功', 'publication': pub.to_dict()})


@management_bp.route('/api/management/publication/<pub_id>', methods=['DELETE'])
@admin_required
def api_delete_publication(pub_id):
    pub_delete(pub_id)
    return jsonify({'success': True, 'message': '公示删除成功'})


@management_bp.route('/api/management/publication/<pub_id>/rankings')
@admin_required
def api_pub_rankings(pub_id):
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
    # 仅排除不存在和锁定/禁用的用户（他们无法签到，不会有记录）
    filtered = [
        r for r in filtered
        if _is_user_active_for_pub(r['user_id'])
    ]

    rankings = compute_ranking(filtered, show_records=pub.show_records)
    return jsonify({'success': True, 'rankings': rankings})


@management_bp.route('/api/management/publication/<pub_id>/export')
@admin_required
def api_pub_export(pub_id):
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
        if _is_user_active_for_pub(r['user_id'])
    ]
    rankings_data = compute_ranking(filtered, show_records=pub.show_records)

    # 记录明细：直接复用 filtered 结果，无需重新遍历 all_records
    records_data = [
        {
            'user_id': r['user_id'],
            'username': r['username'],
            'check_in': r['check_in'],
            'check_out': r.get('check_out', '未签退'),
            'duration_minutes': r.get('duration_minutes', 0),
            'status': r.get('status', AttendanceRecord.STATUS_VALID)
        }
        for r in filtered
    ]

    output = io.StringIO()
    output.write("=== 签到排名 ===\n")
    writer = csv.writer(output)
    writer.writerow(['排名', '编号', '姓名', '签到时长'])
    for r in rankings_data:
        writer.writerow([r['rank'], r['user_id'], r['username'], r['duration_str']])

    output.write("\n=== 签到记录 ===\n")
    writer.writerow(['编号', '姓名', '签到时间', '签退时间', '签到时长', '状态'])
    for r in records_data:
        writer.writerow([r['user_id'], r['username'], r['check_in'],
                         r['check_out'] if r['check_out'] else '未签退',
                         r['duration_minutes'], r['status']])
    output.seek(0)

    safe_name = f"publication_{pub.pub_id}.csv"
    return current_app.response_class(
        response='\ufeff' + output.getvalue(),
        status=200, mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{safe_name}"'}
    )


# ── 系统配置 ──

@management_bp.route('/api/management/system_config')
@admin_required
def api_get_system_config():
    system_config = current_app.config.get('system_config')
    return jsonify({
        'success': True,
        'config': {
            'attendance_start_time': system_config.attendance_start_time,
            'attendance_end_time': system_config.attendance_end_time,
            'attendance_interval_seconds': system_config.attendance_interval_seconds,
            'attendance_reminder_minutes': system_config.attendance_reminder_minutes,
            'session_expire_seconds': system_config.session_expire_seconds,
            'email_enabled': system_config.email_enabled,
            'email_time_start': system_config.email_time_start,
            'email_time_end': system_config.email_time_end,
            'admin_email': system_config.admin_email,
            'sender_address': system_config.sender_address,
            'sender_name': system_config.sender_name,
            'smtp_host': system_config.smtp_host,
            'smtp_port': system_config.smtp_port,
            'allowed_ip_ranges': system_config.allowed_ip_ranges,
            'ranking_include_users': system_config.ranking_include_users,
            'smtp_username': system_config.smtp_username,
            'smtp_password': '******' if system_config.smtp_password else '',
            'oauth_enabled': system_config.oauth_enabled,
            'oauth_client_id': system_config.oauth_client_id,
            'oauth_client_secret': '******' if system_config.oauth_client_secret else '',
            'oauth_redirect_uri': system_config.oauth_redirect_uri,
            'oauth_authorize_url': system_config.oauth_authorize_url,
            'oauth_token_url': system_config.oauth_token_url,
            'oauth_userinfo_url': system_config.oauth_userinfo_url
        }
    })


@management_bp.route('/api/management/system_config', methods=['PUT'])
@admin_required
def api_update_system_config():
    data = request.json
    system_config = current_app.config.get('system_config')
    email_service = current_app.config.get('email_service')

    if 'attendance_start_time' in data:
        system_config.attendance_start_time = data['attendance_start_time']
    if 'attendance_end_time' in data:
        system_config.attendance_end_time = data['attendance_end_time']
    if 'attendance_interval_seconds' in data:
        system_config.attendance_interval_seconds = int(data['attendance_interval_seconds'])
    if 'attendance_reminder_minutes' in data:
        system_config.attendance_reminder_minutes = int(data['attendance_reminder_minutes'])
    if 'session_expire_seconds' in data:
        system_config.session_expire_seconds = int(data['session_expire_seconds'])
        current_app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=system_config.session_expire_seconds)
    if 'email_enabled' in data:
        system_config.email_enabled = bool(data['email_enabled'])
    if 'email_time_start' in data:
        system_config.email_time_start = data['email_time_start']
    if 'email_time_end' in data:
        system_config.email_time_end = data['email_time_end']
    if 'admin_email' in data:
        system_config.admin_email = data['admin_email']
    if 'sender_address' in data:
        system_config.sender_address = data['sender_address']
    if 'sender_name' in data:
        system_config.sender_name = data['sender_name']
    if 'smtp_username' in data:
        system_config.smtp_username = data['smtp_username']
    if 'smtp_password' in data and data['smtp_password'] is not None:
        system_config.smtp_password = data['smtp_password']
    if 'smtp_host' in data:
        system_config.smtp_host = data['smtp_host']
    if 'smtp_port' in data:
        system_config.smtp_port = int(data['smtp_port'])
    if 'allowed_ip_ranges' in data:
        system_config.allowed_ip_ranges = data['allowed_ip_ranges']
    if 'ranking_include_users' in data:
        system_config.ranking_include_users = data['ranking_include_users']
    if 'oauth_enabled' in data:
        system_config.oauth_enabled = bool(data['oauth_enabled'])
    if 'oauth_client_id' in data:
        system_config.oauth_client_id = data['oauth_client_id']
    if 'oauth_client_secret' in data and data['oauth_client_secret'] is not None:
        system_config.oauth_client_secret = data['oauth_client_secret']
    if 'oauth_redirect_uri' in data:
        system_config.oauth_redirect_uri = data['oauth_redirect_uri']
    if 'oauth_authorize_url' in data:
        system_config.oauth_authorize_url = data['oauth_authorize_url']
    if 'oauth_token_url' in data:
        system_config.oauth_token_url = data['oauth_token_url']
    if 'oauth_userinfo_url' in data:
        system_config.oauth_userinfo_url = data['oauth_userinfo_url']

    sys_config_save(system_config)
    return jsonify({'success': True, 'message': '系统配置更新成功'})


@management_bp.route('/api/management/system_config/test_email', methods=['POST'])
@admin_required
def api_test_email():
    email_service = current_app.config.get('email_service')
    success, message = email_service.send_test_email()
    if success:
        return jsonify({'success': True, 'message': '测试邮件发送成功'})
    else:
        return jsonify({'success': False, 'message': f'测试邮件发送失败: {message}'}), 500