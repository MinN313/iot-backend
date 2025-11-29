# ============================================================
# app.py - MAIN APPLICATION (Layer 6 + 7)
# ============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
from config import API_HOST, API_PORT, SECRET_KEY
from auth import hash_password, verify_password, create_token, require_auth, require_role
from models import (
    init_db, get_user_by_email, create_user,
    get_all_devices, get_device_by_id, update_device_status, get_devices_by_type,
    get_latest_sensor_data, add_sensor_data,
    get_all_alerts, create_alert, mark_alert_read, get_unread_alerts_count,
    get_dashboard_stats
)

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY
CORS(app)

# Khởi tạo database khi import (QUAN TRỌNG cho Render)
init_db()

# ==================== HEALTH CHECK ====================

@app.route('/')
def home():
    return jsonify({
        "success": True,
        "message": "🏠 IoT Backend Server is running!",
        "endpoints": [
            "/api/auth/login",
            "/api/auth/register",
            "/api/devices",
            "/api/sensors",
            "/api/alerts",
            "/api/dashboard/stats"
        ]
    })

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "message": "Server is running!"})

# ==================== AUTH APIs ====================

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """API Đăng ký tài khoản"""
    data = request.json
    
    email = data.get('email')
    password = data.get('password')
    name = data.get('name', '')
    role = data.get('role', 'user')
    
    if not email or not password:
        return jsonify({"success": False, "error": "Thiếu email hoặc password"}), 400
    
    if len(password) < 6:
        return jsonify({"success": False, "error": "Password phải ít nhất 6 ký tự"}), 400
    
    password_hash = hash_password(password)
    user_id, error = create_user(email, password_hash, name, role)
    
    if error:
        return jsonify({"success": False, "error": error}), 400
    
    return jsonify({
        "success": True,
        "message": "Đăng ký thành công!",
        "user_id": user_id
    }), 201

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    """API Đăng nhập"""
    data = request.json
    
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({"success": False, "error": "Thiếu email hoặc password"}), 400
    
    user = get_user_by_email(email)
    
    if not user or not verify_password(password, user['password_hash']):
        return jsonify({"success": False, "error": "Email hoặc mật khẩu không đúng"}), 401
    
    token = create_token(user['id'], user['email'], user['role'])
    
    return jsonify({
        "success": True,
        "message": "Đăng nhập thành công!",
        "token": token,
        "user": {
            "id": user['id'],
            "email": user['email'],
            "name": user['name'],
            "role": user['role']
        }
    }), 200

# ==================== FORGOT PASSWORD APIs ====================

@app.route('/api/auth/forgot-password', methods=['POST'])
def api_forgot_password():
    """API Quên mật khẩu - Tạo mã reset"""
    from models import create_reset_code
    
    data = request.json
    email = data.get('email')
    
    if not email:
        return jsonify({"success": False, "error": "Vui lòng nhập email"}), 400
    
    code, error = create_reset_code(email)
    
    if error:
        return jsonify({"success": False, "error": error}), 400
    
    return jsonify({
        "success": True,
        "message": "Mã reset đã được tạo! Kiểm tra email của bạn.",
        "code": code
    }), 200

@app.route('/api/auth/verify-reset-code', methods=['POST'])
def api_verify_reset_code():
    """API Kiểm tra mã reset"""
    from models import verify_reset_code
    
    data = request.json
    email = data.get('email')
    code = data.get('code')
    
    if not email or not code:
        return jsonify({"success": False, "error": "Thiếu thông tin"}), 400
    
    if verify_reset_code(email, code):
        return jsonify({"success": True, "message": "Mã hợp lệ"}), 200
    else:
        return jsonify({"success": False, "error": "Mã không đúng hoặc đã hết hạn"}), 400

@app.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    """API Đổi mật khẩu mới"""
    from models import verify_reset_code, reset_password, delete_reset_code
    
    data = request.json
    email = data.get('email')
    code = data.get('code')
    new_password = data.get('new_password')
    
    if not all([email, code, new_password]):
        return jsonify({"success": False, "error": "Thiếu thông tin"}), 400
    
    if len(new_password) < 6:
        return jsonify({"success": False, "error": "Mật khẩu phải ít nhất 6 ký tự"}), 400
    
    if not verify_reset_code(email, code):
        return jsonify({"success": False, "error": "Mã không đúng hoặc đã hết hạn"}), 400
    
    reset_password(email, new_password)
    delete_reset_code(email)
    
    return jsonify({
        "success": True,
        "message": "Đổi mật khẩu thành công! Vui lòng đăng nhập lại."
    }), 200

# ==================== ADMIN APIs ====================

@app.route('/api/admin/users', methods=['GET'])
@require_auth
@require_role(['admin'])
def api_admin_get_users():
    """API Lấy danh sách tất cả users (chỉ admin)"""
    from models import get_all_users
    
    users = get_all_users()
    return jsonify({"success": True, "data": users}), 200

@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
@require_auth
@require_role(['admin'])
def api_admin_get_user(user_id):
    """API Lấy thông tin 1 user"""
    from models import get_user_by_id
    
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"success": False, "error": "User không tồn tại"}), 404
    
    return jsonify({"success": True, "data": user}), 200

