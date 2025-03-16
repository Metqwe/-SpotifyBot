import sqlite3

def init_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tracks (
            id TEXT PRIMARY KEY,
            file_path TEXT
        )
    ''')
    conn.commit()
    conn.close()

def add_track(track_id, file_path):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO tracks (id, file_path) VALUES (?, ?)", (track_id, file_path))
    conn.commit()
    conn.close()

def get_track(track_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM tracks WHERE id=?", (track_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_tracks():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, file_path FROM tracks")
    result = cursor.fetchall()
    conn.close()
    return result
