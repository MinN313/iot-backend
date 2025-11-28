# ============================================================
# models.py - DATABASE MODELS
# ============================================================

import sqlite3
from config import DATABASE_PATH

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Bảng USERS
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
    
    # Bảng DEVICES
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL,
            location TEXT,
            ip_address TEXT,
            status TEXT DEFAULT 'offline',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bảng SENSOR_DATA
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sensor_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT NOT NULL,
            temperature REAL,
            humidity REAL,
            motion INTEGER DEFAULT 0,
            recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bảng ALERTS
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_id TEXT,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Bảng RESET_CODES (cho chức năng quên mật khẩu)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reset_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL,
            code TEXT NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Thêm dữ liệu mẫu
    sample_devices = [
        ('CAM_001', 'Camera Phòng Khách', 'camera', 'Phòng khách', '192.168.1.100'),
        ('CAM_002', 'Camera Sân Trước', 'camera', 'Sân trước', '192.168.1.101'),
        ('SENSOR_001', 'Cảm Biến Nhiệt Độ', 'sensor', 'Phòng ngủ', '192.168.1.102'),
        ('LED_001', 'Đèn Phòng Khách', 'led', 'Phòng khách', '192.168.1.103'),
    ]
    
    for device in sample_devices:
        try:
            cursor.execute('''
                INSERT INTO devices (device_id, name, type, location, ip_address, status)
                VALUES (?, ?, ?, ?, ?, 'online')
            ''', device)
        except sqlite3.IntegrityError:
            pass
    
    # Thêm sensor data mẫu
    for i in range(5):
        cursor.execute('''
            INSERT INTO sensor_data (device_id, temperature, humidity, motion)
            VALUES ('SENSOR_001', ?, ?, 0)
        ''', (28 + i * 0.5, 60 + i))
    
    conn.commit()
    conn.close()
    print("✅ Database đã khởi tạo!")

def get_all_devices():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM devices")
    devices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return devices

def get_devices_by_type(device_type):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM devices WHERE type = ?", (device_type,))
    devices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return devices

def get_latest_sensor_data():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sensor_data ORDER BY recorded_at DESC LIMIT 1")
    data = cursor.fetchone()
    conn.close()
    return dict(data) if data else None

def get_sensor_history(limit=50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM sensor_data ORDER BY recorded_at DESC LIMIT ?", (limit,))
    data = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return data

def add_sensor_data(device_id, temperature, humidity, motion=0):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sensor_data (device_id, temperature, humidity, motion)
        VALUES (?, ?, ?, ?)
    ''', (device_id, temperature, humidity, motion))
    conn.commit()
    conn.close()

def get_all_alerts(limit=50):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,))
    alerts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return alerts

def get_unread_alerts():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM alerts WHERE is_read = 0 ORDER BY created_at DESC")
    alerts = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return alerts

def add_alert(device_id, alert_type, message):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO alerts (device_id, alert_type, message)
        VALUES (?, ?, ?)
    ''', (device_id, alert_type, message))
    conn.commit()
    conn.close()

def mark_alert_read(alert_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()
# ========================
# RESET PASSWORD
# ========================

def create_reset_code(email):
    """Tạo mã reset password"""
    import random
    code = str(random.randint(100000, 999999))  # Mã 6 số
    
    conn = get_db()
    cursor = conn.cursor()
    
    # Kiểm tra email tồn tại
    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    user = cursor.fetchone()
    
    if not user:
        conn.close()
        return None, "Email không tồn tại"
    
    # Xóa mã cũ nếu có
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
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE email = ?",
        (password_hash, email)
    )
    
    # Xóa mã reset
    cursor.execute("DELETE FROM reset_codes WHERE email = ?", (email,))
    
    conn.commit()
    conn.close()
    
    return True

def delete_reset_code(email):
    """Xóa mã reset sau khi dùng"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM reset_codes WHERE email = ?", (email,))
    conn.commit()
    conn.close()

# ========================
# ADMIN - QUẢN LÝ USER
# ========================

def get_all_users():
    """Lấy danh sách tất cả users"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, email, name, role, created_at 
        FROM users 
        ORDER BY created_at DESC
    ''')
    users = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return users

def update_user_role(user_id, new_role):
    """Đổi role của user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET role = ? WHERE id = ?",
        (new_role, user_id)
    )
    conn.commit()
    conn.close()
    return True

def admin_reset_password(user_id, new_password):
    """Admin reset mật khẩu cho user"""
    from auth import hash_password
    
    conn = get_db()
    cursor = conn.cursor()
    
    password_hash = hash_password(new_password)
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE id = ?",
        (password_hash, user_id)
    )
    
    conn.commit()
    conn.close()
    return True

def delete_user(user_id):
    """Xóa user"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True

def get_user_by_id(user_id):
    """Lấy thông tin user theo ID"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, email, name, role, created_at FROM users WHERE id = ?",
        (user_id,)
    )
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None
if __name__ == "__main__":
    init_db()