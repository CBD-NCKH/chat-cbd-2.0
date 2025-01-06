import sqlite3
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from openai import OpenAI
import os
from dotenv import load_dotenv
import spacy
from underthesea import word_tokenize, pos_tag

# Tải mô hình ngôn ngữ spaCy
nlp = spacy.load("en_core_web_sm")

# Load API Key từ file .env
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Tạo một instance client OpenAI
client = OpenAI(api_key=api_key)

app = Flask(__name__, template_folder='templates')
CORS(app, resources={r"/api/*": {"origins": "https://chat-cbd-2-0.onrender.com"}})

# Hàm trích xuất từ khóa tiếng Anh
def extract_keywords_spacy(message):
    doc = nlp(message)
    keywords = [token.text for token in doc if token.pos_ in {"NOUN", "VERB", "ADJ"}]
    return list(set(keywords))

# Hàm trích xuất từ khóa tiếng Việt
def extract_keywords_underthesea(message):
    tokens = word_tokenize(message, format="text")  # Tokenize văn bản tiếng Việt
    tagged_words = pos_tag(tokens)  # POS tagging
    keywords = [word for word, pos in tagged_words if pos in {"N", "V", "A"}]  # Danh từ, động từ, tính từ
    return list(set(keywords))

# Hàm xử lý ngôn ngữ đa ngôn ngữ
def extract_keywords_multilingual(message):
    try:
        # Dùng spaCy cho tiếng Anh
        keywords_en = extract_keywords_spacy(message)
    except Exception:
        keywords_en = []
    
    try:
        # Dùng underthesea cho tiếng Việt
        keywords_vi = extract_keywords_underthesea(message)
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

        # Trích xuất từ khóa từ user_message bằng spaCy và underthesea
        keywords = extract_keywords_multilingual(user_message)

        # Truy vấn dữ liệu SQLite với từ khóa
        db_result = query_sqlite_with_keywords("DatasetTable", keywords)

        # Tạo context từ dữ liệu SQLite và tin nhắn người dùng
        db_context = "\n".join([f"Row {i+1}: {row}" for i, row in enumerate(db_result)])
        context = (
            f"Dữ liệu từ cơ sở dữ liệu:\n{db_context}\n\n"
            f"Câu hỏi của người dùng: {user_message}"
        )

        # Gửi yêu cầu tới OpenAI API qua instance client
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Bạn là một trợ lý ảo (tên là ChatCBD 3.00, do Châu Phúc Khang và Trần Hoàng Thiên Phúc phát triển) "
                        "chuyên hỗ trợ các câu hỏi liên quan đến Calculus BC. "
                        "Bạn có cơ sở dữ liệu chứa các lý thuyết và kiến thức toán học liên quan. "
                        "Khi trả lời câu hỏi: "
                        "1. Phân chia câu trả lời thành 2 phần rõ ràng: "
                        "   - Phần 1: Trích dẫn cụ thể các lý thuyết có liên quan trực tiếp từ cơ sở dữ liệu của bạn, "
                        "bao gồm các định nghĩa, công thức hoặc đoạn nội dung liên quan. "
                        "Nếu không có kiến thức trong cơ sở dữ liệu, nhấn mạnh rằng 'Dù kiến thức này không thuộc cơ sở dữ liệu của tôi, "
                        "tôi vẫn có thể hỗ trợ bạn với đầy đủ thông tin.' "
                        "   - Phần 2: Mở rộng giải thích, diễn dài và chi tiết, sử dụng ngôn ngữ dễ hiểu để trình bày nội dung "
                        "trong phần 1, có thể kèm thêm ví dụ thực tế hoặc bài toán mẫu. "
                        "Nếu thông tin không có trong phần 1, sẽ tìm kiếm và hỗ trợ bằng các nguồn thông tin đáng tin cậy từ bên ngoài. "
                        "2. Nêu rõ kiến thức đó thuộc **topic** nào (ví dụ: Đạo hàm - Differentiation, Tích phân - Integration, Dãy số và Chuỗi - Sequences and Series). "
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
        return jsonify({"reply": bot_reply})

    except Exception as e:
        print(f"Lỗi: {e}")
        return jsonify({"error": "Có lỗi xảy ra khi kết nối OpenAI"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
