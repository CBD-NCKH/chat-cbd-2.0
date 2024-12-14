from flask import Flask, request, jsonify, render_template
from flask_cors import CORS  # Import Flask-CORS
from openai import OpenAI  # Import l?p OpenAI t? thý vi?n m?i
import os
from dotenv import load_dotenv

# Load API Key t? file .env
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

# T?o m?t instance client OpenAI
client = OpenAI(api_key=api_key)

app = Flask(__name__, template_folder='templates')  # Ð?t thý m?c ch?a HTML templates
CORS(app)  # Kích ho?t CORS cho toàn b? ?ng d?ng Flask

# Route m?c ð?nh ð? render giao di?n
@app.route('/')
def home():
    return render_template('index.html')  # Ð?m b?o file index.html n?m trong thý m?c 'templates/'

# API x? l? tin nh?n
@app.route('/api', methods=['POST'])
def api():
    try:
        data = request.json
        user_message = data.get("message")

        # G?i yêu c?u t?i OpenAI API qua instance client
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": (
                        "B?n là m?t tr? l? ?o (tên là ChatCBD, do Châu Phúc Khang, Tr?n Hoàng Thiên Phúc và Nguy?n H?u Thi?n phát tri?n) gi?ng d?y ki?n th?c d? hi?u, chuyên h? tr? các câu h?i v? ki?n th?c t? chýõng tr?nh giáo d?c ph? thông c?a B? Giáo d?c và Ðào t?o Vi?t Nam. (Có th? dùng c? ti?ng anh và ti?ng vi?t) "
                        "Khi tr? l?i: "
                        "1. Gi?i thích d? hi?u, chia nh? t?ng bý?c. "
                        "2. Luôn ðýa ra ví d? th?c t? liên quan ð?n n?i dung. "
                        "3. Nh?c r? ki?n th?c mà b?n gi?i thích n?m trong chýõng tr?nh l?p m?y ngày ð?u câu tr? l?i. "
                        "- N?u ki?n th?c n?m trong sách giáo khoa: ð? c?p r? và cung c?p thêm thông tin liên quan. "
                        "- N?u ki?n th?c không thu?c sách giáo khoa: nh?n m?nh r?ng \"Dù ki?n th?c này không thu?c sách giáo khoa, tôi v?n có th? h? tr? b?n ð?y ð? thông tin\". "
                        "4. S? d?ng ngôn ng? thân thi?n và d? ti?p c?n."
                    )
                },
                {"role": "user", "content": user_message}
            ],
            max_tokens=16384,
            temperature=0.7
        )

        # L?y ph?n h?i t? API
        bot_reply = response.choices[0].message.content
        return jsonify({"reply": bot_reply})

    except Exception as e:
        print(f"L?i: {e}")
        return jsonify({"error": "Có l?i x?y ra khi k?t n?i OpenAI"}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
