from flask import Flask, request, render_template, session, jsonify
from flask_cors import CORS, cross_origin
import sqlite3
import time

app = Flask(__name__)
app.secret_key = b'fw!pk4[2f4%#g&bh".<t'
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'
dbconn = sqlite3.connect('db.db', check_same_thread=False)
cursor = dbconn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS rooms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    password TEXT
)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    room TEXT NOT NULL,
    name TEXT NOT NULL,
    text TEXT NOT NULL,
    time INTEGER NOT NULL,
    read INTEGER NOT NULL DEFAULT 0
)''')

@app.route("/")
@cross_origin()
def index():
    return jsonify(message='Server working')

@app.route("/chat", methods=['POST', 'GET', 'SESSION'])
@cross_origin()
def chat():
    if 'name' in request.json:
        name = request.json['name']
        session['name'] = name
    elif 'name' in session:
        name = session['name']
    else:
        return request.json
    if 'room' in request.json:
        room = request.json['room']
        session['room'] = room
    elif 'room' in session:
        room = session['room']
    else:
        return index()
    if 'password' in request.json:
        password = request.json['password']
        session['password'] = password
    elif 'password' in session:
        password = session['password']
    else:
        return index()

    cursor.execute("SELECT COUNT(*) FROM rooms WHERE name = ?", [room])
    if cursor.fetchone()[0] < 1:
        cursor.execute("INSERT INTO rooms (name, password) VALUES (?, ?)", (room, password))
        dbconn.commit()
        cursor.execute("SELECT * FROM messages WHERE room = ? ORDER BY id DESC", [room])
        messages = cursor.fetchall()
        return jsonify(
            name=name,
            messages=messages,
            room=room
        )
    else:
        cursor.execute("SELECT * FROM rooms WHERE name = ?", [room])
        if cursor.fetchall()[0][2] == password:
            cursor.execute("SELECT * FROM messages WHERE room = ? ORDER BY id", [room])
            messages = cursor.fetchall()
            return jsonify(
                name=name,
                messages=messages,
                room=room
            )
        else:
            return jsonify(
                error='Invalid Password'
            )

@app.route('/new', methods=['POST'])
@cross_origin()
def add():
    room = request.json['room']
    name = request.json['name']
    password = request.json['password']
    text = request.json['text']

    cursor.execute("SELECT * FROM rooms WHERE name = ?", [room])
    if cursor.fetchall()[0][2] == password:
        cursor.execute("INSERT INTO messages (room, name, text, time) VALUES (?, ?, ?, ?)", (room, name, text, int(time.time())))
        dbconn.commit()

        return jsonify(
            status='seccessful'
        )
    return jsonify(
        status='error'
    )

@app.route('/delete', methods=['POST'])
@cross_origin()
def delete():
    room = request.json['room']
    name = request.json['name']
    password = request.json['password']
    id = request.json['id']

    cursor.execute("SELECT * FROM rooms WHERE name = ? ", [room])
    if cursor.fetchall()[0][2] == password:
        cursor.execute("DELETE FROM messages WHERE id = ? and name = ?", (id, name))
        dbconn.commit()

        return jsonify(
            status='seccessful'
        )
    return jsonify(
        status='error'
    )

@app.route('/logout')
@cross_origin()
def logout():
    session.clear()
    return index()

@app.route('/admin', methods=['GET'])
@cross_origin()
def admin():
    if request.args.get("command"):
        command = request.args.get("command")
        cursor.execute(command)
        output = cursor.fetchall()
    else:
        output = []
    return render_template("admin.html", output=output)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3000, debug=True, threaded=True, use_reloader=True)
    dbconn.close()