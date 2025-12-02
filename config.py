# ============================================================
# config.py - CẤU HÌNH HỆ THỐNG
# ============================================================
# File này chứa tất cả cấu hình của hệ thống
# Sử dụng biến môi trường để bảo mật khi deploy
# ============================================================

import os

# ==================== BẢO MẬT ====================
# SECRET_KEY: Dùng để mã hóa JWT token
# Trong production nên đặt qua biến môi trường
SECRET_KEY = os.environ.get("SECRET_KEY", "my-super-secret-key-iot-project-2024")

# ==================== DATABASE ====================
# Đường dẫn file SQLite
# Render sẽ lưu trong thư mục tạm, reset khi restart
DATABASE_PATH = os.environ.get("DATABASE_PATH", "iot_database.db")

# ==================== MQTT - HIVEMQ CLOUD ====================
# Thông tin kết nối MQTT Broker
# Đây là thông tin HiveMQ Cloud của bạn
MQTT_BROKER = os.environ.get("MQTT_BROKER", "cba26f7b818b4fe3b5315dce8e53941c.s1.eu.hivemq.cloud")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 8883))  # 8883 = TLS/SSL
MQTT_USERNAME = os.environ.get("MQTT_USERNAME", "iot-user")
MQTT_PASSWORD = os.environ.get("MQTT_PASSWORD", "Iot@12345")

# ==================== MQTT TOPICS ====================
# Các "địa chỉ" để gửi/nhận tin nhắn MQTT
MQTT_TOPICS = {
    'data': 'iot/data',           # ESP32 gửi dữ liệu sensor lên
    'control': 'iot/control',     # Backend gửi lệnh điều khiển xuống
    'camera': 'iot/camera',       # ESP32-CAM gửi ảnh lên
    'status': 'iot/status',       # ESP32 gửi trạng thái (online/offline)
}

# ==================== API SERVER ====================
# Cấu hình web server
API_HOST = "0.0.0.0"  # Lắng nghe tất cả IP
API_PORT = int(os.environ.get("PORT", 8080))  # Render tự đặt PORT

# ==================== GIỚI HẠN HỆ THỐNG ====================
# Số slot tối đa cho phép
MAX_SLOTS = 20

# Kích thước ảnh camera tối đa (bytes) - 500KB
MAX_IMAGE_SIZE = 500 * 1024

# ==================== IN THÔNG TIN ====================
if __name__ == '__main__':
    print("=" * 50)
    print("CẤU HÌNH HỆ THỐNG IOT")
    print("=" * 50)
    print(f"MQTT Broker: {MQTT_BROKER}")
    print(f"MQTT Port: {MQTT_PORT}")
    print(f"MQTT Username: {MQTT_USERNAME}")
    print(f"API Port: {API_PORT}")
    print(f"Max Slots: {MAX_SLOTS}")
    print("=" * 50)
