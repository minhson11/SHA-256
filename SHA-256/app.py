from flask import Flask, render_template, request, redirect, session, send_from_directory
from flask_socketio import SocketIO, emit, join_room
import os, json, hashlib, uuid
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "supersecretkey"
socketio = SocketIO(app, cors_allowed_origins="*")

UPLOAD_FOLDER = "files/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

with open("users.json") as f:
    USERS = {u["username"]: u["password"] for u in json.load(f)}

@app.route("/")
def index():
    if "username" in session:
        return render_template("index.html", username=session["username"], users=list(USERS.keys()))
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        if USERS.get(username) == password:
            session["username"] = username
            return redirect("/")
        return "Đăng nhập thất bại. <a href='/login'>Thử lại</a>"
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("username", None)
    return redirect("/login")

@app.route("/download/<file_id>_<filename>")
def download_file(file_id, filename):
    return send_from_directory(UPLOAD_FOLDER, f"{file_id}_{filename}", as_attachment=True)

@socketio.on("connect")
def on_connect():
    if "username" in session:
        join_room(session["username"])
        emit("status", f"Connected as {session['username']}")

@socketio.on("send_file")
def handle_send_file(data):
    sender = session.get("username")
    receiver = data.get("receiver")
    filename = secure_filename(data.get("filename"))
    file_bytes = bytes(data.get("filedata"))
    client_sha256 = data.get("sha256")

    if not sender or not receiver or not filename or not file_bytes or not client_sha256:
        emit("error", "Thiếu thông tin gửi file")
        return

    # Server tính SHA256
    server_sha256 = hashlib.sha256(file_bytes).hexdigest()

    # So sánh client và server SHA256
    if client_sha256 != server_sha256:
        print(f"CẢNH BÁO: SHA256 client và server KHÔNG KHỚP! client={client_sha256} server={server_sha256}")

    # Lưu file
    file_id = str(uuid.uuid4())
    filepath = os.path.join(UPLOAD_FOLDER, f"{file_id}_{filename}")
    with open(filepath, "wb") as f:
        f.write(file_bytes)

    # Gửi info file cho người nhận
    emit("receive_file", {
        "file_id": file_id,
        "filename": filename,
        "sha256": server_sha256,
        "sender": sender
    }, room=receiver)

    emit("status", f"File '{filename}' đã gửi đến {receiver}")

if __name__ == "__main__":
    socketio.run(app, debug=True)
