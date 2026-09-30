"""
后台任务调度器
- 强制签退检查（定时将未签退的用户标记为已签退）
- 签退提醒邮件（精确延时到提醒时间发送一次）
- 邮件队列刷新（定期发送因时间窗口延迟的邮件）
"""
import threading
import time
from datetime import datetime, timedelta


def start_background_tasks(app):
    """启动所有后台任务线程"""

    def _run_force_checkout():
        force_checkout(app)

    def _run_reminder():
        checkout_reminder(app)

    def _run_email_flush():
        email_queue_flush(app)

    force_thread = threading.Thread(target=_run_force_checkout, daemon=True)
    force_thread.start()

    reminder_thread = threading.Thread(target=_run_reminder, daemon=True)
    reminder_thread.start()

    email_flush_thread = threading.Thread(target=_run_email_flush, daemon=True)
    email_flush_thread.start()


def force_checkout(app):
    """每60秒检查一次，强制签退未签退的用户"""
    while True:
        time.sleep(60)
        try:
            _force_checkout_all(app)
        except Exception as e:
            print(f"[Scheduler] force_checkout error: {e}")


def _force_checkout_all(app):
    """执行强制签退逻辑"""
    from db import record_get_online, record_update, AttendanceRecord
    from tool_func import parse_datetime

    online_records = record_get_online()
    system_config = app.config.get('system_config')

    now = datetime.now()
    current_time = now.strftime('%H:%M')
    end_time = system_config.attendance_end_time

    if current_time < end_time:
        return

    for record in online_records:
        check_in = parse_datetime(record.check_in)
        if check_in.date() <= now.date():
            # 当天或昨天未签退的记录，标记为无效
            record.status = AttendanceRecord.STATUS_INVALID
            record_update(record)
            print(f"[Scheduler] 过期记录标记无效: {record.user_id} ({record.username})")


def checkout_reminder(app):
    """精确延时到提醒时间，每天只发送一次签退提醒"""
    last_reminder_date = None  # 记录上次发送提醒的日期

    while True:
        time.sleep(30)  # 每30秒检查一次配置变化
        try:
            system_config = app.config.get('system_config')
            if not system_config or not system_config.email_enabled:
                continue

            reminder_minutes = system_config.attendance_reminder_minutes
            if reminder_minutes <= 0:
                continue  # 设置为0则不提醒

            now = datetime.now()
            end_h, end_m = map(int, system_config.attendance_end_time.split(':'))
            end_time = now.replace(hour=end_h, minute=end_m, second=0, microsecond=0)
            reminder_time = end_time - timedelta(minutes=reminder_minutes)

            # 如果提醒时间已过，算作明天的
            if now >= reminder_time:
                # 如果今天还没发过且还在延迟窗口内（10分钟内），补发
                today_str = now.strftime('%Y%m%d')
                if last_reminder_date != today_str and now < reminder_time + timedelta(minutes=10):
                    _send_reminders(app)
                    last_reminder_date = today_str
                continue

            # 距离提醒时间还有多久
            wait_seconds = (reminder_time - now).total_seconds()
            if wait_seconds <= 0:
                continue

            # 精确等待到提醒时间
            print(f"[Scheduler] 签退提醒将在 {reminder_time.strftime('%H:%M:%S')} 发送（{int(wait_seconds)}秒后）")
            time.sleep(wait_seconds)

            # 重新读取配置（可能在等待期间被修改）
            system_config = app.config.get('system_config')
            reminder_minutes = system_config.attendance_reminder_minutes
            if reminder_minutes <= 0:
                continue

            today_str = datetime.now().strftime('%Y%m%d')
            if last_reminder_date != today_str:
                _send_reminders(app)
                last_reminder_date = today_str
                print(f"[Scheduler] 签退提醒已发送")

        except Exception as e:
            print(f"[Scheduler] checkout_reminder error: {e}")


def _send_reminders(app):
    """向未签退用户发送提醒邮件（仅当天记录，每人只取最近一条）"""
    from db import record_get_online, user_find_by_user_id
    from datetime import date

    system_config = app.config.get('system_config')
    email_service = app.config.get('email_service')
    if not email_service:
        return

    online_records = record_get_online()
    today_str = date.today().isoformat()

    # 筛选当天记录，每人只保留最近一条
    user_latest = {}
    for record in online_records:
        # 仅当天签到记录
        if record.check_in[:10] != today_str:
            continue
        if record.user_id not in user_latest or record.check_in > user_latest[record.user_id].check_in:
            user_latest[record.user_id] = record

    for user_id, record in user_latest.items():
        user = user_find_by_user_id(user_id)
        if user and user.email:
            email_service.send_check_out_reminder(
                user.email, user.username, system_config.attendance_end_time
            )
            print(f"[Scheduler] 发送签退提醒: {user.email}")


def email_queue_flush(app):
    """每30秒检查一次，若在时间窗口内则发送队列中的延迟邮件"""
    while True:
        time.sleep(30)
        try:
            email_service = app.config.get('email_service')
            if email_service:
                email_service.flush_queue()
        except Exception as e:
            print(f"[Scheduler] email_queue_flush error: {e}")