# ============================================================
# models.py - DATABASE MODELS
# ============================================================
# File này quản lý tất cả tương tác với Database
# Sử dụng SQLite - database nhẹ, không cần cài đặt server
# ============================================================

import sqlite3
from datetime import datetime
from config import DATABASE_PATH, MAX_SLOTS

# ==================== KẾT NỐI DATABASE ====================

def get_db():
    """
    Tạo kết nối đến database SQLite
    row_factory = sqlite3.Row cho phép truy cập cột bằng tên
    """
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ==================== KHỞI TẠO DATABASE ====================

def init_db():
    """
    Tạo tất cả các bảng cần thiết
    Chạy mỗi khi server khởi động
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # ========== BẢNG USERS ==========
    # Lưu thông tin người dùng
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            name TEXT,
            role TEXT DEFAULT 'user',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ========== BẢNG SLOTS ==========
    # Cấu hình các slot thiết bị
    # Đây là bảng quan trọng nhất - định nghĩa thiết bị
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            icon TEXT DEFAULT '📟',
            unit TEXT DEFAULT '',
            location TEXT DEFAULT '',
            threshold_min REAL,
            threshold_max REAL,
            stream_url TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Giải thích các cột:
    # - slot_number: Số slot (1-20), ESP32 gửi đến số này
    # - name: Tên hiển thị (VD: "Nhiệt độ phòng khách")
    # - type: Loại slot (value/status/control/camera)
    # - icon: Emoji icon hiển thị
    # - unit: Đơn vị (°C, %, lux...)
    # - location: Vị trí đặt (Phòng khách, Sân vườn...)
    # - threshold_min/max: Ngưỡng cảnh báo
    # - stream_url: URL stream cho camera (local)
    # - is_active: Slot có đang hoạt động không
    
    # ========== BẢNG SLOT_DATA ==========
    # Lưu dữ liệu từ ESP32 gửi lên
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS slot_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number INTEGER NOT NULL,
            value TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ========== BẢNG CAMERA_IMAGES ==========
    # Lưu ảnh mới nhất từ camera
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS camera_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number INTEGER UNIQUE NOT NULL,
            image_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # image_data: Ảnh dạng Base64
    
    # ========== BẢNG ALERTS ==========
    # Lưu các cảnh báo
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slot_number INTEGER,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # ========== BẢNG RESET_CODES ==========
    # Mã reset mật khẩu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reset_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    
    # ========== TẠO ADMIN MẶC ĐỊNH ==========
    cursor.execute("SELECT id FROM users WHERE email = 'admin@admin.com'")
    if not cursor.fetchone():
        from auth import hash_password
        admin_password = hash_password('admin123')
        cursor.execute('''
            INSERT INTO users (email, password_hash, name, role)
            VALUES ('admin@admin.com', ?, 'Administrator', 'admin')
        ''', (admin_password,))
        conn.commit()
        print("✅ Đã tạo tài khoản admin mặc định!")
        print("   Email: admin@admin.com")
        print("   Password: admin123")
    
    conn.close()
    print("✅ Database đã khởi tạo!")


# ==================== USER FUNCTIONS ====================

def get_user_by_email(email):
    """Lấy user theo email"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_user_by_id(user_id):
    """Lấy user theo ID"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, email, name, role, created_at FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def create_user(email, password_hash, name, role='user'):
    """Tạo user mới"""
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO users (email, password_hash, name, role)
            VALUES (?, ?, ?, ?)
        ''', (email, password_hash, name, role))
        conn.commit()
        user_id = cursor.lastrowid
        conn.close()
        return user_id, None
    except sqlite3.IntegrityError:
        conn.close()
        return None, "Email đã tồn tại"

def get_all_users():
    """Lấy danh sách tất cả users"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT id, email, name, role, created_at FROM users ORDER BY created_at DESC')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

def update_user_role(user_id, new_role):
    """Đổi role của user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET role = ? WHERE id = ?", (new_role, user_id))
    conn.commit()
    conn.close()

def delete_user(user_id):
    """Xóa user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()

def admin_reset_password(user_id, new_password):
    """Admin reset mật khẩu cho user"""
    from auth import hash_password
    conn = get_db()
    cursor = conn.cursor()
    password_hash = hash_password(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))
    conn.commit()
    conn.close()


# ==================== SLOT FUNCTIONS ====================

