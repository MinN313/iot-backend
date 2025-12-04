import os
from config import DATABASE_URL, MAX_SLOTS

if DATABASE_URL:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    USE_POSTGRES = True
    print("✅ PostgreSQL")
else:
    import sqlite3
    USE_POSTGRES = False
    DATABASE_PATH = "iot_database.db"
    print("✅ SQLite")

def get_db():
    if USE_POSTGRES:
        return psycopg2.connect(DATABASE_URL)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_cursor(conn):
    if USE_POSTGRES:
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()

def dict_row(row):
    return dict(row) if row else None

def q(query, params=None, one=False, all=False):
    conn = get_db()
    cur = get_cursor(conn)
    if USE_POSTGRES and params:
        query = query.replace('?', '%s')
    try:
        cur.execute(query, params) if params else cur.execute(query)
        if one:
            r = cur.fetchone()
            cur.close(); conn.close()
            return dict_row(r)
        elif all:
            r = cur.fetchall()
            cur.close(); conn.close()
            return [dict_row(x) for x in r]
        else:
            conn.commit()
            lid = None
            if USE_POSTGRES:
                try:
                    cur.execute("SELECT lastval()")
                    lid = cur.fetchone()['lastval']
                except: pass
            else:
                lid = cur.lastrowid
            cur.close(); conn.close()
            return lid
    except Exception as e:
        print(f"DB Error: {e}")
        cur.close(); conn.close()
        raise e

