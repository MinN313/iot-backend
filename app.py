# app.py - MAIN API
from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'secret-key-iot')
CORS(app)

from auth import hash_password, verify_password, create_token, require_auth, require_role
from models import (
    init_db, get_user_by_email, create_user, get_all_users, get_user_by_id,
    update_user_role, delete_user, admin_reset_password,
    get_all_slots, get_slot_by_number, create_slot, update_slot, delete_slot,
    get_available_slot_numbers, save_slot_data, get_latest_slot_data,
    get_all_latest_data, get_slot_history, save_camera_image, get_camera_image,
    get_alerts, mark_alert_read, get_unread_alert_count, get_dashboard_stats,
    create_reset_code, verify_reset_code, reset_password
)
from mqtt_handler import init_mqtt, publish_control, get_mqtt_status

init_db()
init_mqtt()

# ===== HEALTH =====
@app.route('/')
def home():
    return jsonify({"success": True, "message": "🏠 IoT Backend Running!", "mqtt": get_mqtt_status()})

@app.route('/api/health')
def health():
    return jsonify({"status": "healthy", "mqtt": get_mqtt_status()})

# ===== AUTH =====
@app.route('/api/auth/register', methods=['POST'])
def api_register():
    d = request.json
    email, pw, name = d.get('email','').strip(), d.get('password',''), d.get('name','').strip()
    if not email or not pw: return jsonify({"success": False, "error": "Thiếu thông tin"}), 400
    if len(pw) < 6: return jsonify({"success": False, "error": "Mật khẩu ít nhất 6 ký tự"}), 400
    uid, err = create_user(email, hash_password(pw), name)
    if err: return jsonify({"success": False, "error": err}), 400
    return jsonify({"success": True, "message": "Đăng ký thành công!"}), 201

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    d = request.json
    email, pw = d.get('email','').strip(), d.get('password','')
    if not email or not pw: return jsonify({"success": False, "error": "Thiếu thông tin"}), 400
    user = get_user_by_email(email)
    if not user: return jsonify({"success": False, "error": "Email không tồn tại"}), 401
    if not verify_password(pw, user['password_hash']): return jsonify({"success": False, "error": "Sai mật khẩu"}), 401
    token = create_token(user['id'], user['email'], user['role'])
    return jsonify({"success": True, "token": token, "user": {"id": user['id'], "email": user['email'], "name": user['name'], "role": user['role']}}), 200

@app.route('/api/auth/forgot-password', methods=['POST'])
def api_forgot_password():
    """Gửi mã reset qua email"""
    d = request.json
    email = d.get('email','').strip()
    if not email: return jsonify({"success": False, "error": "Vui lòng nhập email"}), 400
    
    code, err = create_reset_code(email)
    if err: return jsonify({"success": False, "error": err}), 400
    
    # Gửi email
    try:
        import resend
        resend.api_key = os.environ.get("RESEND_API_KEY")
        
        if resend.api_key:
            resend.Emails.send({
                "from": os.environ.get("EMAIL_FROM", "onboarding@resend.dev"),
                "to": email,
                "subject": "🔑 Mã reset mật khẩu - IoT Platform",
                "html": f"""
                    <div style="font-family: Arial; max-width: 500px; margin: 0 auto; padding: 20px;">
                        <h2 style="color: #4facfe;">🏠 IoT Platform</h2>
                        <p>Mã xác nhận của bạn là:</p>
                        <div style="background: #f0f0f0; padding: 20px; text-align: center; font-size: 32px; font-weight: bold; letter-spacing: 5px; border-radius: 10px;">{code}</div>
                        <p style="color: #888; margin-top: 20px;">Mã có hiệu lực 15 phút.</p>
                    </div>
                """
            })
            return jsonify({"success": True, "message": "Mã xác nhận đã gửi đến email!"}), 200
        else:
            # Không có API key, trả về mã (test mode)
            return jsonify({"success": True, "message": "Mã xác nhận đã tạo!", "code": code}), 200
    except Exception as e:
        print(f"Email error: {e}")
        return jsonify({"success": True, "message": "Mã xác nhận!", "code": code}), 200

