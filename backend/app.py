import sqlite3
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from openai import OpenAI
import os
from dotenv import load_dotenv
import spacy
from pyvi import ViTokenizer, ViPosTagger
import gspread
from oauth2client.service_account import ServiceAccountCredentials

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

# Hàm lưu lịch sử hội thoại vào Google Sheets
def save_to_google_sheet(sheet, role, content):
    sheet.append_row([role, content])

def get_latest_conversation(sheet, max_rows=4):
    rows = sheet.get_all_values()  # Lấy toàn bộ dữ liệu từ Google Sheets
    if not rows:
        rows = [["", ""]]  # Đặt giá trị mặc định nếu không có dữ liệu
    return rows[-max_rows:] if len(rows) > max_rows else rows  # Lấy các dòng cuối cùng

# Khởi tạo ứng dụng Flask    
app = Flask(__name__, template_folder='templates')
CORS(app, resources={r"/api/*": {"origins": "https://chat-cbd-2-0.onrender.com"}})

# Hàm trích xuất từ khóa tiếng Anh
def extract_keywords_spacy(message):
    doc = nlp(message)
    keywords = [token.text for token in doc if token.pos_ in {"NOUN", "VERB", "ADJ"}]
    return list(set(keywords))

# Hàm trích xuất từ khóa tiếng Việt bằng Pyvi
def extract_keywords_pyvi(message):
    tokens = ViTokenizer.tokenize(message)  # Tokenize văn bản tiếng Việt
    tagged_words = ViPosTagger.postagging(tokens)  # POS tagging
    keywords = [word for word, pos in zip(tagged_words[0], tagged_words[1]) if pos in {"N", "V", "A"}]  # Danh từ, động từ, tính từ
    return list(set(keywords))

# Hàm xử lý ngôn ngữ đa ngôn ngữ
def extract_keywords_multilingual(message):
    try:
        # Dùng spaCy cho tiếng Anh
        keywords_en = extract_keywords_spacy(message)
    except Exception:
        keywords_en = []
    
    try:
        # Dùng Pyvi cho tiếng Việt
        keywords_vi = extract_keywords_pyvi(message)
    except Exception:
        keywords_vi = []
    
    # Kết hợp từ khóa tiếng Anh và tiếng Việt
    return list(set(keywords_en + keywords_vi))

# Hàm truy vấn SQLite theo từ khóa
def query_sqlite_with_keywords(table_name, keywords):
    conn = sqlite3.connect("chatbot.db")
    cursor = conn.cursor()

    # Tạo điều kiện tìm kiếm theo từ khóa
    conditions = []
    params = []
    for keyword in keywords:
        conditions.append(f"Chapter LIKE ? OR `Sub-topic` LIKE ?")
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    # Gộp điều kiện bằng OR
    where_clause = " OR ".join(conditions)

    # Thực hiện câu truy vấn
    query = f"SELECT * FROM {table_name} WHERE {where_clause}"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()

    return rows

# Route mặc định để render giao diện
@app.route('/')
def home():
    return render_template('index.html')

