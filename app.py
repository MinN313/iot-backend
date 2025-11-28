# ============================================================
# app.py - MAIN APPLICATION
# ============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime

from config import API_HOST, API_PORT, TEMP_MAX, TEMP_MIN, HUMIDITY_MAX, HUMIDITY_MIN
from models import (
    init_db, get_db, get_all_devices, get_devices_by_type,
    get_latest_sensor_data, get_sensor_history, add_sensor_data,
    get_all_alerts, get_unread_alerts, add_alert, mark_alert_read
)
from auth import require_auth, require_role, register_user, login_user

app = Flask(__name__)
CORS(app)

# ==================== AUTH APIs ====================

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    data = request.json
    if not data.get('email') or not data.get('password'):
        return jsonify({"success": False, "error": "Thiếu email hoặc password"}), 400
    
    result, error = register_user(
        email=data['email'],
        password=data['password'],
        name=data.get('name', ''),
        role=data.get('role', 'user')
    )
    
    if error:
        return jsonify({"success": False, "error": error}), 400
    return jsonify({"success": True, "message": "Đăng ký thành công!", "data": result}), 201

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    data = request.json
    if not data.get('email') or not data.get('password'):
        return jsonify({"success": False, "error": "Thiếu email hoặc password"}), 400
    
    result, error = login_user(email=data['email'], password=data['password'])
    
    if error:
        return jsonify({"success": False, "error": error}), 401
    return jsonify({"success": True, "message": "Đăng nhập thành công!", "data": result}), 200

@app.route('/api/auth/me', methods=['GET'])
@require_auth
def api_get_me():
    return jsonify({"success": True, "data": request.user}), 200

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
    
    # Trong thực tế, gửi code qua email
    # Ở đây trả về code để test (production nên bỏ)
    return jsonify({
        "success": True,
        "message": "Mã reset đã được tạo! Kiểm tra email của bạn.",
        "code": code  # CHỈ ĐỂ TEST - Production phải gửi qua email
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
    
    # Kiểm tra mã
    if not verify_reset_code(email, code):
        return jsonify({"success": False, "error": "Mã không đúng hoặc đã hết hạn"}), 400
    
    # Đổi mật khẩu
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
    new_password = data.get('new_password', '123456')  # Mặc định 123456
    
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
    
    # Không cho xóa chính mình
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
    devices = get_all_devices()
    return jsonify({"success": True, "data": devices}), 200

@app.route('/api/cameras', methods=['GET'])
@require_auth
def api_get_cameras():
    cameras = get_devices_by_type('camera')
    return jsonify({"success": True, "data": cameras}), 200

@app.route('/api/devices/<device_id>/control', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def api_control_device(device_id):
    data = request.json
    action = data.get('action')
    
    if action not in ['on', 'off']:
        return jsonify({"success": False, "error": "Action phải là 'on' hoặc 'off'"}), 400
    
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE devices SET status = ? WHERE device_id = ?", (action, device_id))
    conn.commit()
    conn.close()
    
    return jsonify({"success": True, "message": f"Đã gửi lệnh '{action}' đến {device_id}"}), 200

# ==================== SENSOR APIs ====================

@app.route('/api/sensors', methods=['GET'])
@require_auth
def api_get_sensors():
    data = get_latest_sensor_data()
    if not data:
        data = {"temperature": 0, "humidity": 0, "motion": 0}
    return jsonify({"success": True, "data": data}), 200

@app.route('/api/sensors/history', methods=['GET'])
@require_auth
def api_get_sensor_history():
    limit = request.args.get('limit', 50, type=int)
    data = get_sensor_history(limit)
    return jsonify({"success": True, "data": data}), 200

@app.route('/api/sensors/data', methods=['POST'])
def api_post_sensor_data():
    data = request.json
    device_id = data.get('device_id', 'SENSOR_001')
    temperature = data.get('temperature')
    humidity = data.get('humidity')
    motion = data.get('motion', 0)
    
    add_sensor_data(device_id, temperature, humidity, motion)
    
    if temperature and temperature > TEMP_MAX:
        add_alert(device_id, 'temp_high', f'Nhiệt độ cao: {temperature}°C')
    if humidity and humidity > HUMIDITY_MAX:
        add_alert(device_id, 'humidity_high', f'Độ ẩm cao: {humidity}%')
    if motion == 1:
        add_alert(device_id, 'motion', 'Phát hiện chuyển động!')
    
    return jsonify({"success": True, "message": "Đã nhận dữ liệu"}), 200

# ==================== ALERT APIs ====================

@app.route('/api/alerts', methods=['GET'])
@require_auth
def api_get_alerts():
    alerts = get_all_alerts()
    return jsonify({"success": True, "data": alerts}), 200

@app.route('/api/alerts/unread', methods=['GET'])
@require_auth
def api_get_unread_alerts():
    alerts = get_unread_alerts()
    return jsonify({"success": True, "data": alerts, "count": len(alerts)}), 200

@app.route('/api/alerts/<int:alert_id>/read', methods=['PUT'])
@require_auth
def api_mark_alert_read(alert_id):
    mark_alert_read(alert_id)
    return jsonify({"success": True, "message": "Đã đánh dấu đọc"}), 200

# ==================== DASHBOARD APIs ====================

@app.route('/api/dashboard/stats', methods=['GET'])
@require_auth
def api_get_dashboard_stats():
    devices = get_all_devices()
    sensor_data = get_latest_sensor_data()
    unread_alerts = get_unread_alerts()
    
    online_count = sum(1 for d in devices if d['status'] == 'online')
    cameras = [d for d in devices if d['type'] == 'camera']
    
    return jsonify({
        "success": True,
        "data": {
            "total_devices": len(devices),
            "online_devices": online_count,
            "total_cameras": len(cameras),
            "unread_alerts": len(unread_alerts),
            "latest_sensor": sensor_data
        }
    }), 200

# ==================== HEALTH CHECK ====================

@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"success": True, "message": "Server is running!", "time": datetime.now().isoformat()}), 200

@app.route('/', methods=['GET'])
def home():
    return jsonify({
        "success": True,
        "message": "🏠 IoT Backend Server is running!",
        "endpoints": ["/api/auth/login", "/api/devices", "/api/sensors", "/api/alerts"]
    }), 200

# ==================== RUN SERVER ====================
init_db()
if __name__ == '__main__':
    print("=" * 50)
    print("🚀 IOT BACKEND SERVER")
    print("=" * 50)
    print(f"📡 http://localhost:{API_PORT}")
    print("=" * 50)
    app.run(host=API_HOST, port=API_PORT, debug=True)