import paho.mqtt.client as mqtt
import ssl
import json
from config import MQTT_BROKER, MQTT_PORT, MQTT_USERNAME, MQTT_PASSWORD

client = None
mqtt_connected = False

def on_connect(c, userdata, flags, rc):
    global mqtt_connected
    if rc == 0:
        mqtt_connected = True
        print("✅ MQTT Connected!")
        c.subscribe("iot/data")
        c.subscribe("iot/camera")
        c.subscribe("iot/status")
    else:
        mqtt_connected = False
        print(f"❌ MQTT Failed: {rc}")

def on_disconnect(c, userdata, rc):
    global mqtt_connected
    mqtt_connected = False
    print("⚠️ MQTT Disconnected")

def on_message(c, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
        topic = msg.topic
        
        if topic == "iot/data":
            from models import save_slot_data, get_slot_by_number
            slot = data.get('slot')
            value = data.get('value')
            if slot and value is not None:
                if get_slot_by_number(slot):
                    save_slot_data(slot, value)
                    print(f"📊 Slot {slot}: {value}")
        
        elif topic == "iot/camera":
            from models import save_camera_image, get_slot_by_number
            slot = data.get('slot')
            image = data.get('image')
            if slot and image:
                if get_slot_by_number(slot):
                    save_camera_image(slot, image)
                    print(f"📷 Camera {slot} updated")
    except Exception as e:
        print(f"MQTT Error: {e}")

def init_mqtt():
    global client
    if not MQTT_BROKER:
        print("⚠️ MQTT not configured")
        return
    
    try:
        client = mqtt.Client()
        client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
        client.tls_set(cert_reqs=ssl.CERT_NONE)
        client.tls_insecure_set(True)
        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = on_message
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        client.loop_start()
        print(f"🔄 MQTT connecting to {MQTT_BROKER}...")
    except Exception as e:
        print(f"❌ MQTT Error: {e}")

def publish_control(slot, command):
    global client, mqtt_connected
    if not client or not mqtt_connected:
        return False
    try:
        payload = json.dumps({"slot": slot, "command": command})
        client.publish("iot/control", payload)
        print(f"📤 Control Slot {slot}: {command}")
        return True
    except:
        return False

def get_mqtt_status():
    return {"connected": mqtt_connected, "broker": MQTT_BROKER}
