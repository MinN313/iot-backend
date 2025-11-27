# ============================================================
# auth.py - AUTHENTICATION & AUTHORIZATION
# ============================================================

import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from config import SECRET_KEY
from models import get_db

def hash_password(password):
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def check_password(password, password_hash):
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

def create_token(user_id, email, role):
    payload = {
        "user_id": user_id,
        "email": email,
        "role": role,
        "exp": datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

def verify_token(token):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload
    except:
        return None

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({"success": False, "error": "Vui lòng đăng nhập"}), 401
        
        payload = verify_token(token)
        if not payload:
            return jsonify({"success": False, "error": "Token không hợp lệ"}), 401
        
        request.user = payload
        return f(*args, **kwargs)
    return decorated

def require_role(allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if request.user.get('role') not in allowed_roles:
                return jsonify({"success": False, "error": "Không có quyền"}), 403
            return f(*args, **kwargs)
        return decorated
    return decorator

def register_user(email, password, name=None, role='user'):
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return None, "Email đã được sử dụng"
    
    password_hash = hash_password(password)
    cursor.execute('''
        INSERT INTO users (email, password_hash, name, role)
        VALUES (?, ?, ?, ?)
    ''', (email, password_hash, name, role))
    
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    
    return {"user_id": user_id, "email": email, "role": role}, None

def login_user(email, password):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        return None, "Email không tồn tại"
    
    user = dict(user)
    if not check_password(password, user['password_hash']):
        return None, "Sai mật khẩu"
    
    token = create_token(user['id'], user['email'], user['role'])
    return {
        "token": token,
        "user": {"id": user['id'], "email": user['email'], "name": user['name'], "role": user['role']}
    }, None