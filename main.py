from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import sqlite3
import time
from contextlib import closing
import os
import hashlib
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'default-secret-key')

CORS(app, resources={
    r"/api/*": {
        "origins": ["http://localhost:5173", "https://chat-app-sooty-kappa.vercel.app"]
    },
    r"/uploads/*": {
        "origins": ["http://localhost:5173", "https://chat-app-sooty-kappa.vercel.app"],
    }
})

UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'txt', 'mp3', 'mp4', 'wav', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

DATABASE = 'chat.db'

def get_db():
    return sqlite3.connect(DATABASE, check_same_thread=False)

def init_db():
    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_id INTEGER NOT NULL,
            user_name TEXT NOT NULL,
            text TEXT NOT NULL,
            timestamp INTEGER NOT NULL,
            is_file INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )''')
        conn.commit()

init_db()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.after_request
def add_cors_headers(response):
    if request.path.startswith('/api/'):
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
        response.headers.add('Access-Control-Allow-Methods', 'GET,POST,OPTIONS')
        response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response

@app.route("/api/check_room", methods=['POST'])
def check_room():
    data = request.json
    room_name = data.get('room')
    password = data.get('password')

    if not room_name or not password:
        return jsonify(error='Room name and password required'), 400

    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, password FROM rooms WHERE name = ?", (room_name,))
        room = cursor.fetchone()

        if room:
            room_id, hashed_pw = room
            if hashed_pw == hash_password(password):
                return jsonify(exists=True, room_id=room_id)
            return jsonify(exists=True, error='Invalid password'), 401
        return jsonify(exists=False)

@app.route("/api/create_room", methods=['POST'])
def create_room():
    data = request.json
    room_name = data.get('room')
    password = data.get('password')

    if not room_name or not password:
        return jsonify(error='Room name and password required'), 400

    hashed_pw = hash_password(password)

    try:
        with closing(get_db()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO rooms (name, password) VALUES (?, ?)",
                (room_name, hashed_pw)
            )
            room_id = cursor.lastrowid
            conn.commit()
        return jsonify(success=True, room_id=room_id)
    except sqlite3.IntegrityError:
        return jsonify(error='Room already exists'), 409

@app.route("/api/messages", methods=['GET'])
def get_messages():
    room_id = request.args.get('room_id')
    if not room_id:
        return jsonify(error='Room ID required'), 400

    try:
        with closing(get_db()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, room_id, user_name, text, timestamp, is_file FROM messages WHERE room_id = ? ORDER BY timestamp ASC",
                (room_id,)
            )
            messages = [
                {
                    'id': row[0],
                    'room_id': row[1],
                    'user': row[2],
                    'text': row[3],
                    'time': row[4],
                    'is_file': row[5],
                } for row in cursor.fetchall()
            ]
        return jsonify(messages=messages)
    except sqlite3.Error:
        return jsonify(error='Database error'), 500

@app.route("/api/send_message", methods=['POST'])
def send_message():
    data = request.json
    room_id = data.get('room_id')
    user_name = data.get('user')
    text = data.get('text')

    if not all([room_id, user_name, text]):
        return jsonify(error='Missing required fields'), 400

    try:
        with closing(get_db()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (room_id, user_name, text, timestamp) VALUES (?, ?, ?, ?)",
                (room_id, user_name, text, int(time.time()))
            )
            conn.commit()
        return jsonify(success=True, message_id=cursor.lastrowid)
    except sqlite3.Error:
        return jsonify(error='Failed to send message'), 500

@app.route("/api/delete_message", methods=['POST'])
def delete_message():
    data = request.json
    message_id = data.get('message_id')
    user_name = data.get('user')

    if not message_id or not user_name:
        return jsonify(error='Missing required fields'), 400

    try:
        with closing(get_db()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM messages WHERE id = ? AND user_name = ?",
                (message_id, user_name)
            )
            if cursor.rowcount == 0:
                return jsonify(error='Message not found or not authorized'), 404
            conn.commit()
        return jsonify(success=True)
    except sqlite3.Error:
        return jsonify(error='Database error'), 500
    
@app.route('/api/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify(error='No file part'), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify(error='No selected file'), 400
    
    if not allowed_file(file.filename):
        return jsonify(error='File type not allowed'), 400
    
    try:
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        # Получаем данные из формы
        room_id = request.form['room_id']
        user_name = request.form['user_name']

        print(request.form)
        
        if not room_id or not user_name:
            os.remove(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            return jsonify(error='Missing room_id or user_name'), 400
        
        # Сохраняем в БД (добавляем is_file=1)
        with closing(get_db()) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO messages (room_id, user_name, text, timestamp, is_file) VALUES (?, ?, ?, ?, ?)",
                (room_id, user_name, filename, int(time.time()), 1)
            )
            conn.commit()
        
        return jsonify(
            success=True,
            filename=filename,
            url=f'/uploads/{filename}'
        )
    except Exception as e:
        return jsonify(error=str(e)), 500

# Маршрут для доступа к загруженным файлам
@app.route('/uploads/<filename>')
def serve_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)