# ============================================================
# mqtt_handler.py - MQTT HANDLER
# ============================================================
# File này xử lý:
# - Kết nối đến HiveMQ Cloud
# - Nhận dữ liệu từ ESP32 (subscribe)
# - Gửi lệnh điều khiển đến ESP32 (publish)
# ============================================================

import paho.mqtt.client as mqtt
import ssl
import json
import threading
from config import (
    MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD, MQTT_TOPICS
)

# Biến global để lưu MQTT client
mqtt_client = None
is_connected = False

# ==================== CALLBACKS ====================
# Callback là hàm được gọi tự động khi có sự kiện

def on_connect(client, userdata, flags, rc):
    """
    Callback khi kết nối đến MQTT broker
    
    rc (return code):
    - 0: Kết nối thành công
    - 1: Protocol version không đúng
    - 2: Client ID không hợp lệ
    - 3: Server không khả dụng
    - 4: Username/password sai
    - 5: Không được phép kết nối
    """
    global is_connected
    
    if rc == 0:
        is_connected = True
        print("=" * 50)
        print("✅ ĐÃ KẾT NỐI HIVEMQ CLOUD!")
        print("=" * 50)
        
        # Subscribe các topic để nhận dữ liệu
        # Topic 'iot/data': Nhận dữ liệu sensor từ ESP32
        client.subscribe(MQTT_TOPICS['data'])
        print(f"📡 Subscribed: {MQTT_TOPICS['data']}")
        
        # Topic 'iot/camera': Nhận ảnh từ ESP32-CAM
        client.subscribe(MQTT_TOPICS['camera'])
        print(f"📡 Subscribed: {MQTT_TOPICS['camera']}")
        
        # Topic 'iot/status': Nhận trạng thái online/offline
        client.subscribe(MQTT_TOPICS['status'])
        print(f"📡 Subscribed: {MQTT_TOPICS['status']}")
        
        print("=" * 50)
    else:
        is_connected = False
        error_messages = {
            1: "Protocol version không đúng",
            2: "Client ID không hợp lệ",
            3: "Server không khả dụng",
            4: "Username/password sai",
            5: "Không được phép kết nối"
        }
        print(f"❌ Kết nối MQTT thất bại!")
        print(f"   Lỗi: {error_messages.get(rc, f'Unknown error {rc}')}")

def on_disconnect(client, userdata, rc):
    """Callback khi mất kết nối"""
    global is_connected
    is_connected = False
    print(f"⚠️ Mất kết nối MQTT (code: {rc})")
    
    if rc != 0:
        print("   Đang thử kết nối lại...")

def on_message(client, userdata, msg):
    """
    Callback khi nhận được message từ MQTT
    
    Đây là hàm quan trọng nhất - xử lý tất cả dữ liệu từ ESP32
    """
    topic = msg.topic
    
    try:
        # Giải mã payload từ bytes sang string, rồi sang JSON
        payload = json.loads(msg.payload.decode('utf-8'))
    except json.JSONDecodeError:
        # Nếu không phải JSON, giữ nguyên string
        payload = msg.payload.decode('utf-8')
    except:
        print(f"❌ Lỗi giải mã message từ {topic}")
        return
    
    print(f"📩 Nhận MQTT: {topic}")
    print(f"   Payload: {str(payload)[:100]}...")  # In 100 ký tự đầu
    
    # Xử lý theo topic
    if topic == MQTT_TOPICS['data']:
        handle_sensor_data(payload)
    elif topic == MQTT_TOPICS['camera']:
        handle_camera_data(payload)
    elif topic == MQTT_TOPICS['status']:
        handle_status_data(payload)
    else:
        print(f"   ⚠️ Topic không xử lý: {topic}")


# ==================== DATA HANDLERS ====================

def handle_sensor_data(payload):
    """
    Xử lý dữ liệu sensor từ ESP32
    
    Payload format từ ESP32:
    {
        "slot": 1,
        "value": 28.5
    }
    
    Hoặc nhiều slot cùng lúc:
    {
        "data": [
            {"slot": 1, "value": 28.5},
            {"slot": 2, "value": 65}
        ]
    }
    """
    from models import save_slot_data, get_slot_by_number
    
    try:
        # Trường hợp 1: Một slot
        if 'slot' in payload and 'value' in payload:
            slot_number = payload['slot']
            value = payload['value']
            
            # Kiểm tra slot có tồn tại không
            slot = get_slot_by_number(slot_number)
            if slot:
                save_slot_data(slot_number, value)
                print(f"   ✅ Saved: Slot {slot_number} = {value}")
            else:
                print(f"   ⚠️ Slot {slot_number} chưa được cấu hình")
        
        # Trường hợp 2: Nhiều slot
        elif 'data' in payload and isinstance(payload['data'], list):
            for item in payload['data']:
                if 'slot' in item and 'value' in item:
                    slot_number = item['slot']
                    value = item['value']
                    
                    slot = get_slot_by_number(slot_number)
                    if slot:
                        save_slot_data(slot_number, value)
                        print(f"   ✅ Saved: Slot {slot_number} = {value}")
        
        else:
            print("   ⚠️ Payload format không đúng")
            
    except Exception as e:
        print(f"   ❌ Lỗi xử lý sensor data: {e}")

