# ============================================================
# app.py - MAIN APPLICATION
# ============================================================
# File này là điểm khởi đầu của Backend
# Chứa tất cả API endpoints
# ============================================================

from flask import Flask, request, jsonify
from flask_cors import CORS
from config import API_HOST, API_PORT, SECRET_KEY
from auth import hash_password, verify_password, create_token, require_auth, require_role
from models import (
    init_db, 
    # User functions
    get_user_by_email, create_user, get_all_users, get_user_by_id,
    update_user_role, delete_user, admin_reset_password,
    # Slot functions
    get_all_slots, get_slot_by_number, create_slot, update_slot, delete_slot,
    get_available_slot_numbers,
    # Data functions
    save_slot_data, get_latest_slot_data, get_all_latest_data, get_slot_history,
    # Camera functions
    save_camera_image, get_camera_image,
    # Alert functions
    get_alerts, mark_alert_read, get_unread_alert_count,
    # Other
    get_dashboard_stats, create_reset_code, verify_reset_code, reset_password
)
from mqtt_handler import init_mqtt, publish_control, get_mqtt_status

# ==================== KHỞI TẠO APP ====================

app = Flask(__name__)
app.config['SECRET_KEY'] = SECRET_KEY

# CORS: Cho phép Frontend từ domain khác gọi API
# Quan trọng vì Frontend (Netlify) và Backend (Render) khác domain
CORS(app)

# Khởi tạo Database
init_db()

# Khởi tạo MQTT (kết nối HiveMQ Cloud)
init_mqtt()


# ==================== HEALTH CHECK ====================

@app.route('/')
def home():
    """
    API kiểm tra server có hoạt động không
    
    Truy cập: GET /
    """
    mqtt_status = get_mqtt_status()
    return jsonify({
        "success": True,
        "message": "🏠 IoT Backend Server đang chạy!",
        "mqtt": mqtt_status,
        "version": "2.0",
        "endpoints": {
            "auth": ["/api/auth/login", "/api/auth/register"],
            "slots": ["/api/slots", "/api/slots/<id>"],
            "data": ["/api/data", "/api/data/<slot>"],
            "camera": ["/api/camera/<slot>"],
            "control": ["/api/control/<slot>"],
            "alerts": ["/api/alerts"],
            "admin": ["/api/admin/users", "/api/admin/slots"]
        }
    })

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "mqtt": get_mqtt_status()
    })


# ==================== AUTH APIs ====================

@app.route('/api/auth/register', methods=['POST'])
def api_register():
    """
    API Đăng ký tài khoản
    
    Body:
    {
        "email": "user@email.com",
        "password": "123456",
        "name": "Tên người dùng"
    }
    """
    data = request.json
    
    email = data.get('email', '').strip()
    password = data.get('password', '')
    name = data.get('name', '').strip()
    role = data.get('role', 'user')  # Mặc định là user
    
    # Validate
    if not email or not password:
        return jsonify({"success": False, "error": "Thiếu email hoặc password"}), 400
    
    if len(password) < 6:
        return jsonify({"success": False, "error": "Password phải ít nhất 6 ký tự"}), 400
    
    # Tạo user
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
    """
    API Đăng nhập
    
    Body:
    {
        "email": "user@email.com",
        "password": "123456"
    }
    
    Response:
    {
        "success": true,
        "token": "eyJ...",
        "user": {...}
    }
    """
    data = request.json
    
    email = data.get('email', '').strip()
    password = data.get('password', '')
    
    if not email or not password:
        return jsonify({"success": False, "error": "Thiếu email hoặc password"}), 400
    
    # Tìm user
    user = get_user_by_email(email)
    
    if not user:
        return jsonify({"success": False, "error": "Email không tồn tại"}), 401
    
    # Kiểm tra password
    if not verify_password(password, user['password_hash']):
        return jsonify({"success": False, "error": "Mật khẩu không đúng"}), 401
    
    # Tạo token
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
    """Tạo mã reset password"""
    data = request.json
    email = data.get('email', '').strip()
    
    if not email:
        return jsonify({"success": False, "error": "Vui lòng nhập email"}), 400
    
    code, error = create_reset_code(email)
    
    if error:
        return jsonify({"success": False, "error": error}), 400
    
    # Trong thực tế: gửi mã qua email
    # Hiện tại: trả về mã để test
    return jsonify({
        "success": True,
        "message": "Mã reset đã được tạo!",
        "code": code  # Chỉ để test, production nên xóa dòng này
    }), 200

@app.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    """Đổi mật khẩu mới"""
    data = request.json
    email = data.get('email', '').strip()
    code = data.get('code', '').strip()
    new_password = data.get('new_password', '')
    
    if not all([email, code, new_password]):
        return jsonify({"success": False, "error": "Thiếu thông tin"}), 400
    
    if len(new_password) < 6:
        return jsonify({"success": False, "error": "Mật khẩu phải ít nhất 6 ký tự"}), 400
    
    if not verify_reset_code(email, code):
        return jsonify({"success": False, "error": "Mã không đúng hoặc đã hết hạn"}), 400
    
    reset_password(email, new_password)
    
    return jsonify({
        "success": True,
        "message": "Đổi mật khẩu thành công!"
    }), 200


# ==================== SLOT APIs ====================

@app.route('/api/slots', methods=['GET'])
@require_auth
def api_get_slots():
    """
    Lấy danh sách tất cả slots đã cấu hình
    
    Response:
    {
        "success": true,
        "data": [
            {"slot_number": 1, "name": "Nhiệt độ", "type": "value", ...},
            ...
        ]
    }
    """
    slots = get_all_slots()
    return jsonify({"success": True, "data": slots}), 200

@app.route('/api/slots/available', methods=['GET'])
@require_auth
@require_role(['admin'])
def api_get_available_slots():
    """Lấy danh sách số slot còn trống"""
    available = get_available_slot_numbers()
    return jsonify({"success": True, "data": available}), 200

@app.route('/api/slots/<int:slot_number>', methods=['GET'])
@require_auth
def api_get_slot(slot_number):
    """Lấy thông tin 1 slot"""
    slot = get_slot_by_number(slot_number)
    if not slot:
        return jsonify({"success": False, "error": "Slot không tồn tại"}), 404
    return jsonify({"success": True, "data": slot}), 200

@app.route('/api/slots', methods=['POST'])
@require_auth
@require_role(['admin'])
def api_create_slot():
    """
    Tạo slot mới (chỉ Admin)
    
    Body:
    {
        "slot_number": 1,
        "name": "Nhiệt độ phòng khách",
        "type": "value",
        "icon": "🌡️",
        "unit": "°C",
        "location": "Phòng khách",
        "threshold_min": 10,
        "threshold_max": 35,
        "stream_url": ""
    }
    
    type có thể là: "value", "status", "control", "camera"
    """
    data = request.json
    
    slot_number = data.get('slot_number')
    name = data.get('name', '').strip()
    slot_type = data.get('type', 'value')
    
    if not slot_number or not name:
        return jsonify({"success": False, "error": "Thiếu slot_number hoặc name"}), 400
    
    if slot_type not in ['value', 'status', 'control', 'camera']:
        return jsonify({"success": False, "error": "Type không hợp lệ"}), 400
    
    slot_id, error = create_slot(
        slot_number=slot_number,
        name=name,
        slot_type=slot_type,
        icon=data.get('icon', '📟'),
        unit=data.get('unit', ''),
        location=data.get('location', ''),
        threshold_min=data.get('threshold_min'),
        threshold_max=data.get('threshold_max'),
        stream_url=data.get('stream_url', '')
    )
    
    if error:
        return jsonify({"success": False, "error": error}), 400
    
    return jsonify({
        "success": True,
        "message": f"Đã tạo Slot {slot_number}",
        "slot_id": slot_id
    }), 201

@app.route('/api/slots/<int:slot_number>', methods=['PUT'])
@require_auth
@require_role(['admin'])
def api_update_slot(slot_number):
    """Cập nhật thông tin slot"""
    data = request.json
    
    success, error = update_slot(
        slot_number=slot_number,
        name=data.get('name'),
        slot_type=data.get('type'),
        icon=data.get('icon'),
        unit=data.get('unit'),
        location=data.get('location'),
        threshold_min=data.get('threshold_min'),
        threshold_max=data.get('threshold_max'),
        stream_url=data.get('stream_url')
    )
    
    if error:
        return jsonify({"success": False, "error": error}), 400
    
    return jsonify({"success": True, "message": "Đã cập nhật slot"}), 200

@app.route('/api/slots/<int:slot_number>', methods=['DELETE'])
@require_auth
@require_role(['admin'])
def api_delete_slot(slot_number):
    """Xóa slot"""
    delete_slot(slot_number)
    return jsonify({"success": True, "message": "Đã xóa slot"}), 200


# ==================== DATA APIs ====================

@app.route('/api/data', methods=['GET'])
@require_auth
def api_get_all_data():
    """
    Lấy dữ liệu mới nhất của tất cả slots
    
    Response:
    {
        "success": true,
        "data": {
            "1": {"value": "28.5", "created_at": "..."},
            "2": {"value": "65", "created_at": "..."}
        }
    }
    """
    data = get_all_latest_data()
    return jsonify({"success": True, "data": data}), 200

@app.route('/api/data/<int:slot_number>', methods=['GET'])
@require_auth
def api_get_slot_data(slot_number):
    """Lấy dữ liệu mới nhất của 1 slot"""
    data = get_latest_slot_data(slot_number)
    return jsonify({"success": True, "data": data}), 200

@app.route('/api/data/<int:slot_number>/history', methods=['GET'])
@require_auth
def api_get_slot_history(slot_number):
    """Lấy lịch sử dữ liệu của 1 slot"""
    limit = request.args.get('limit', 100, type=int)
    history = get_slot_history(slot_number, limit)
    return jsonify({"success": True, "data": history}), 200

@app.route('/api/data', methods=['POST'])
def api_post_data():
    """
    API nhận dữ liệu từ ESP32 (qua HTTP)
    
    Dùng khi ESP32 gửi qua HTTP thay vì MQTT
    
    Body:
    {
        "slot": 1,
        "value": 28.5
    }
    """
    data = request.json
    
    slot_number = data.get('slot')
    value = data.get('value')
    
    if slot_number is None or value is None:
        return jsonify({"success": False, "error": "Thiếu slot hoặc value"}), 400
    
    slot = get_slot_by_number(slot_number)
    if not slot:
        return jsonify({"success": False, "error": f"Slot {slot_number} chưa cấu hình"}), 404
    
    save_slot_data(slot_number, value)
    
    return jsonify({
        "success": True,
        "message": "Đã lưu dữ liệu"
    }), 201


# ==================== CONTROL APIs ====================

@app.route('/api/control/<int:slot_number>', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def api_control_device(slot_number):
    """
    Gửi lệnh điều khiển đến ESP32
    
    Body:
    {
        "command": 1
    }
    
    command: 0 = tắt, 1 = bật
    """
    data = request.json
    command = data.get('command')
    
    if command not in [0, 1]:
        return jsonify({"success": False, "error": "Command phải là 0 hoặc 1"}), 400
    
    # Kiểm tra slot có phải loại control không
    slot = get_slot_by_number(slot_number)
    if not slot:
        return jsonify({"success": False, "error": "Slot không tồn tại"}), 404
    
    if slot['type'] != 'control':
        return jsonify({"success": False, "error": "Slot này không phải loại điều khiển"}), 400
    
    # Gửi lệnh qua MQTT
    success = publish_control(slot_number, command)
    
    if success:
        # Lưu trạng thái mới vào database
        save_slot_data(slot_number, command)
        
        return jsonify({
            "success": True,
            "message": f"Đã gửi lệnh {'BẬT' if command == 1 else 'TẮT'} đến Slot {slot_number}"
        }), 200
    else:
        return jsonify({
            "success": False,
            "error": "Không thể gửi lệnh. Kiểm tra kết nối MQTT"
        }), 500


# ==================== CAMERA APIs ====================

@app.route('/api/camera/<int:slot_number>', methods=['GET'])
@require_auth
def api_get_camera_image(slot_number):
    """
    Lấy ảnh mới nhất của camera
    
    Response:
    {
        "success": true,
        "data": {
            "image_data": "data:image/jpeg;base64,...",
            "created_at": "2024-..."
        }
    }
    """
    slot = get_slot_by_number(slot_number)
    if not slot:
        return jsonify({"success": False, "error": "Slot không tồn tại"}), 404
    
    if slot['type'] != 'camera':
        return jsonify({"success": False, "error": "Slot này không phải camera"}), 400
    
    image = get_camera_image(slot_number)
    
    if image:
        return jsonify({
            "success": True,
            "data": {
                "image_data": image['image_data'],
                "created_at": image['created_at'],
                "stream_url": slot.get('stream_url', '')
            }
        }), 200
    else:
        return jsonify({
            "success": True,
            "data": {
                "image_data": None,
                "stream_url": slot.get('stream_url', ''),
                "message": "Chưa có ảnh từ camera"
            }
        }), 200

@app.route('/api/camera/<int:slot_number>', methods=['POST'])
def api_post_camera_image(slot_number):
    """
    API nhận ảnh từ ESP32-CAM (qua HTTP)
    
    Body:
    {
        "image": "data:image/jpeg;base64,..."
    }
    """
    data = request.json
    image_data = data.get('image')
    
    if not image_data:
        return jsonify({"success": False, "error": "Thiếu image data"}), 400
    
    slot = get_slot_by_number(slot_number)
    if not slot or slot['type'] != 'camera':
        return jsonify({"success": False, "error": "Slot camera không tồn tại"}), 404
    
    save_camera_image(slot_number, image_data)
    
    return jsonify({"success": True, "message": "Đã lưu ảnh"}), 201


# ==================== ALERT APIs ====================

@app.route('/api/alerts', methods=['GET'])
@require_auth
def api_get_alerts():
    """Lấy danh sách cảnh báo"""
    limit = request.args.get('limit', 50, type=int)
    alerts = get_alerts(limit)
    return jsonify({"success": True, "data": alerts}), 200

@app.route('/api/alerts/<int:alert_id>/read', methods=['PUT'])
@require_auth
def api_mark_alert_read(alert_id):
    """Đánh dấu cảnh báo đã đọc"""
    mark_alert_read(alert_id)
    return jsonify({"success": True, "message": "Đã đánh dấu đã đọc"}), 200

@app.route('/api/alerts/unread-count', methods=['GET'])
@require_auth
def api_get_unread_count():
    """Lấy số cảnh báo chưa đọc"""
    count = get_unread_alert_count()
    return jsonify({"success": True, "count": count}), 200


# ==================== DASHBOARD APIs ====================

@app.route('/api/dashboard/stats', methods=['GET'])
@require_auth
def api_get_stats():
    """Lấy thống kê cho dashboard"""
    stats = get_dashboard_stats()
    return jsonify({"success": True, "data": stats}), 200

@app.route('/api/dashboard/full', methods=['GET'])
@require_auth
def api_get_full_dashboard():
    """
    Lấy toàn bộ dữ liệu cho dashboard trong 1 API call
    
    Response:
    {
        "success": true,
        "stats": {...},
        "slots": [...],
        "data": {...},
        "alerts": [...]
    }
    """
    return jsonify({
        "success": True,
        "stats": get_dashboard_stats(),
        "slots": get_all_slots(),
        "data": get_all_latest_data(),
        "alerts": get_alerts(10),
        "mqtt": get_mqtt_status()
    }), 200


# ==================== ADMIN APIs ====================

@app.route('/api/admin/users', methods=['GET'])
@require_auth
@require_role(['admin'])
def api_admin_get_users():
    """Lấy danh sách users (Admin only)"""
    users = get_all_users()
    return jsonify({"success": True, "data": users}), 200

@app.route('/api/admin/users/<int:user_id>', methods=['GET'])
@require_auth
@require_role(['admin'])
def api_admin_get_user(user_id):
    """Lấy thông tin 1 user"""
    user = get_user_by_id(user_id)
    if not user:
        return jsonify({"success": False, "error": "User không tồn tại"}), 404
    return jsonify({"success": True, "data": user}), 200

@app.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
@require_auth
@require_role(['admin'])
def api_admin_update_role(user_id):
    """Đổi role của user"""
    data = request.json
    new_role = data.get('role')
    
    if new_role not in ['admin', 'operator', 'user']:
        return jsonify({"success": False, "error": "Role không hợp lệ"}), 400
    
    update_user_role(user_id, new_role)
    return jsonify({"success": True, "message": f"Đã đổi role thành {new_role}"}), 200

@app.route('/api/admin/users/<int:user_id>/reset-password', methods=['POST'])
@require_auth
@require_role(['admin'])
def api_admin_reset_user_password(user_id):
    """Admin reset mật khẩu cho user"""
    data = request.json
    new_password = data.get('new_password', '123456')
    
    if len(new_password) < 6:
        return jsonify({"success": False, "error": "Mật khẩu phải ít nhất 6 ký tự"}), 400
    
    admin_reset_password(user_id, new_password)
    return jsonify({
        "success": True,
        "message": f"Đã reset mật khẩu thành: {new_password}"
    }), 200

@app.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@require_auth
@require_role(['admin'])
def api_admin_delete_user(user_id):
    """Xóa user"""
    if request.user.get('user_id') == user_id:
        return jsonify({"success": False, "error": "Không thể xóa chính mình"}), 400
    
    delete_user(user_id)
    return jsonify({"success": True, "message": "Đã xóa user"}), 200


# ==================== MQTT STATUS API ====================

@app.route('/api/mqtt/status', methods=['GET'])
@require_auth
def api_mqtt_status():
    """Kiểm tra trạng thái MQTT"""
    return jsonify({
        "success": True,
        "data": get_mqtt_status()
    }), 200


# ==================== RUN SERVER ====================

if __name__ == '__main__':
    print("=" * 60)
    print("🚀 IOT BACKEND SERVER")
    print("=" * 60)
    print(f"📡 API: http://localhost:{API_PORT}")
    print("=" * 60)
    print("📝 Tài khoản Admin mặc định:")
    print("   Email: admin@admin.com")
    print("   Password: admin123")
    print("=" * 60)
    
    app.run(host=API_HOST, port=API_PORT, debug=True)