def get_all_slots():
    """Lấy danh sách tất cả slots đã cấu hình"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM slots WHERE is_active = 1 ORDER BY slot_number')
    slots = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return slots

def get_slot_by_number(slot_number):
    """Lấy thông tin 1 slot"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM slots WHERE slot_number = ?", (slot_number,))
    slot = cursor.fetchone()
    conn.close()
    return dict(slot) if slot else None

def create_slot(slot_number, name, slot_type, icon='📟', unit='', location='', 
                threshold_min=None, threshold_max=None, stream_url=''):
    """
    Tạo slot mới
    slot_type: 'value', 'status', 'control', 'camera'
    """
    if slot_number < 1 or slot_number > MAX_SLOTS:
        return None, f"Slot number phải từ 1-{MAX_SLOTS}"
    
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO slots (slot_number, name, type, icon, unit, location, 
                             threshold_min, threshold_max, stream_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (slot_number, name, slot_type, icon, unit, location, 
              threshold_min, threshold_max, stream_url))
        conn.commit()
        slot_id = cursor.lastrowid
        conn.close()
        return slot_id, None
    except sqlite3.IntegrityError:
        conn.close()
        return None, f"Slot {slot_number} đã được sử dụng"

def update_slot(slot_number, name=None, slot_type=None, icon=None, unit=None, 
                location=None, threshold_min=None, threshold_max=None, stream_url=None):
    """Cập nhật thông tin slot"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Lấy thông tin hiện tại
    cursor.execute("SELECT * FROM slots WHERE slot_number = ?", (slot_number,))
    current = cursor.fetchone()
    if not current:
        conn.close()
        return False, "Slot không tồn tại"
    
    # Cập nhật các trường được chỉ định
    cursor.execute('''
        UPDATE slots SET 
            name = ?, type = ?, icon = ?, unit = ?, location = ?,
            threshold_min = ?, threshold_max = ?, stream_url = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE slot_number = ?
    ''', (
        name if name else current['name'],
        slot_type if slot_type else current['type'],
        icon if icon else current['icon'],
        unit if unit else current['unit'],
        location if location else current['location'],
        threshold_min if threshold_min is not None else current['threshold_min'],
        threshold_max if threshold_max is not None else current['threshold_max'],
        stream_url if stream_url else current['stream_url'],
        slot_number
    ))
    conn.commit()
    conn.close()
    return True, None

def delete_slot(slot_number):
    """Xóa slot (soft delete - đặt is_active = 0)"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE slots SET is_active = 0 WHERE slot_number = ?", (slot_number,))
    conn.commit()
    conn.close()

def get_available_slot_numbers():
    """Lấy danh sách số slot còn trống"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT slot_number FROM slots WHERE is_active = 1")
    used = set(row['slot_number'] for row in cursor.fetchall())
    conn.close()
    available = [i for i in range(1, MAX_SLOTS + 1) if i not in used]
    return available


# ==================== SLOT DATA FUNCTIONS ====================

def save_slot_data(slot_number, value):
    """Lưu dữ liệu từ ESP32 gửi lên"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO slot_data (slot_number, value)
        VALUES (?, ?)
    ''', (slot_number, str(value)))
    conn.commit()
    data_id = cursor.lastrowid
    conn.close()
    
    # Kiểm tra ngưỡng và tạo cảnh báo
    check_threshold(slot_number, value)
    
    return data_id

def get_latest_slot_data(slot_number):
    """Lấy dữ liệu mới nhất của 1 slot"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM slot_data 
        WHERE slot_number = ? 
        ORDER BY created_at DESC 
        LIMIT 1
    ''', (slot_number,))
    data = cursor.fetchone()
    conn.close()
    return dict(data) if data else None

def get_all_latest_data():
    """Lấy dữ liệu mới nhất của tất cả slots"""
    conn = get_db()
    cursor = conn.cursor()
    
    # Lấy dữ liệu mới nhất cho mỗi slot
    cursor.execute('''
        SELECT sd.* FROM slot_data sd
        INNER JOIN (
            SELECT slot_number, MAX(created_at) as max_time
            FROM slot_data
            GROUP BY slot_number
        ) latest ON sd.slot_number = latest.slot_number 
                AND sd.created_at = latest.max_time
    ''')
    data = {row['slot_number']: dict(row) for row in cursor.fetchall()}
    conn.close()
    return data