@app.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    d = request.json
    email, code, new_pw = d.get('email','').strip(), d.get('code','').strip(), d.get('new_password','')
    if not all([email, code, new_pw]): return jsonify({"success": False, "error": "Thiếu thông tin"}), 400
    if len(new_pw) < 6: return jsonify({"success": False, "error": "Mật khẩu ít nhất 6 ký tự"}), 400
    if not verify_reset_code(email, code): return jsonify({"success": False, "error": "Mã không đúng hoặc hết hạn"}), 400
    reset_password(email, new_pw)
    return jsonify({"success": True, "message": "Đổi mật khẩu thành công!"}), 200

# ===== SLOTS =====
@app.route('/api/slots', methods=['GET'])
@require_auth
def api_get_slots():
    return jsonify({"success": True, "data": get_all_slots()}), 200

@app.route('/api/slots/available', methods=['GET'])
@require_auth
@require_role(['admin'])
def api_available_slots():
    return jsonify({"success": True, "data": get_available_slot_numbers()}), 200

@app.route('/api/slots/<int:num>', methods=['GET'])
@require_auth
def api_get_slot(num):
    s = get_slot_by_number(num)
    if not s: return jsonify({"success": False, "error": "Slot không tồn tại"}), 404
    return jsonify({"success": True, "data": s}), 200

@app.route('/api/slots', methods=['POST'])
@require_auth
@require_role(['admin'])
def api_create_slot():
    d = request.json
    num, name, stype = d.get('slot_number'), d.get('name','').strip(), d.get('type','value')
    if not num or not name: return jsonify({"success": False, "error": "Thiếu thông tin"}), 400
    sid, err = create_slot(num, name, stype, d.get('icon','📟'), d.get('unit',''), d.get('location',''), d.get('threshold_min'), d.get('threshold_max'), d.get('stream_url',''))
    if err: return jsonify({"success": False, "error": err}), 400
    return jsonify({"success": True, "message": f"Đã tạo Slot {num}"}), 201

@app.route('/api/slots/<int:num>', methods=['PUT'])
@require_auth
@require_role(['admin'])
def api_update_slot(num):
    d = request.json
    ok, err = update_slot(num, d.get('name'), d.get('type'), d.get('icon'), d.get('unit'), d.get('location'), d.get('threshold_min'), d.get('threshold_max'), d.get('stream_url'))
    if err: return jsonify({"success": False, "error": err}), 400
    return jsonify({"success": True, "message": "Đã cập nhật"}), 200

@app.route('/api/slots/<int:num>', methods=['DELETE'])
@require_auth
@require_role(['admin'])
def api_delete_slot(num):
    delete_slot(num)
    return jsonify({"success": True, "message": "Đã xóa"}), 200

# ===== DATA =====
@app.route('/api/data', methods=['GET'])
@require_auth
def api_get_data():
    return jsonify({"success": True, "data": get_all_latest_data()}), 200

@app.route('/api/data/<int:num>', methods=['GET'])
@require_auth
def api_get_slot_data(num):
    return jsonify({"success": True, "data": get_latest_slot_data(num)}), 200

@app.route('/api/data/<int:num>/history', methods=['GET'])
@require_auth
def api_slot_history(num):
    limit = request.args.get('limit', 100, type=int)
    return jsonify({"success": True, "data": get_slot_history(num, limit)}), 200

@app.route('/api/data', methods=['POST'])
def api_post_data():
    d = request.json
    num, val = d.get('slot'), d.get('value')
    if num is None or val is None: return jsonify({"success": False, "error": "Thiếu thông tin"}), 400
    if not get_slot_by_number(num): return jsonify({"success": False, "error": f"Slot {num} chưa cấu hình"}), 404
    save_slot_data(num, val)
    return jsonify({"success": True, "message": "Đã lưu"}), 201

