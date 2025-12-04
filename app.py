from flask import Flask, request, jsonify
from flask_cors import CORS
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'iot-secret')
CORS(app)

from auth import hash_password, verify_password, create_token, require_auth, require_role
from models import *
from mqtt_handler import init_mqtt, publish_control, get_mqtt_status

init_db()
init_mqtt()

# ===== HEALTH =====
@app.route('/')
def home():
    return jsonify({"success": True, "message": "🏠 IoT Backend", "mqtt": get_mqtt_status()})

# ===== AUTH =====
@app.route('/api/auth/register', methods=['POST'])
def api_register():
    d = request.json
    email, pw, name = d.get('email','').strip(), d.get('password',''), d.get('name','').strip()
    if not email or not pw: return jsonify({"success": False, "error": "Thiếu thông tin"}), 400
    if len(pw) < 6: return jsonify({"success": False, "error": "Mật khẩu ≥ 6 ký tự"}), 400
    uid, err = create_user(email, hash_password(pw), name)
    if err: return jsonify({"success": False, "error": err}), 400
    return jsonify({"success": True, "message": "Đăng ký thành công!"}), 201

@app.route('/api/auth/login', methods=['POST'])
def api_login():
    d = request.json
    email, pw = d.get('email','').strip(), d.get('password','')
    user = get_user_by_email(email)
    if not user: return jsonify({"success": False, "error": "Email không tồn tại"}), 401
    if not verify_password(pw, user['password_hash']): return jsonify({"success": False, "error": "Sai mật khẩu"}), 401
    token = create_token(user['id'], user['email'], user['role'])
    return jsonify({"success": True, "token": token, "user": {
        "id": user['id'], "email": user['email'], "name": user['name'], 
        "role": user['role'], "avatar": user.get('avatar',''), 
        "theme": user.get('theme','dark'), "language": user.get('language','vi')
    }}), 200

@app.route('/api/auth/forgot-password', methods=['POST'])
def api_forgot_password():
    d = request.json
    email = d.get('email','').strip()
    if not email: return jsonify({"success": False, "error": "Nhập email"}), 400
    code, err = create_reset_code(email)
    if err: return jsonify({"success": False, "error": err}), 400
    
    try:
        import resend
        resend.api_key = os.environ.get("RESEND_API_KEY")
        if resend.api_key:
            resend.Emails.send({
                "from": os.environ.get("EMAIL_FROM", "onboarding@resend.dev"),
                "to": email,
                "subject": "🔑 Mã reset - IoT",
                "html": f"<h2>Mã xác nhận: <b>{code}</b></h2><p>Hết hạn sau 15 phút</p>"
            })
            return jsonify({"success": True, "message": "Đã gửi mã qua email!"}), 200
    except: pass
    return jsonify({"success": True, "message": "Mã xác nhận!", "code": code}), 200

@app.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    d = request.json
    email, code, new_pw = d.get('email',''), d.get('code',''), d.get('new_password','')
    if not all([email, code, new_pw]): return jsonify({"success": False, "error": "Thiếu thông tin"}), 400
    if len(new_pw) < 6: return jsonify({"success": False, "error": "Mật khẩu ≥ 6 ký tự"}), 400
    if not verify_reset_code(email, code): return jsonify({"success": False, "error": "Mã sai/hết hạn"}), 400
    reset_password(email, new_pw)
    return jsonify({"success": True, "message": "Đổi mật khẩu thành công!"}), 200

# ===== USER PROFILE =====
@app.route('/api/user/profile', methods=['GET'])
@require_auth
def api_get_profile():
    user = get_user_by_id(request.user['user_id'])
    return jsonify({"success": True, "data": user}), 200

@app.route('/api/user/profile', methods=['PUT'])
@require_auth
def api_update_profile():
    d = request.json
    update_user_profile(request.user['user_id'], d.get('name'), d.get('avatar'), d.get('theme'), d.get('language'))
    user = get_user_by_id(request.user['user_id'])
    return jsonify({"success": True, "data": user}), 200

@app.route('/api/user/password', methods=['PUT'])
@require_auth
def api_change_password():
    d = request.json
    old_pw, new_pw = d.get('old_password',''), d.get('new_password','')
    if len(new_pw) < 6: return jsonify({"success": False, "error": "Mật khẩu ≥ 6 ký tự"}), 400
    user = get_user_by_email(request.user['email'])
    if not verify_password(old_pw, user['password_hash']): return jsonify({"success": False, "error": "Mật khẩu cũ sai"}), 400
    update_user_password(request.user['user_id'], new_pw)
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
    if not s: return jsonify({"success": False, "error": "Không tồn tại"}), 404
    return jsonify({"success": True, "data": s}), 200

