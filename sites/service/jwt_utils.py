# -*- coding: utf-8 -*-
import jwt
import datetime
from config import Config

def generate_token(user_id, username, user_type, email='', expiration_hours=None):
    if expiration_hours is None:
        expiration_hours = Config.JWT_EXPIRATION_HOURS
    payload = {
        'user_id': user_id,
        'username': username,
        'user_type': user_type,
        'email': email,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=expiration_hours),
        'iat': datetime.datetime.utcnow()
    }
    token = jwt.encode(payload, Config.JWT_SECRET_KEY, algorithm=Config.JWT_ALGORITHM)
    # PyJWT 1.x returns bytes, 2.x returns str; normalize to str
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token

def get_expiration_hours(settings):
    return settings.get('jwt_expiration_hours', Config.JWT_EXPIRATION_HOURS)

def verify_token(token):
    try:
        payload = jwt.decode(token, Config.JWT_SECRET_KEY, algorithms=[Config.JWT_ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def get_user_info_from_token(token):
    payload = verify_token(token)
    if payload:
        return {
            'user_id': payload.get('user_id'),
            'username': payload.get('username'),
            'user_type': payload.get('user_type')
        }
    return None
