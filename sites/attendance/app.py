"""
StarClub | 星社出勤平台
入口文件 - Flask应用工厂
"""
import os
from flask import Flask, session, request, g
from datetime import timedelta

from config import Config
from db import init_db, sys_config_load
from email_service import EmailService
from services.scheduler import start_background_tasks


def create_app():
    app = Flask(__name__)
    app.secret_key = Config.SECRET_KEY

    # 初始化数据库
    init_db()

    # 加载系统配置
    system_config = sys_config_load()
    email_service = EmailService(system_config)

    # 存储到 app.config 供路由和后台任务访问
    app.config['system_config'] = system_config
    app.config['email_service'] = email_service

    # Session 配置
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(seconds=system_config.session_expire_seconds)
    app.config['SESSION_COOKIE_SECURE'] = False
    app.config['SESSION_COOKIE_HTTPONLY'] = True

    # 登记蓝图
    from routes.auth import auth_bp
    from routes.attendance import attendance_bp
    from routes.management import management_bp
    app.register_blueprint(auth_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(management_bp)

    # JWT 认证：从 Authorization header 提取 JWT payload
    @app.before_request
    def _extract_jwt():
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if token:
            import requests as _req
            try:
                r = _req.post(app.config['portal_url'] + '/api/jwt/verify',
                              json={'token': token}, timeout=5)
                result = r.json()
                if result.get('success'):
                    from flask import g
                    g.jwt_payload = result['payload']
            except Exception:
                pass

    # 根路由
    @app.route('/')
    def index():
        if 'user_id' not in session:
            return app.redirect('/login')
        return app.redirect('/attendance')

    return app


# 创建应用实例
app = create_app()

if __name__ == '__main__':
    start_background_tasks(app)
    debug = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'
    app.run(host=Config.HOST, port=Config.PORT, debug=debug)