@app.route('/api/slots', methods=['POST'])
@require_auth
@require_role(['admin'])
def api_create_slot():
    d = request.json
    num, name, stype = d.get('slot_number'), d.get('name','').strip(), d.get('type','value')
    if not num or not name: return jsonify({"success": False, "error": "Thiếu thông tin"}), 400
    sid, err = create_slot(num, name, stype, d.get('icon','📟'), d.get('unit',''), d.get('location',''), d.get('stream_url',''))
    if err: return jsonify({"success": False, "error": err}), 400
    return jsonify({"success": True, "message": f"Tạo Slot {num} thành công"}), 201

@app.route('/api/slots/<int:num>', methods=['PUT'])
@require_auth
@require_role(['admin'])
def api_update_slot(num):
    d = request.json
    ok, err = update_slot(num, d.get('name'), d.get('type'), d.get('icon'), d.get('unit'), d.get('location'), d.get('stream_url'))
    if err: return jsonify({"success": False, "error": err}), 400
    return jsonify({"success": True}), 200

@app.route('/api/slots/<int:num>', methods=['DELETE'])
@require_auth
@require_role(['admin'])
def api_delete_slot(num):
    delete_slot(num)
    return jsonify({"success": True}), 200

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
    if num is None or val is None: return jsonify({"success": False, "error": "Thiếu"}), 400
    if not get_slot_by_number(num): return jsonify({"success": False, "error": f"Slot {num} chưa cấu hình"}), 404
    save_slot_data(num, val)
    return jsonify({"success": True}), 201

# ===== CONTROL =====
@app.route('/api/control/<int:num>', methods=['POST'])
@require_auth
@require_role(['admin', 'operator'])
def api_control(num):
    d = request.json
    cmd = d.get('command')
    if cmd not in [0, 1]: return jsonify({"success": False, "error": "Command 0/1"}), 400
    slot = get_slot_by_number(num)
    if not slot or slot['type'] != 'control': return jsonify({"success": False, "error": "Slot không hợp lệ"}), 400
    publish_control(num, cmd)
    save_slot_data(num, cmd)
    return jsonify({"success": True, "message": f"{'BẬT' if cmd else 'TẮT'} Slot {num}"}), 200

# ===== CAMERA =====
@app.route('/api/camera/<int:num>', methods=['GET'])
@require_auth
def api_get_camera(num):
    slot = get_slot_by_number(num)
    if not slot or slot['type'] != 'camera': return jsonify({"success": False, "error": "Không hợp lệ"}), 400
    img = get_camera_image(num)
    return jsonify({"success": True, "data": {
        "image_data": img['image_data'] if img else None,
        "stream_url": slot.get('stream_url',''),
        "created_at": img['created_at'] if img else None
    }}), 200

@app.route('/api/camera/<int:num>', methods=['POST'])
def api_post_camera(num):
    d = request.json
    img = d.get('image')
    if not img: return jsonify({"success": False, "error": "Thiếu image"}), 400
    slot = get_slot_by_number(num)
    if not slot or slot['type'] != 'camera': return jsonify({"success": False, "error": "Không hợp lệ"}), 404
    save_camera_image(num, img)
    return jsonify({"success": True}), 201

# ===== DASHBOARD =====
@app.route('/api/dashboard/stats', methods=['GET'])
@require_auth
def api_stats():
    return jsonify({"success": True, "data": get_dashboard_stats()}), 200

@app.route('/api/dashboard/full', methods=['GET'])
@require_auth
def api_full_dashboard():
    return jsonify({"success": True, "stats": get_dashboard_stats(), "slots": get_all_slots(), 
                    "data": get_all_latest_data(), "mqtt": get_mqtt_status()}), 200

# ===== ADMIN =====
@app.route('/api/admin/users', methods=['GET'])
@require_auth
@require_role(['admin'])
def api_get_users():
    return jsonify({"success": True, "data": get_all_users()}), 200

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
    admin_reset_password(uid, new_pw)
    return jsonify({"success": True, "message": f"Reset thành: {new_pw}"}), 200

@app.route('/api/admin/users/<int:uid>', methods=['DELETE'])
@require_auth
@require_role(['admin'])
def api_delete_user(uid):
    user = get_user_by_id(uid)
    if user and user['email'] == 'admin@admin.com':
        return jsonify({"success": False, "error": "Không thể xóa admin gốc"}), 400
    delete_user(uid)
    return jsonify({"success": True}), 200

@app.route('/api/mqtt/status', methods=['GET'])
@require_auth
def api_mqtt_status():
    return jsonify({"success": True, "data": get_mqtt_status()}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
