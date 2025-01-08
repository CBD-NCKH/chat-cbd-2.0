import sqlite3
from flask import Flask, request, jsonify, render_template, session
from flask_cors import CORS
from flask_session import Session
from flask.sessions import SecureCookieSessionInterface
from openai import OpenAI
import os
from dotenv import load_dotenv
import spacy
from pyvi import ViTokenizer, ViPosTagger
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import hashlib
import shutil

shutil.rmtree("/tmp/flask_session", ignore_errors=True)

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


# Tạo thư mục lưu session nếu chưa tồn tại
try:
    session_dir = '/tmp/flask_session'  # Thư mục lưu session
    if not os.path.exists(session_dir):
        os.makedirs(session_dir)  # Tạo thư mục nếu chưa tồn tại

    # Kiểm tra quyền ghi
    if not os.access(session_dir, os.W_OK):
        raise PermissionError(f"Thư mục {session_dir} không có quyền ghi. Vui lòng kiểm tra lại quyền truy cập.")
except Exception as e:
    print(f"Lỗi khi thiết lập thư mục session: {e}")
    raise e  # Ném lỗi để ngăn ứng dụng chạy khi cấu hình sai

# Khởi tạo ứng dụng Flask
app = Flask(__name__, template_folder='templates')

# Cấu hình session cho Flask
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'supersecretkey')  # Khóa bí mật
app.config['SESSION_TYPE'] = 'filesystem'  # Lưu session trong file hệ thống
app.config['SESSION_FILE_DIR'] = session_dir  # Thư mục lưu trữ session
app.config['SESSION_PERMANENT'] = False  # Không giữ session vĩnh viễn
app.config['SESSION_USE_SIGNER'] = True  # Bảo mật session với chữ ký
app.config['SESSION_COOKIE_NAME'] = 'session'  # Tên cookie của session

# Ghi đè phương thức set_cookie để đảm bảo giá trị là string

class CustomSessionInterface(SecureCookieSessionInterface):
    def save_session(self, app, session, response):
        if not session:
            self.session_store.delete(session.sid)
            return

        # Log giá trị session.sid
        print(f"Original session.sid: {session.sid}, type: {type(session.sid)}")

        # Chuyển đổi nếu cần
        if isinstance(session.sid, bytes):
            print("Converting session ID from bytes to string")
            session.sid = session.sid.decode('utf-8')

        if not isinstance(session.sid, str):
            raise TypeError(f"Session ID must be a string, got {type(session.sid)}")

        super(CustomSessionInterface, self).save_session(app, session, response)


app.session_interface = CustomSessionInterface()

Session(app)


CORS(app, resources={r"/*": {"origins": "https://chat-cbd-2-0.onrender.com"}})

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

# Xử lý lỗi 404 - Not Found
@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Resource not found."}), 404

# Xử lý lỗi 500 - Internal Server Error
@app.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "Internal server error. Please try again later."}), 500

# Xử lý các lỗi khác
@app.errorhandler(Exception)
def handle_exception(error):
    print(f"Unexpected error: {error}")  # Log lỗi chi tiết trên server
    return jsonify({"error": "An unexpected error occurred."}), 500

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
                {
                    "role": "system",
                    "content": (
                        "Bạn là một trợ lý ảo (tên là ChatCBD 3.0, do Châu Phúc Khang và Trần Hoàng Thiên Phúc phát triển) chuyên hỗ trợ các câu hỏi liên quan đến Calculus BC. "
                        "Bạn có cơ sở dữ liệu chứa các lý thuyết và kiến thức toán học liên quan nhưng chỉ cần truy cập vào kho này nếu câu hỏi là về toántoán. "
                        "1. Khi trả lời câu hỏi liên quan đến toán cần phân chia câu trả lời thành 2 phần rõ ràng: "
                        "   - Phần 1: Trích dẫn cụ thể các lý thuyết có liên quan trực tiếp từ cơ sở dữ liệu của bạn (có thể bao gồm các định nghĩa, công thức) hoặc đoạn nội dung liên quan. Lưu ý phần trích dẫn bằng tiếng anh thì bỏ trong ngoặc kép đóng lại và bên cạnh đó ghi thêm 1 phần bản dịch của phần trích dẫn đó ngay tiếp theotheo"
                        "Nếu không có kiến thức trong cơ sở dữ liệu, nhấn mạnh rằng 'Dù kiến thức này không thuộc cơ sở dữ liệu của tôi, tôi vẫn có thể hỗ trợ bạn với đầy đủ thông tin.' "
                        "   - Phần 2: Mở rộng giải thích, diễn dài và chi tiết, sử dụng ngôn ngữ dễ hiểu để trình bày nội dung trong phần 1, có thể kèm thêm ví dụ thực tế hoặc bài toán mẫu. "
                        "Nếu thông tin không có trong phần 1, sẽ tìm kiếm và hỗ trợ bằng các nguồn thông tin đáng tin cậy từ bên ngoài. "
                        "2. Chủ động hỏi người dùng cần biết thêm về câu hỏi gì để giúp đỡ. "
                        "3. Sử dụng ngôn ngữ thân thiện và dễ tiếp cận để khuyến khích người dùng học tập."
                    )
                },
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
