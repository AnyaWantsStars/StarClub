import smtplib
import os
import threading
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.header import Header

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), 'templates', 'email')


class EmailService:
    def __init__(self, system_config):
        self.config = system_config
        self._queue = []          # 延迟发送队列: [(to_email, subject, html_content), ...]
        self._queue_lock = threading.Lock()

    def _is_in_time_window(self):
        """检查当前时间是否在允许发送邮件的时间范围内"""
        now = datetime.now()
        current = now.strftime('%H:%M')
        start = self.config.email_time_start
        end = self.config.email_time_end

        if start <= end:
            # 正常范围，如 06:00-23:59
            return start <= current <= end
        else:
            # 跨天范围，如 23:00-06:00
            return current >= start or current <= end

    def _enqueue(self, to_email, subject, html_content):
        """将邮件加入延迟队列"""
        with self._queue_lock:
            self._queue.append((to_email, subject, html_content))
            print(f"[EmailService] 邮件已加入延迟队列（当前共 {len(self._queue)} 封）")

    def flush_queue(self):
        """发送队列中所有延迟邮件（由调度器定期调用）"""
        if not self._is_in_time_window():
            return

        with self._queue_lock:
            if not self._queue:
                return
            pending = self._queue[:]
            self._queue.clear()

        print(f"[EmailService] 正在发送 {len(pending)} 封延迟邮件...")
        for to_email, subject, html_content in pending:
            success, msg = self._send_raw(to_email, subject, html_content)
            if not success:
                print(f"[EmailService] 延迟邮件发送失败 ({to_email}): {msg}")

    def _send_raw(self, to_email, subject, html_content):
        """底层发送（不做时间检查）"""
        if not self.config.email_enabled:
            return False, "Email disabled"

        try:
            msg = MIMEMultipart('alternative')
            from_name = Header(self.config.sender_name, 'utf-8').encode()
            msg['From'] = f"{from_name} <{self.config.sender_address}>"
            msg['To'] = to_email
            msg['Subject'] = subject

            msg.attach(MIMEText(html_content, 'html', 'utf-8'))

            if self.config.smtp_port == 465:
                with smtplib.SMTP_SSL(self.config.smtp_host, self.config.smtp_port) as server:
                    server.login(self.config.smtp_username, self.config.smtp_password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                    server.starttls()
                    server.login(self.config.smtp_username, self.config.smtp_password)
                    server.send_message(msg)

            return True, "Email sent"
        except Exception as e:
            return False, str(e)

    def send_email(self, to_email, subject, html_content, skip_time_check=False):
        """
        发送邮件。若不在时间窗口内且非 skip_time_check，则加入延迟队列。
        测试邮件使用 skip_time_check=True 绕过时间限制。
        """
        if not skip_time_check and not self._is_in_time_window():
            self._enqueue(to_email, subject, html_content)
            return True, "Queued"  # 入队视为成功，避免调用方报错

        return self._send_raw(to_email, subject, html_content)

    def _render(self, title, body):
        """渲染统一邮件模板"""
        template_path = os.path.join(TEMPLATE_DIR, 'base.html')
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
        return template.replace('{{ title }}', title).replace('{{ body }}', body)

    def send_check_out_reminder(self, email, username, check_out_time="23:30"):
        subject = "【签退提醒】星社成员出勤平台"
        body = f"""<p>亲爱的 <strong>{username}</strong>：</p>
            <p>您好！今日出勤将于 <strong>{check_out_time}</strong> 结束。</p>
            <p>请您及时完成签退操作，以免影响您的出勤记录。</p>
            <p>祝您学习进步，生活愉快！</p>"""
        html_content = self._render('StarClub | 星社出勤', body)
        return self.send_email(email, subject, html_content)

    def send_report_notification(self, email, reported_username, reason="未填写"):
        subject = "【举报提醒】星社成员出勤平台"
        body = f"""<p>亲爱的 <strong>{reported_username}</strong>：</p>
            <p>您好！您当前的在线状态受到举报，举报原因：<strong>{reason}</strong>。</p>
            <p>您的账号已被强制签退，本次出勤记录无效。</p>
            <p>您可以在系统进行申诉或接受本次举报处理结果。</p>"""
        html_content = self._render('StarClub | 星社出勤', body)
        return self.send_email(email, subject, html_content)

    def send_admin_notification(self, email, event_type, details):
        subject = f"【待处理】{event_type} - 星社成员出勤平台"
        body = f"""<p>管理员，您好！</p>
            <p>有一条新的<strong>{event_type}</strong>需要处理：</p>
            <div class="info-box">{details}</div>
            <p>请及时登录系统处理。</p>"""
        html_content = self._render('StarClub | 星社出勤', body)
        return self.send_email(email, subject, html_content)

    def send_test_email(self):
        from datetime import datetime as dt
        if not self.config.admin_email:
            return False, "管理员邮箱未设置"
        subject = "【测试邮件】星社成员出勤平台"
        send_time = dt.now().strftime('%Y-%m-%d %H:%M:%S')
        body = f"""<p>这是一封来自 <strong>StarClub | 星社成员出勤平台</strong> 的测试邮件。</p>
            <p>如果您收到这封邮件，说明邮件发送功能配置正常！</p>
            <p><strong>发送时间：</strong>{send_time}</p>"""
        html_content = self._render('StarClub | 星社出勤', body)
        # 测试邮件跳过时间窗口限制
        return self.send_email(self.config.admin_email, subject, html_content, skip_time_check=True)