def init_db():
    conn = get_db()
    cur = get_cursor(conn)
    
    if USE_POSTGRES:
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, name TEXT,
            role TEXT DEFAULT 'user', avatar TEXT DEFAULT '',
            theme TEXT DEFAULT 'dark', language TEXT DEFAULT 'vi',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS slots (
            id SERIAL PRIMARY KEY, slot_number INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL, type TEXT NOT NULL, icon TEXT DEFAULT '📟',
            unit TEXT DEFAULT '', location TEXT DEFAULT '', stream_url TEXT,
            is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS slot_data (
            id SERIAL PRIMARY KEY, slot_number INTEGER NOT NULL,
            value TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS camera_images (
            id SERIAL PRIMARY KEY, slot_number INTEGER UNIQUE NOT NULL,
            image_data TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS reset_codes (
            id SERIAL PRIMARY KEY, email TEXT NOT NULL,
            code TEXT NOT NULL, expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    else:
        cur.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL, name TEXT,
            role TEXT DEFAULT 'user', avatar TEXT DEFAULT '',
            theme TEXT DEFAULT 'dark', language TEXT DEFAULT 'vi',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS slots (
            id INTEGER PRIMARY KEY AUTOINCREMENT, slot_number INTEGER UNIQUE NOT NULL,
            name TEXT NOT NULL, type TEXT NOT NULL, icon TEXT DEFAULT '📟',
            unit TEXT DEFAULT '', location TEXT DEFAULT '', stream_url TEXT,
            is_active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS slot_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT, slot_number INTEGER NOT NULL,
            value TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS camera_images (
            id INTEGER PRIMARY KEY AUTOINCREMENT, slot_number INTEGER UNIQUE NOT NULL,
            image_data TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS reset_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL,
            code TEXT NOT NULL, expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    conn.commit()
    
    # Create admin
    cur.execute("SELECT id FROM users WHERE email = 'admin@admin.com'")
    if not cur.fetchone():
        from auth import hash_password
        pw = hash_password('admin123')
        if USE_POSTGRES:
            cur.execute("INSERT INTO users (email, password_hash, name, role) VALUES (%s, %s, %s, %s)",
                       ('admin@admin.com', pw, 'Administrator', 'admin'))
        else:
            cur.execute("INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)",
                       ('admin@admin.com', pw, 'Administrator', 'admin'))
        conn.commit()
        print("✅ Created admin: admin@admin.com / admin123")
    
    cur.close(); conn.close()
    print("✅ Database OK!")

# ===== USER =====
def get_user_by_email(email):
    return q("SELECT * FROM users WHERE email = ?", (email,), one=True)

def get_user_by_id(uid):
    return q("SELECT id, email, name, role, avatar, theme, language, created_at FROM users WHERE id = ?", (uid,), one=True)

def create_user(email, pw_hash, name, role='user'):
    try:
        uid = q("INSERT INTO users (email, password_hash, name, role) VALUES (?, ?, ?, ?)", (email, pw_hash, name, role))
        return uid, None
    except:
        return None, "Email đã tồn tại"

def get_all_users():
    return q("SELECT id, email, name, role, avatar, theme, language, created_at FROM users ORDER BY created_at DESC", all=True)

def update_user_role(uid, role):
    q("UPDATE users SET role = ? WHERE id = ?", (role, uid))

def update_user_profile(uid, name=None, avatar=None, theme=None, language=None):
    user = get_user_by_id(uid)
    if not user: return False
    q("UPDATE users SET name=COALESCE(?,name), avatar=COALESCE(?,avatar), theme=COALESCE(?,theme), language=COALESCE(?,language) WHERE id=?",
      (name, avatar, theme, language, uid))
    return True

def update_user_password(uid, new_pw):
    from auth import hash_password
    q("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_pw), uid))

def delete_user(uid):
    q("DELETE FROM users WHERE id = ?", (uid,))

def admin_reset_password(uid, new_pw):
    from auth import hash_password
    q("UPDATE users SET password_hash = ? WHERE id = ?", (hash_password(new_pw), uid))

# ===== SLOT =====
def get_all_slots():
    return q("SELECT * FROM slots WHERE is_active = 1 ORDER BY slot_number", all=True)

def get_slot_by_number(num):
    return q("SELECT * FROM slots WHERE slot_number = ?", (num,), one=True)

def create_slot(num, name, stype, icon='📟', unit='', loc='', stream=''):
    if num < 1 or num > MAX_SLOTS:
        return None, f"Slot 1-{MAX_SLOTS}"
    try:
        sid = q("INSERT INTO slots (slot_number,name,type,icon,unit,location,stream_url) VALUES (?,?,?,?,?,?,?)",
               (num, name, stype, icon, unit, loc, stream))
        return sid, None
    except:
        return None, f"Slot {num} đã tồn tại"

def update_slot(num, name=None, stype=None, icon=None, unit=None, loc=None, stream=None):
    if not get_slot_by_number(num):
        return False, "Slot không tồn tại"
    q("UPDATE slots SET name=COALESCE(?,name), type=COALESCE(?,type), icon=COALESCE(?,icon), unit=COALESCE(?,unit), location=COALESCE(?,location), stream_url=COALESCE(?,stream_url) WHERE slot_number=?",
      (name, stype, icon, unit, loc, stream, num))
    return True, None

def delete_slot(num):
    q("DELETE FROM slot_data WHERE slot_number = ?", (num,))
    q("DELETE FROM camera_images WHERE slot_number = ?", (num,))
    q("DELETE FROM slots WHERE slot_number = ?", (num,))

def get_available_slot_numbers():
    slots = q("SELECT slot_number FROM slots WHERE is_active = 1", all=True)
    used = set(s['slot_number'] for s in slots)
    return [i for i in range(1, MAX_SLOTS + 1) if i not in used]

# ===== DATA =====
def save_slot_data(num, val):
    return q("INSERT INTO slot_data (slot_number, value) VALUES (?, ?)", (num, str(val)))

def get_latest_slot_data(num):
    return q("SELECT * FROM slot_data WHERE slot_number = ? ORDER BY created_at DESC LIMIT 1", (num,), one=True)

def get_all_latest_data():
    data = {}
    for s in get_all_slots():
        d = get_latest_slot_data(s['slot_number'])
        if d: data[s['slot_number']] = d
    return data

def get_slot_history(num, limit=100):
    return q("SELECT * FROM slot_data WHERE slot_number = ? ORDER BY created_at DESC LIMIT ?", (num, limit), all=True)

# ===== CAMERA =====
def save_camera_image(num, img):
    q("DELETE FROM camera_images WHERE slot_number = ?", (num,))
    q("INSERT INTO camera_images (slot_number, image_data) VALUES (?, ?)", (num, img))

def get_camera_image(num):
    return q("SELECT * FROM camera_images WHERE slot_number = ?", (num,), one=True)

# ===== RESET PASSWORD =====
def create_reset_code(email):
    import random
    user = get_user_by_email(email)
    if not user: return None, "Email không tồn tại"
    code = str(random.randint(100000, 999999))
    q("DELETE FROM reset_codes WHERE email = ?", (email,))
    if USE_POSTGRES:
        q("INSERT INTO reset_codes (email, code, expires_at) VALUES (?, ?, CURRENT_TIMESTAMP + INTERVAL '15 minutes')", (email, code))
    else:
        q("INSERT INTO reset_codes (email, code, expires_at) VALUES (?, ?, datetime('now', '+15 minutes'))", (email, code))
    return code, None

def verify_reset_code(email, code):
    if USE_POSTGRES:
        r = q("SELECT * FROM reset_codes WHERE email = ? AND code = ? AND expires_at > CURRENT_TIMESTAMP", (email, code), one=True)
    else:
        r = q("SELECT * FROM reset_codes WHERE email = ? AND code = ? AND expires_at > datetime('now')", (email, code), one=True)
    return r is not None

def reset_password(email, new_pw):
    from auth import hash_password
    q("UPDATE users SET password_hash = ? WHERE email = ?", (hash_password(new_pw), email))
    q("DELETE FROM reset_codes WHERE email = ?", (email,))

# ===== DASHBOARD =====
def get_dashboard_stats():
    t = q("SELECT COUNT(*) as count FROM slots WHERE is_active = 1", one=True)
    c = q("SELECT COUNT(*) as count FROM slots WHERE is_active = 1 AND type = 'camera'", one=True)
    co = q("SELECT COUNT(*) as count FROM slots WHERE is_active = 1 AND type = 'control'", one=True)
    ch = q("SELECT COUNT(*) as count FROM slots WHERE is_active = 1 AND type = 'chart'", one=True)
    return {
        'total_slots': t['count'] if t else 0,
        'total_cameras': c['count'] if c else 0,
        'total_controls': co['count'] if co else 0,
        'total_charts': ch['count'] if ch else 0
    }

if __name__ == '__main__':
    init_db()
