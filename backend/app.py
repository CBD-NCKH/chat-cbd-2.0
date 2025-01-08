import sqlite3
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from flask_session import Session
from openai import OpenAI
import os
from dotenv import load_dotenv
import spacy
from pyvi import ViTokenizer, ViPosTagger
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import hashlib

# Tải mô hình ngôn ngữ spaCy
nlp = spacy.load("en_core_web_sm")

# Load API Key từ file .env
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Tạo một instance client OpenAI
client = OpenAI(api_key=api_key)

# Kết nối Google Sheets
def connect_google_sheet(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds = ServiceAccountCredentials.from_json_keyfile_name("/etc/secrets/credentials.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open(sheet_name).sheet1
    return sheet

# Hash mật khẩu để lưu trữ và xác thực an toàn
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Hàm tạo tài khoản người dùng
def create_account(sheet, username, password):
    users = sheet.get_all_values()
    for row in users:
        if len(row) >= 1 and row[0] == username:  # Kiểm tra nếu username đã tồn tại
            return False, "Username already exists."

    hashed_password = hash_password(password)  # Hash mật khẩu
    sheet.append_row([username, hashed_password, "", ""])
    return True, "Account created successfully."

# Hàm xác thực người dùng
def authenticate_user(sheet, username, password):
    users = sheet.get_all_values()
    hashed_password = hash_password(password)

    for row in users:
        if len(row) >= 2 and row[0] == username and row[1] == hashed_password:
            return True
    return False

# Hàm lưu lịch sử hội thoại vào Google Sheets
def save_to_google_sheet(sheet, username, role, content):
    sheet.append_row([username, role, content])

# Hàm lấy hội thoại gần nhất của người dùng
def get_user_conversation(sheet, username, max_rows=4):
    rows = sheet.get_all_values()
    user_rows = [row for row in rows if len(row) >= 3 and row[0] == username]
    return user_rows[-max_rows:] if len(user_rows) > max_rows else user_rows

# Khởi tạo ứng dụng Flask
app = Flask(__name__, template_folder='templates')
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'supersecretkey')
app.config['SESSION_TYPE'] = 'filesystem'  # Lưu session trong file hệ thống
app.config['SESSION_FILE_DIR'] = '/tmp/flask_session'  # Thư mục lưu trữ session
app.config['SESSION_PERMANENT'] = False  # Không giữ session vĩnh viễn
Session(app)

CORS(app, resources={r"/api/*": {"origins": "https://chat-cbd-2-0.onrender.com"}})

# Hàm trích xuất từ khóa tiếng Anh
def extract_keywords_spacy(message):
    doc = nlp(message)
    keywords = [token.text for token in doc if token.pos_ in {"NOUN", "VERB", "ADJ"}]
    return list(set(keywords))

# Hàm trích xuất từ khóa tiếng Việt bằng Pyvi
def extract_keywords_pyvi(message):
    tokens = ViTokenizer.tokenize(message)
    tagged_words = ViPosTagger.postagging(tokens)
    keywords = [word for word, pos in zip(tagged_words[0], tagged_words[1]) if pos in {"N", "V", "A"}]
    return list(set(keywords))

# Hàm xử lý ngôn ngữ đa ngôn ngữ
def extract_keywords_multilingual(message):
    try:
        keywords_en = extract_keywords_spacy(message)
    except Exception:
        keywords_en = []

    try:
        keywords_vi = extract_keywords_pyvi(message)
    except Exception:
        keywords_vi = []

    return list(set(keywords_en + keywords_vi))

# Hàm truy vấn SQLite theo từ khóa
def query_sqlite_with_keywords(table_name, keywords):
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    conditions = []
    params = []
    for keyword in keywords:
        conditions.append(f"Chapter LIKE ? OR `Sub-topic` LIKE ?")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    where_clause = " OR ".join(conditions)
    query = f"SELECT * FROM {table_name} WHERE {where_clause}"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return rows

# Route mặc định để render giao diện
@app.route('/')
def home():
    return render_template('index.html')

# API xử lý đăng ký
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    sheet = connect_google_sheet("ChatHistory")
    success, message = create_account(sheet, username, password)

    if success:
        return jsonify({"message": message}), 201
    else:
        return jsonify({"error": message}), 400

# API xử lý đăng nhập
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    sheet = connect_google_sheet("ChatHistory")
    if authenticate_user(sheet, username, password):
        session['username'] = username
        session['password'] = password
        return jsonify({"message": "Login successful."}), 200
    else:
        return jsonify({"error": "Invalid username or password."}), 401

# API xử lý tin nhắn
@app.route('/api', methods=['POST'])
def api():
    try:
        if 'username' not in session or 'password' not in session:
            return jsonify({"error": "Unauthorized. Please log in first."}), 401

        username = session['username']
        password = session['password']

        sheet = connect_google_sheet("ChatHistory")

        if not authenticate_user(sheet, username, password):
            return jsonify({"error": "Authentication failed."}), 401

        data = request.json
        user_message = data.get("message")

        memory = get_user_conversation(sheet, username, max_rows=4)
        memory_context = "\n".join([f"{row[1]}: {row[2]}" for row in memory if len(row) >= 3])

        keywords = extract_keywords_multilingual(user_message)
        db_result = query_sqlite_with_keywords("DatasetTable", keywords)

        db_context = "\n".join([f"Row {i+1}: {row}" for i, row in enumerate(db_result)])
        context = (
            f"Dữ liệu từ cơ sở dữ liệu:\n{db_context}\n\n"
            f"Lịch sử hội thoại:\n{memory_context}\n\n"
            f"Câu hỏi của người dùng: {user_message}"
        )

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "Bạn là một trợ lý ảo thông minh."},
                {"role": "user", "content": context}
            ],
            max_tokens=16384,
            temperature=0.7
        )

        bot_reply = response.choices[0].message.content

        save_to_google_sheet(sheet, username, "user", user_message)
        save_to_google_sheet(sheet, username, "assistant", bot_reply)

        return jsonify({"reply": bot_reply})

    except Exception as e:
        print(f"Lỗi: {e}")
        return jsonify({"error": "Có lỗi xảy ra khi kết nối OpenAI"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
