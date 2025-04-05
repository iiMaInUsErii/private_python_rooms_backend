from flask import Flask, request, jsonify, session
from flask_cors import CORS
import sqlite3
import time
from contextlib import closing
from typing import Optional, Dict, Any, List, Tuple

app = Flask(__name__)
app.secret_key = b'fw!pk4[2f4%#g&bh".<t'  # В продакшене используйте переменные окружения
app.config['CORS_HEADERS'] = 'Content-Type'
CORS(app)

# Конфигурация БД
DATABASE = 'db.db'

def get_db() -> sqlite3.Connection:
    """Возвращает соединение с базой данных."""
    return sqlite3.connect(DATABASE, check_same_thread=False)

def init_db():
    """Инициализирует таблицы базы данных."""
    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            password TEXT NOT NULL
        )''')

        cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room TEXT NOT NULL,
            name TEXT NOT NULL,
            text TEXT NOT NULL,
            time INTEGER NOT NULL,
            read INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (room) REFERENCES rooms(name)
        )''')
        conn.commit()

# Инициализация БД при старте
init_db()

# Вспомогательные функции
def get_session_data() -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Извлекает данные пользователя из сессии или запроса."""
    name = request.json.get('name', session.get('name'))
    room = request.json.get('room', session.get('room'))
    password = request.json.get('password', session.get('password'))
    return name, room, password

def validate_room(room: str, password: str) -> bool:
    """Проверяет, существует ли комната и верный ли пароль."""
    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password FROM rooms WHERE name = ?", (room,))
        result = cursor.fetchone()
        return result is not None and result[0] == password

# Роуты
@app.route("/")
def index():
    """Проверка работоспособности сервера."""
    return jsonify(message='Server working')

@app.route("/chat", methods=['POST', 'GET'])
def chat():
    """Обработчик чат-комнаты."""
    name, room, password = get_session_data()
    
    if not all([name, room, password]):
        return jsonify(error='Missing required parameters'), 400

    with closing(get_db()) as conn:
        cursor = conn.cursor()
        
        # Создание комнаты, если не существует
        cursor.execute("SELECT COUNT(*) FROM rooms WHERE name = ?", (room,))
        if cursor.fetchone()[0] < 1:
            cursor.execute("INSERT INTO rooms (name, password) VALUES (?, ?)", (room, password))
            conn.commit()

        # Проверка пароля и получение сообщений
        if not validate_room(room, password):
            return jsonify(error='Invalid password'), 403

        cursor.execute("SELECT * FROM messages WHERE room = ? ORDER BY time", (room,))
        messages = cursor.fetchall()

    # Сохранение данных в сессии
    session.update(name=name, room=room, password=password)
    
    return jsonify(
        name=name,
        messages=messages,
        room=room
    )

@app.route('/new', methods=['POST'])
def add_message():
    """Добавление нового сообщения."""
    required_fields = ['room', 'name', 'password', 'text']
    if not all(field in request.json for field in required_fields):
        return jsonify(error='Missing required fields'), 400

    room, name, password, text = (request.json[f] for f in required_fields)

    if not validate_room(room, password):
        return jsonify(error='Invalid password'), 403

    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (room, name, text, time) VALUES (?, ?, ?, ?)",
            (room, name, text, int(time.time()))
        )
        conn.commit()

    return jsonify(status='success')

@app.route('/delete', methods=['POST'])
def delete_message():
    """Удаление сообщения."""
    required_fields = ['room', 'name', 'password', 'id']
    if not all(field in request.json for field in required_fields):
        return jsonify(error='Missing required fields'), 400

    room, name, password, msg_id = (request.json[f] for f in required_fields)

    if not validate_room(room, password):
        return jsonify(error='Invalid password'), 403

    with closing(get_db()) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM messages WHERE id = ? AND name = ?",
            (msg_id, name)
        )
        conn.commit()

    return jsonify(status='success')

@app.route('/logout')
def logout():
    """Выход из системы (очистка сессии)."""
    session.clear()
    return jsonify(status='logged out')

# Внимание: этот роут опасен в продакшене!
@app.route('/admin', methods=['GET'])
def admin_panel():
    """Админ-панель (только для демонстрации!)."""
    if 'command' in request.args:
        try:
            with closing(get_db()) as conn:
                cursor = conn.cursor()
                cursor.execute(request.args['command'])
                output = cursor.fetchall()
        except sqlite3.Error as e:
            output = [f"Error: {str(e)}"]
    else:
        output = []
    return jsonify(output=output)  # В продакшене используйте шаблоны с авторизацией

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True)