def handle_camera_data(payload):
    """
    Xử lý ảnh từ ESP32-CAM
    
    Payload format:
    {
        "slot": 5,
        "image": "data:image/jpeg;base64,/9j/4AAQ..."
    }
    """
    from models import save_camera_image, get_slot_by_number
    
    try:
        slot_number = payload.get('slot')
        image_data = payload.get('image')
        
        if slot_number and image_data:
            slot = get_slot_by_number(slot_number)
            if slot and slot['type'] == 'camera':
                save_camera_image(slot_number, image_data)
                print(f"   ✅ Saved: Camera Slot {slot_number}")
            else:
                print(f"   ⚠️ Slot {slot_number} không phải camera")
        else:
            print("   ⚠️ Thiếu slot hoặc image data")
            
    except Exception as e:
        print(f"   ❌ Lỗi xử lý camera data: {e}")

def handle_status_data(payload):
    """
    Xử lý trạng thái online/offline từ ESP32
    
    Payload format:
    {
        "slot": 1,
        "status": "online"
    }
    """
    try:
        slot_number = payload.get('slot')
        status = payload.get('status')
        
        if slot_number and status:
            print(f"   ℹ️ Slot {slot_number} status: {status}")
            # Có thể lưu vào database nếu cần
            
    except Exception as e:
        print(f"   ❌ Lỗi xử lý status: {e}")


# ==================== PUBLISH FUNCTIONS ====================

def publish_control(slot_number, command):
    """
    Gửi lệnh điều khiển đến ESP32
    
    Dùng khi user bật/tắt thiết bị trên web
    
    Parameters:
    - slot_number: Số slot cần điều khiển
    - command: 0 (tắt) hoặc 1 (bật)
    
    ESP32 sẽ subscribe topic 'iot/control' và nhận:
    {
        "slot": 3,
        "command": 1
    }
    """
    global mqtt_client, is_connected
    
    if not mqtt_client or not is_connected:
        print("❌ MQTT chưa kết nối!")
        return False
    
    payload = {
        "slot": slot_number,
        "command": command
    }
    
    topic = MQTT_TOPICS['control']
    message = json.dumps(payload)
    
    result = mqtt_client.publish(topic, message)
    
    if result.rc == mqtt.MQTT_ERR_SUCCESS:
        print(f"📤 Gửi MQTT: {topic}")
        print(f"   Payload: {message}")
        return True
    else:
        print(f"❌ Lỗi gửi MQTT: {result.rc}")
        return False


# ==================== INIT & STOP ====================

def init_mqtt():
    """
    Khởi tạo và kết nối MQTT client
    
    Gọi hàm này khi server khởi động
    """
    global mqtt_client, is_connected
    
    try:
        # Tạo client với client_id duy nhất
        client_id = "iot-backend-server"
        mqtt_client = mqtt.Client(client_id=client_id)
        
        # Đặt callbacks
        mqtt_client.on_connect = on_connect
        mqtt_client.on_disconnect = on_disconnect
        mqtt_client.on_message = on_message
        
        # Đặt username/password
        mqtt_client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        
        # Cấu hình TLS/SSL (bắt buộc với HiveMQ Cloud port 8883)
        mqtt_client.tls_set(tls_version=ssl.PROTOCOL_TLS)
        
        print("=" * 50)
        print("🔌 ĐANG KẾT NỐI MQTT...")
        print(f"   Broker: {MQTT_BROKER}")
        print(f"   Port: {MQTT_PORT}")
        print(f"   Username: {MQTT_USERNAME}")
        print("=" * 50)
        
        # Kết nối (timeout 60 giây)
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60)
        
        # Chạy loop trong background thread
        # loop_start() tạo thread mới để xử lý MQTT
        # Không block thread chính
        mqtt_client.loop_start()
        
        return True
        
    except Exception as e:
        print(f"❌ Lỗi kết nối MQTT: {e}")
        is_connected = False
        return False

def stop_mqtt():
    """
    Dừng MQTT client
    
    Gọi khi server shutdown
    """
    global mqtt_client, is_connected
    
    if mqtt_client:
        mqtt_client.loop_stop()
        mqtt_client.disconnect()
        is_connected = False
        print("🛑 Đã dừng MQTT client")

def get_mqtt_status():
    """Kiểm tra trạng thái kết nối MQTT"""
    return {
        "connected": is_connected,
        "broker": MQTT_BROKER,
        "port": MQTT_PORT
    }


# ==================== TEST ====================
if __name__ == '__main__':
    import time
    
    print("Testing MQTT connection...")
    
    if init_mqtt():
        print("\nĐợi 5 giây để nhận message...")
        time.sleep(5)
        
        # Test publish
        print("\nTest publish control command...")
        publish_control(3, 1)  # Bật slot 3
        
        time.sleep(2)
        stop_mqtt()
    else:
        print("Không thể kết nối MQTT")
