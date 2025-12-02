# ============================================================
# auth.py - AUTHENTICATION & AUTHORIZATION
# ============================================================
# File này xử lý:
# - Mã hóa mật khẩu (bcrypt)
# - Tạo/giải mã JWT token
# - Kiểm tra quyền truy cập
# ============================================================

import jwt
import bcrypt
from datetime import datetime, timedelta
from functools import wraps
from flask import request, jsonify
from config import SECRET_KEY

# ==================== MÃ HÓA MẬT KHẨU ====================

def hash_password(password):
    """
    Mã hóa mật khẩu bằng bcrypt
    
    Bcrypt là thuật toán mã hóa 1 chiều:
    - Không thể giải mã ngược lại
    - Mỗi lần mã hóa ra kết quả khác nhau (do salt)
    - Tự động thêm salt để chống rainbow table attack
    
    VD: "admin123" → "$2b$12$xyz..."
    """
    salt = bcrypt.gensalt()  # Tạo salt ngẫu nhiên
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')

def verify_password(password, password_hash):
    """
    Kiểm tra mật khẩu có đúng không
    
    So sánh mật khẩu người dùng nhập với hash trong database
    """
    return bcrypt.checkpw(
        password.encode('utf-8'), 
        password_hash.encode('utf-8')
    )


# ==================== JWT TOKEN ====================

def create_token(user_id, email, role):
    """
    Tạo JWT token cho user sau khi đăng nhập thành công
    
    JWT (JSON Web Token) gồm 3 phần:
    1. Header: Loại token, thuật toán
    2. Payload: Dữ liệu (user_id, email, role, thời gian hết hạn)
    3. Signature: Chữ ký để xác thực
    
    Token có thời hạn 24 giờ
    """
    payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=24),  # Hết hạn sau 24h
        'iat': datetime.utcnow()  # Thời gian tạo
    }
    
    token = jwt.encode(payload, SECRET_KEY, algorithm='HS256')
    return token

def decode_token(token):
    """
    Giải mã JWT token
    
    Trả về:
    - (payload, None): Nếu token hợp lệ
    - (None, error): Nếu token không hợp lệ hoặc hết hạn
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=['HS256'])
        return payload, None
    except jwt.ExpiredSignatureError:
        return None, "Token đã hết hạn"
    except jwt.InvalidTokenError:
        return None, "Token không hợp lệ"


# ==================== DECORATORS ====================
# Decorator là cách "bọc" thêm chức năng cho hàm
# Dùng để kiểm tra quyền trước khi chạy hàm chính

def require_auth(f):
    """
    Decorator yêu cầu đăng nhập
    
    Kiểm tra:
    1. Có header Authorization không?
    2. Token có hợp lệ không?
    3. Token có hết hạn không?
    
    Sử dụng:
    @require_auth
    def my_api():
        # Code chỉ chạy khi đã đăng nhập
        pass
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        
        # Lấy token từ header "Authorization: Bearer <token>"
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
        
        # Lưu thông tin user vào request để dùng sau
        request.user = payload
        
        return f(*args, **kwargs)
    
    return decorated

def require_role(roles):
    """
    Decorator yêu cầu role cụ thể
    
    Kiểm tra user có đúng role không
    
    Sử dụng:
    @require_role(['admin'])           # Chỉ admin
    @require_role(['admin', 'operator']) # Admin hoặc operator
    
    VD:
    @require_auth
    @require_role(['admin'])
    def delete_user():
        # Chỉ admin mới xóa được user
        pass
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # Kiểm tra đã đăng nhập chưa
            if not hasattr(request, 'user'):
                return jsonify({
                    "success": False,
                    "error": "Vui lòng đăng nhập"
                }), 401
            
            # Kiểm tra role
            user_role = request.user.get('role', 'user')
            
            if user_role not in roles:
                return jsonify({
                    "success": False,
                    "error": "Bạn không có quyền thực hiện thao tác này"
                }), 403
            
            return f(*args, **kwargs)
        
        return decorated
    return decorator


# ==================== TEST ====================
if __name__ == '__main__':
    # Test mã hóa password
    print("=" * 50)
    print("TEST AUTH MODULE")
    print("=" * 50)
    
    password = "admin123"
    hashed = hash_password(password)
    print(f"\n1. Hash password:")
    print(f"   Password: {password}")
    print(f"   Hashed: {hashed[:50]}...")
    print(f"   Verify: {verify_password(password, hashed)}")
    print(f"   Wrong: {verify_password('wrong', hashed)}")
    
    # Test JWT token
    print(f"\n2. JWT Token:")
    token = create_token(1, "admin@admin.com", "admin")
    print(f"   Token: {token[:50]}...")
    
    payload, error = decode_token(token)
    print(f"   Decoded: {payload}")