@app.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
@require_auth
@require_role(['admin'])
def api_admin_update_role(user_id):
    """API Đổi role của user"""
    from models import update_user_role
    
    data = request.json
    new_role = data.get('role')
    
    if new_role not in ['admin', 'operator', 'user']:
        return jsonify({"success": False, "error": "Role không hợp lệ"}), 400
    
    update_user_role(user_id, new_role)
    
    return jsonify({
        "success": True,
        "message": f"Đã đổi role thành {new_role}"
    }), 200

@app.route('/api/admin/users/<int:user_id>/reset-password', methods=['POST'])
@require_auth
@require_role(['admin'])
def api_admin_reset_password(user_id):
    """API Admin reset mật khẩu cho user"""
    from models import admin_reset_password
    
    data = request.json
    new_password = data.get('new_password', '123456')
    
    admin_reset_password(user_id, new_password)
    
    return jsonify({
        "success": True,
        "message": f"Đã reset mật khẩu thành: {new_password}"
    }), 200

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@require_auth
@require_role(['admin'])
def api_admin_delete_user(user_id):
    """API Xóa user"""
    from models import delete_user
    
    if request.user.get('user_id') == user_id:
        return jsonify({"success": False, "error": "Không thể xóa chính mình"}), 400
    
    delete_user(user_id)
    
    return jsonify({
        "success": True,
        "message": "Đã xóa user"
    }), 200

# ==================== DEVICE APIs ====================

@app.route('/api/devices', methods=['GET'])
@require_auth
def api_get_devices():
    """API Lấy danh sách thiết bị"""
    devices = get_all_devices()
    return jsonify({"success": True, "data": devices}), 200

@app.route('/api/devices/<device_id>', methods=['GET'])
@require_auth
def api_get_device(device_id):
    """API Lấy thông tin thiết bị"""
    device = get_device_by_id(device_id)
    if not device:
        return jsonify({"success": False, "error": "Không tìm thấy thiết bị"}), 404
    return jsonify({"success": True, "data": device}), 200

@app.route('/api/devices/<device_id>/control', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def api_control_device(device_id):
    """API Điều khiển thiết bị"""
    data = request.json
    action = data.get('action')
    
    if action not in ['on', 'off']:
        return jsonify({"success": False, "error": "Action phải là 'on' hoặc 'off'"}), 400
    
    device = get_device_by_id(device_id)
    if not device:
        return jsonify({"success": False, "error": "Không tìm thấy thiết bị"}), 404
    
    new_status = 'online' if action == 'on' else 'offline'
    update_device_status(device_id, new_status)
    
    return jsonify({
        "success": True,
        "message": f"Đã {action.upper()} thiết bị {device['name']}",
        "device_id": device_id,
        "status": new_status
    }), 200

# ==================== CAMERA APIs ====================

@app.route('/api/cameras', methods=['GET'])
@require_auth
def api_get_cameras():
    """API Lấy danh sách camera"""
    cameras = get_devices_by_type('camera')
    return jsonify({"success": True, "data": cameras}), 200

# ==================== SENSOR APIs ====================

@app.route('/api/sensors', methods=['GET'])
@require_auth
def api_get_sensors():
    """API Lấy dữ liệu sensor mới nhất"""
    data = get_latest_sensor_data()
    if not data:
        data = {"temperature": 0, "humidity": 0, "motion": 0}
    return jsonify({"success": True, "data": data}), 200

@app.route('/api/sensors', methods=['POST'])
def api_add_sensor_data():
    """API Thêm dữ liệu sensor (từ ESP32)"""
    data = request.json
    
    device_id = data.get('device_id')
    temperature = data.get('temperature')
    humidity = data.get('humidity')
    motion = data.get('motion', 0)
    
    if not all([device_id, temperature is not None, humidity is not None]):
        return jsonify({"success": False, "error": "Thiếu dữ liệu"}), 400
    
    data_id = add_sensor_data(device_id, temperature, humidity, motion)
    
    return jsonify({
        "success": True,
        "message": "Đã lưu dữ liệu sensor",
        "data_id": data_id
    }), 201

# ==================== ALERT APIs ====================

@app.route('/api/alerts', methods=['GET'])
@require_auth
def api_get_alerts():
    """API Lấy danh sách cảnh báo"""
    alerts = get_all_alerts()
    return jsonify({"success": True, "data": alerts}), 200

@app.route('/api/alerts/<int:alert_id>/read', methods=['PUT'])
@require_auth
def api_mark_alert_read(alert_id):
    """API Đánh dấu cảnh báo đã đọc"""
    mark_alert_read(alert_id)
    return jsonify({"success": True, "message": "Đã đánh dấu đã đọc"}), 200

# ==================== DASHBOARD APIs ====================

@app.route('/api/dashboard/stats', methods=['GET'])
@require_auth
def api_get_dashboard_stats():
    """API Lấy thống kê dashboard"""
    stats = get_dashboard_stats()
    return jsonify({"success": True, "data": stats}), 200

# ==================== RUN SERVER ====================

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 IOT BACKEND SERVER")
    print("=" * 50)
    print(f"📡 http://localhost:{API_PORT}")
    print("=" * 50)
    app.run(host=API_HOST, port=API_PORT, debug=True)