def get_slot_history(slot_number, limit=100):
    """Lấy lịch sử dữ liệu của 1 slot"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM slot_data 
        WHERE slot_number = ? 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (slot_number, limit))
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return history


# ==================== CAMERA FUNCTIONS ====================

def save_camera_image(slot_number, image_data):
    """
    Lưu ảnh camera (ghi đè ảnh cũ)
    image_data: Base64 string
    """
    conn = get_db()
    cursor = conn.cursor()
    
    # Xóa ảnh cũ
    cursor.execute("DELETE FROM camera_images WHERE slot_number = ?", (slot_number,))
    
    # Lưu ảnh mới
    cursor.execute('''
        INSERT INTO camera_images (slot_number, image_data)
        VALUES (?, ?)
    ''', (slot_number, image_data))
    conn.commit()
    conn.close()

def get_camera_image(slot_number):
    """Lấy ảnh mới nhất của camera"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM camera_images 
        WHERE slot_number = ?
    ''', (slot_number,))
    image = cursor.fetchone()
    conn.close()
    return dict(image) if image else None


# ==================== ALERT FUNCTIONS ====================

def check_threshold(slot_number, value):
    """Kiểm tra ngưỡng và tạo cảnh báo nếu vượt"""
    slot = get_slot_by_number(slot_number)
    if not slot or slot['type'] != 'value':
        return
    
    try:
        numeric_value = float(value)
    except:
        return
    
    if slot['threshold_max'] and numeric_value > slot['threshold_max']:
        create_alert(
            slot_number, 
            'threshold_high',
            f"⚠️ {slot['name']} vượt ngưỡng cao: {value}{slot['unit']} (>{slot['threshold_max']}{slot['unit']})"
        )
    
    if slot['threshold_min'] and numeric_value < slot['threshold_min']:
        create_alert(
            slot_number,
            'threshold_low', 
            f"⚠️ {slot['name']} dưới ngưỡng thấp: {value}{slot['unit']} (<{slot['threshold_min']}{slot['unit']})"
        )

def create_alert(slot_number, alert_type, message):
    """Tạo cảnh báo mới"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO alerts (slot_number, alert_type, message)
        VALUES (?, ?, ?)
    ''', (slot_number, alert_type, message))
    conn.commit()
    conn.close()

def get_alerts(limit=50):
    """Lấy danh sách cảnh báo"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM alerts 
        ORDER BY created_at DESC 
        LIMIT ?
    ''', (limit,))
    alerts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return alerts

def mark_alert_read(alert_id):
    """Đánh dấu cảnh báo đã đọc"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()

def get_unread_alert_count():
    """Đếm số cảnh báo chưa đọc"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM alerts WHERE is_read = 0")
    count = cursor.fetchone()[0]
    conn.close()
    return count


# ==================== RESET PASSWORD FUNCTIONS ====================

def create_reset_code(email):
    """Tạo mã reset password"""
    import random
    
    # Kiểm tra email tồn tại
    user = get_user_by_email(email)
    if not user:
        return None, "Email không tồn tại"
    
    code = str(random.randint(100000, 999999))
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Xóa mã cũ
    cursor.execute("DELETE FROM reset_codes WHERE email = ?", (email,))
    
    # Tạo mã mới (hết hạn sau 15 phút)
    cursor.execute('''
        INSERT INTO reset_codes (email, code, expires_at)
        VALUES (?, ?, datetime('now', '+15 minutes'))
    ''', (email, code))
    conn.commit()
    conn.close()
    
    return code, None

def verify_reset_code(email, code):
    """Kiểm tra mã reset có đúng không"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM reset_codes 
        WHERE email = ? AND code = ? AND expires_at > datetime('now')
    ''', (email, code))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def reset_password(email, new_password):
    """Đổi mật khẩu"""
    from auth import hash_password
    
    conn = get_db()
    cursor = conn.cursor()
    password_hash = hash_password(new_password)
    cursor.execute("UPDATE users SET password_hash = ? WHERE email = ?", (password_hash, email))
    cursor.execute("DELETE FROM reset_codes WHERE email = ?", (email,))
    conn.commit()
    conn.close()


# ==================== DASHBOARD STATS ====================

def get_dashboard_stats():
    """Lấy thống kê cho dashboard"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM slots WHERE is_active = 1")
    total_slots = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM slots WHERE is_active = 1 AND type = 'camera'")
    total_cameras = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM slots WHERE is_active = 1 AND type = 'control'")
    total_controls = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM alerts WHERE is_read = 0")
    unread_alerts = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_slots': total_slots,
        'total_cameras': total_cameras,
        'total_controls': total_controls,
        'unread_alerts': unread_alerts
    }


# ==================== CHẠY THỬ ====================
if __name__ == '__main__':
    init_db()
    print("\n📊 Thống kê:")
    print(get_dashboard_stats())
