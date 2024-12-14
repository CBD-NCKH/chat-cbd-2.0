from flask import Flask, request, jsonify, render_template
from flask_cors import CORS  # Import Flask-CORS
from openai import OpenAI  # Import lớp OpenAI từ thư viện mới
import os
from dotenv import load_dotenv

# Load API Key từ file .env
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# Tạo một instance client OpenAI
client = OpenAI(api_key=api_key)

app = Flask(__name__, template_folder='templates')  # Đặt thư mục chứa HTML templates
CORS(app)  # Kích hoạt CORS cho toàn bộ ứng dụng Flask

# Route mặc định để render giao diện
@app.route('/')
def home():
    return render_template('index.html')  # Đảm bảo file index.html nằm trong thư mục 'templates/'

# API xử lý tin nhắn
@app.route('/api', methods=['POST'])
def api():
    try:
        data = request.json
        user_message = data.get("message")

        # Gửi yêu cầu tới OpenAI API qua instance client
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Bạn là một trợ lý ảo (tên là ChatCBD, do Châu Phúc Khang, Trần Hoàng Thiên Phúc và Nguyễn Hữu Thiện phát triển) "
                        "giảng dạy kiến thức dễ hiểu, chuyên hỗ trợ các câu hỏi về kiến thức từ chương trình giáo dục phổ thông của Bộ Giáo dục và Đào tạo Việt Nam. "
                        "(Có thể dùng cả tiếng Anh và tiếng Việt) "
                        "Khi trả lời: "
                        "1. Giải thích dễ hiểu, chia nhỏ từng bước. "
                        "2. Luôn đưa ra ví dụ thực tế liên quan đến nội dung. "
                        "3. Nhắc rõ kiến thức mà bạn giải thích nằm trong chương trình lớp mấy ngày đầu câu trả lời. "
                        "- Nếu kiến thức nằm trong sách giáo khoa: đề cập rõ và cung cấp thêm thông tin liên quan. "
                        "- Nếu kiến thức không thuộc sách giáo khoa: nhấn mạnh rằng \"Dù kiến thức này không thuộc sách giáo khoa, tôi vẫn có thể hỗ trợ bạn đầy đủ thông tin\". "
                        "4. Sử dụng ngôn ngữ thân thiện và dễ tiếp cận."
                    )
                },
                {"role": "user", "content": user_message}
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
