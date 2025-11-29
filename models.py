# ============================================================
# models.py - DATABASE MODELS (Layer 6)
# ============================================================

import sqlite3
from config import DATABASE_PATH

def get_db():
    """Kết nối database"""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Khởi tạo database và các bảng"""
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
            status TEXT DEFAULT 'offline',
            ip_address TEXT,
            mac_address TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    
    conn.commit()
    
    # Tạo admin mặc định nếu chưa có
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
    
    # Thêm dữ liệu mẫu nếu chưa có
    cursor.execute("SELECT COUNT(*) FROM devices")
    if cursor.fetchone()[0] == 0:
        sample_devices = [
            ('CAM_001', 'Camera Phòng Khách', 'camera', 'Phòng khách', 'online', '192.168.1.100'),
            ('CAM_002', 'Camera Sân Trước', 'camera', 'Sân trước', 'online', '192.168.1.101'),
            ('SENSOR_001', 'Cảm biến Phòng Khách', 'sensor', 'Phòng khách', 'online', '192.168.1.102'),
            ('LED_001', 'Đèn LED Phòng Khách', 'led', 'Phòng khách', 'online', '192.168.1.103'),
        ]
        cursor.executemany('''
            INSERT INTO devices (device_id, name, type, location, status, ip_address)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', sample_devices)
        
        # Thêm dữ liệu sensor mẫu
        cursor.execute('''
            INSERT INTO sensor_data (device_id, temperature, humidity, motion)
            VALUES ('SENSOR_001', 28.0, 60, 0)
        ''')
        
        conn.commit()
        print("✅ Đã thêm dữ liệu mẫu!")
    
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

# ==================== DEVICE FUNCTIONS ====================

def get_all_devices():
    """Lấy tất cả devices"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM devices ORDER BY created_at DESC")
    devices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return devices

def get_device_by_id(device_id):
    """Lấy device theo ID"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM devices WHERE device_id = ?", (device_id,))
    device = cursor.fetchone()
    conn.close()
    return dict(device) if device else None

def update_device_status(device_id, status):
    """Cập nhật trạng thái device"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE devices SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE device_id = ?
    ''', (status, device_id))
    conn.commit()
    conn.close()

def get_devices_by_type(device_type):
    """Lấy devices theo loại"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM devices WHERE type = ?", (device_type,))
    devices = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return devices

# ==================== SENSOR FUNCTIONS ====================

def get_latest_sensor_data():
    """Lấy dữ liệu sensor mới nhất"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM sensor_data 
        ORDER BY created_at DESC LIMIT 1
    ''')
    data = cursor.fetchone()
    conn.close()
    return dict(data) if data else None

def add_sensor_data(device_id, temperature, humidity, motion=0):
    """Thêm dữ liệu sensor"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO sensor_data (device_id, temperature, humidity, motion)
        VALUES (?, ?, ?, ?)
    ''', (device_id, temperature, humidity, motion))
    conn.commit()
    data_id = cursor.lastrowid
    conn.close()
    return data_id

# ==================== ALERT FUNCTIONS ====================

def get_all_alerts(limit=50):
    """Lấy tất cả alerts"""
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

def create_alert(device_id, alert_type, message):
    """Tạo alert mới"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO alerts (device_id, alert_type, message)
        VALUES (?, ?, ?)
    ''', (device_id, alert_type, message))
    conn.commit()
    alert_id = cursor.lastrowid
    conn.close()
    return alert_id

def mark_alert_read(alert_id):
    """Đánh dấu alert đã đọc"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE alerts SET is_read = 1 WHERE id = ?", (alert_id,))
    conn.commit()
    conn.close()

def get_unread_alerts_count():
    """Đếm số alerts chưa đọc"""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM alerts WHERE is_read = 0")
    count = cursor.fetchone()[0]
    conn.close()
    return count

# ==================== DASHBOARD STATS ====================

def get_dashboard_stats():
    """Lấy thống kê cho dashboard"""
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM devices")
    total_devices = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM devices WHERE status = 'online'")
    online_devices = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM devices WHERE type = 'camera'")
    total_cameras = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM alerts WHERE is_read = 0")
    unread_alerts = cursor.fetchone()[0]
    
    conn.close()
    
    return {
        'total_devices': total_devices,
        'online_devices': online_devices,
        'total_cameras': total_cameras,
        'unread_alerts': unread_alerts
    }

# ========================
# RESET PASSWORD
# ========================

def create_reset_code(email):
    """Tạo mã reset password"""
    import random
    code = str(random.randint(100000, 999999))
    
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


if __name__ == '__main__':
    init_db()