# ===== CONTROL =====
@app.route('/api/control/<int:num>', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def api_control(num):
    d = request.json
    cmd = d.get('command')
    if cmd not in [0, 1]: return jsonify({"success": False, "error": "Command phải 0 hoặc 1"}), 400
    slot = get_slot_by_number(num)
    if not slot: return jsonify({"success": False, "error": "Slot không tồn tại"}), 404
    if slot['type'] != 'control': return jsonify({"success": False, "error": "Slot không phải điều khiển"}), 400
    if publish_control(num, cmd):
        save_slot_data(num, cmd)
        return jsonify({"success": True, "message": f"Đã {'BẬT' if cmd else 'TẮT'} Slot {num}"}), 200
    return jsonify({"success": False, "error": "Không thể gửi lệnh"}), 500

# ===== CAMERA =====
@app.route('/api/camera/<int:num>', methods=['GET'])
@require_auth
def api_get_camera(num):
    slot = get_slot_by_number(num)
    if not slot: return jsonify({"success": False, "error": "Slot không tồn tại"}), 404
    if slot['type'] != 'camera': return jsonify({"success": False, "error": "Không phải camera"}), 400
    img = get_camera_image(num)
    return jsonify({"success": True, "data": {"image_data": img['image_data'] if img else None, "stream_url": slot.get('stream_url',''), "created_at": img['created_at'] if img else None}}), 200

@app.route('/api/camera/<int:num>', methods=['POST'])
def api_post_camera(num):
    d = request.json
    img = d.get('image')
    if not img: return jsonify({"success": False, "error": "Thiếu image"}), 400
    slot = get_slot_by_number(num)
    if not slot or slot['type'] != 'camera': return jsonify({"success": False, "error": "Slot camera không tồn tại"}), 404
    save_camera_image(num, img)
    return jsonify({"success": True}), 201

# ===== ALERTS =====
@app.route('/api/alerts', methods=['GET'])
@require_auth
def api_get_alerts():
    limit = request.args.get('limit', 50, type=int)
    return jsonify({"success": True, "data": get_alerts(limit)}), 200

@app.route('/api/alerts/<int:aid>/read', methods=['PUT'])
@require_auth
def api_mark_read(aid):
    mark_alert_read(aid)
    return jsonify({"success": True}), 200

@app.route('/api/alerts/unread-count', methods=['GET'])
@require_auth
def api_unread_count():
    return jsonify({"success": True, "count": get_unread_alert_count()}), 200

# ===== DASHBOARD =====
@app.route('/api/dashboard/stats', methods=['GET'])
@require_auth
def api_stats():
    return jsonify({"success": True, "data": get_dashboard_stats()}), 200

@app.route('/api/dashboard/full', methods=['GET'])
@require_auth
def api_full_dashboard():
    return jsonify({"success": True, "stats": get_dashboard_stats(), "slots": get_all_slots(), "data": get_all_latest_data(), "alerts": get_alerts(10), "mqtt": get_mqtt_status()}), 200

# ===== ADMIN =====
@app.route('/api/admin/users', methods=['GET'])
@require_auth
@require_role(['admin'])
def api_get_users():
    return jsonify({"success": True, "data": get_all_users()}), 200

@app.route('/api/admin/users/<int:uid>', methods=['GET'])
@require_auth
@require_role(['admin'])
def api_get_user(uid):
    u = get_user_by_id(uid)
    if not u: return jsonify({"success": False, "error": "User không tồn tại"}), 404
    return jsonify({"success": True, "data": u}), 200

@app.route('/api/admin/users/<int:uid>/role', methods=['PUT'])
@require_auth
@require_role(['admin'])
def api_change_role(uid):
    role = request.json.get('role')
    if role not in ['admin','operator','user']: return jsonify({"success": False, "error": "Role không hợp lệ"}), 400
    update_user_role(uid, role)
    return jsonify({"success": True}), 200

@app.route('/api/admin/users/<int:uid>/reset-password', methods=['POST'])
@require_auth
@require_role(['admin'])
def api_admin_reset_pw(uid):
    new_pw = request.json.get('new_password', '123456')
    if len(new_pw) < 6: return jsonify({"success": False, "error": "Mật khẩu ít nhất 6 ký tự"}), 400
    admin_reset_password(uid, new_pw)
    return jsonify({"success": True, "message": f"Đã reset thành: {new_pw}"}), 200

@app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
@require_auth
@require_role(['admin'])
def api_delete_user(uid):
    if request.user.get('user_id') == uid: return jsonify({"success": False, "error": "Không thể xóa chính mình"}), 400
    delete_user(uid)
    return jsonify({"success": True}), 200

@app.route('/api/mqtt/status', methods=['GET'])
@require_auth
def api_mqtt_status():
    return jsonify({"success": True, "data": get_mqtt_status()}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
