# ============================================================
# auth.py - AUTHENTICATION & AUTHORIZATION (Layer 5)
# ============================================================

import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from config import SECRET_KEY

# ==================== PASSWORD FUNCTIONS ====================

def hash_password(password):
    """Mã hóa password bằng bcrypt"""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def verify_password(password, password_hash):
    """Kiểm tra password có đúng không"""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

# ==================== JWT TOKEN FUNCTIONS ====================

def create_token(user_id, email, role):
    """Tạo JWT token"""
    payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=24),
        'iat': datetime.utcnow()
    }
    return jwt.encode(payload, SECRET_KEY, algorithm='HS256')

def decode_token(token):
    """Giải mã JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "Token đã hết hạn"
    except jwt.InvalidTokenError:
        return None, "Token không hợp lệ"

# ==================== DECORATORS ====================

def require_auth(f):
    """Decorator yêu cầu đăng nhập"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Lấy token từ header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({
                "success": False,
                "error": "Vui lòng đăng nhập"
            }), 401
        
        # Giải mã token
        payload, error = decode_token(token)
        
        if error:
            return jsonify({
                "success": False,
                "error": error
            }), 401
        
        # Lưu thông tin user vào request
        request.user = payload
        
        return f(*args, **kwargs)
    
    return decorated

def require_role(roles):
    """Decorator yêu cầu role cụ thể"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if not hasattr(request, 'user'):
                return jsonify({
                    "success": False,
                    "error": "Vui lòng đăng nhập"
                }), 401
            
            user_role = request.user.get('role', 'user')
            
            if user_role not in roles:
                return jsonify({
                    "success": False,
                    "error": "Bạn không có quyền thực hiện thao tác này"
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated
    return decorator

# ==================== USER AUTH FUNCTIONS ====================

def login_user(email, password):
    """Xác thực user đăng nhập"""
    from models import get_user_by_email
    
    user = get_user_by_email(email)
    
    if not user:
        return None, "Email không tồn tại"
    
    if not verify_password(password, user['password_hash']):
        return None, "Mật khẩu không đúng"
    
    # Tạo token
    token = create_token(user['id'], user['email'], user['role'])
    
    return {
        'token': token,
        'user': {
            'id': user['id'],
            'email': user['email'],
            'name': user['name'],
            'role': user['role']
        }
    }, None

def register_user(email, password, name, role='user'):
    """Đăng ký user mới"""
    from models import get_user_by_email, create_user
    
    # Kiểm tra email đã tồn tại chưa
    existing_user = get_user_by_email(email)
    if existing_user:
        return None, "Email đã được sử dụng"
    
    # Mã hóa password
    password_hash = hash_password(password)
    
    # Tạo user
    user_id, error = create_user(email, password_hash, name, role)
    
    if error:
        return None, error
    
    return {'user_id': user_id}, None


if __name__ == '__main__':
    # Test password hashing
    password = "test123"
    hashed = hash_password(password)
    print(f"Password: {password}")
    print(f"Hashed: {hashed}")
    print(f"Verify: {verify_password(password, hashed)}")
    
    # Test token
    token = create_token(1, "test@test.com", "admin")
    print(f"Token: {token}")
    
    payload, error = decode_token(token)
    print(f"Decoded: {payload}")