# API xử lý tin nhắn
@app.route('/api', methods=['POST'])
def api():
    try:
        data = request.json
        user_message = data.get("message")

        sheet = connect_google_sheet("ChatHistory")

        # Lấy các dòng hội thoại gần nhất từ Google Sheets
        memory = get_latest_conversation(sheet, max_rows=4)

        # Chuyển dữ liệu từ Google Sheets thành ngữ cảnh
        memory_context = "\n".join([f"{row[0]}: {row[1]}" for row in memory if len(row) >= 2])


        # Trích xuất từ khóa từ user_message bằng spaCy và Pyvi
        keywords = extract_keywords_multilingual(user_message)

        # Truy vấn dữ liệu SQLite với từ khóa
        db_result = query_sqlite_with_keywords("DatasetTable", keywords)

        # Tạo context từ dữ liệu SQLite và tin nhắn người dùng
        db_context = "\n".join([f"Row {i+1}: {row}" for i, row in enumerate(db_result)])
        context = (
            f"Dữ liệu từ cơ sở dữ liệu:\n{db_context}\n\n"
            f"Lịch sử hội thoại:\n{memory_context}\n\n"
            f"Câu hỏi của người dùng: {user_message}"
        )

        # Gửi yêu cầu tới OpenAI API qua instance client
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Bạn là một trợ lý ảo (tên là ChatCBD 3.0, do Châu Phúc Khang và Trần Hoàng Thiên Phúc phát triển) chuyên hỗ trợ các câu hỏi liên quan đến Calculus BC. "
                        "Bạn có cơ sở dữ liệu chứa các lý thuyết và kiến thức toán học liên quan. "
                        "Khi trả lời câu hỏi: "
                        "1. Phân chia câu trả lời thành 2 phần rõ ràng: "
                        "   - Phần 1: Trích dẫn cụ thể các lý thuyết có liên quan trực tiếp từ cơ sở dữ liệu của bạn (có thể bao gồm các định nghĩa, công thức) hoặc đoạn nội dung liên quan. Lưu ý phần trích dẫn bằng tiếng anh thì bỏ trong ngoặc kép đóng lại và bên cạnh đó ghi thêm 1 phần bản dịch của phần trích dẫn đó ngay tiếp theotheo"
                        "Nếu không có kiến thức trong cơ sở dữ liệu, nhấn mạnh rằng 'Dù kiến thức này không thuộc cơ sở dữ liệu của tôi, tôi vẫn có thể hỗ trợ bạn với đầy đủ thông tin.' "
                        "   - Phần 2: Mở rộng giải thích, diễn dài và chi tiết, sử dụng ngôn ngữ dễ hiểu để trình bày nội dung trong phần 1, có thể kèm thêm ví dụ thực tế hoặc bài toán mẫu. "
                        "Nếu thông tin không có trong phần 1, sẽ tìm kiếm và hỗ trợ bằng các nguồn thông tin đáng tin cậy từ bên ngoài. "
                        "2. Nêu rõ kiến thức đó thuộc **topic** nào (trong 31 chủ đề sau: Differential calculus (rates of change), Integral calculus (areas under curves), Fundamental Theorem of Calculus, Definitions and properties (domain, range), Methods of representing functions (tables, equations, graphs), Combining and transforming functions, Special types like polynomial, exponential, logarithmic, and trigonometric functions, Sum, difference, double-angle, and half-angle formulas, Pythagorean identities and inverse trigonometric functions, Special values and graph properties of trigonometric functions, Formal definitions (ε-δ definition), Types of limits (one-sided, infinite), Continuity and types of discontinuities, Limit laws and frequently encountered limits, Definition and interpretation (slope of tangent, instantaneous rate of change), Rules for differentiation (product, quotient, chain rules), Derivatives of common functions, including trigonometric, inverse trigonometric, and logarithmic functions, Implicit differentiation and applications, Notations and higher-order derivatives, Tangent line approximations, Motion analysis (displacement, velocity, acceleration), Maxima and minima, critical points, Second derivative test and points of inflection, Intermediate Value Theorem, Rolle’s Theorem, Mean Value Theorem, L'Hôpital's Rule for evaluating indeterminate limits, Using derivatives to analyze and sketch graphs, Identifying asymptotes, intercepts, extrema, and concavity, Rules for exponents and logarithms, Mnemonics for differentiation rules). "
                        "3. Sử dụng ngôn ngữ thân thiện và dễ tiếp cận để khuyến khích người dùng học tập."
                    )
                },
                {"role": "user", "content": context}
            ],
            max_tokens=16384,
            temperature=0.7
        )

        # Lấy phản hồi từ API
        bot_reply = response.choices[0].message.content

        # Lưu lịch sử hội thoại vào Google Sheets  
        save_to_google_sheet(sheet, "user", user_message)
        save_to_google_sheet(sheet, "assistant", bot_reply)

        return jsonify({"reply": bot_reply})

    except Exception as e:
        print(f"Lỗi: {e}")
        return jsonify({"error": "Có lỗi xảy ra khi kết nối OpenAI"}), 500


if __name__ == '__main__':
    # Lấy cổng từ biến môi trường, nếu không có thì mặc định là 5000
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
