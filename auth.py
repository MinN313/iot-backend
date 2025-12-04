import jwt
import bcrypt
from functools import wraps
from flask import request, jsonify
from config import SECRET_KEY

def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password, password_hash):
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def create_token(user_id, email, role):
    import datetime
    payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=7)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def decode_token(token):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'success': False, 'error': 'Token không hợp lệ'}), 401
        
        payload = decode_token(token)
        if not payload:
            return jsonify({'success': False, 'error': 'Token hết hạn'}), 401
        
        request.user = payload
        return f(*args, **kwargs)
    return decorated

def require_role(roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if request.user.get('role') not in roles:
                return jsonify({'success': False, 'error': 'Không có quyền'}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator
