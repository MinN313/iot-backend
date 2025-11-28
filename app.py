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