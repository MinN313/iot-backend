# ============================================================
# config.py - CẤU HÌNH HỆ THỐNG
# ============================================================

import os

# Layer 5: Security
SECRET_KEY = os.environ.get("SECRET_KEY", "my-super-secret-key-iot-project-2024")

# Layer 6: Database
DATABASE_PATH = os.environ.get("DATABASE_PATH", "iot_database.db")

# Layer 4: MQTT (sẽ dùng MQTT broker công cộng khi deploy)
MQTT_BROKER = os.environ.get("MQTT_BROKER", "broker.hivemq.com")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))

# Layer 3: Transport
API_HOST = "0.0.0.0"
API_PORT = int(os.environ.get("PORT", 8080))

# Alert Thresholds
TEMP_MAX = 35.0
TEMP_MIN = 10.0
HUMIDITY_MAX = 80.0
HUMIDITY_MIN = 30.0
