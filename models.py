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

if __name__ == "__main__":
    init_db()