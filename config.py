import os

SECRET_KEY = os.environ.get('SECRET_KEY', 'iot-secret-key-2024')
DATABASE_URL = os.environ.get('DATABASE_URL')

MQTT_BROKER = os.environ.get('MQTT_BROKER', 'localhost')
MQTT_PORT = int(os.environ.get('MQTT_PORT', 8883))
MQTT_USERNAME = os.environ.get('MQTT_USERNAME', '')
MQTT_PASSWORD = os.environ.get('MQTT_PASSWORD', '')

RESEND_API_KEY = os.environ.get('RESEND_API_KEY', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', 'onboarding@resend.dev')

MAX_SLOTS = 20
