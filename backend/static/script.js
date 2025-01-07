const sendButton = document.getElementById('send-button');
const userInput = document.getElementById('user-input');
const messagesDiv = document.getElementById('messages');
const themeToggleButton = document.getElementById('theme-toggle-button');
const body = document.body;

// Hàm thêm tin nhắn
function addMessage(content, sender, isMarkdown = false, typingSpeed = 100) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);

    if (isMarkdown) {
        content = marked.parse(content);
    }

    messageDiv.textContent = content;
    messagesDiv.appendChild(messageDiv);

    // Cuộn xuống cuối
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Hàm gửi tin nhắn
function sendMessage() {
    const userMessage = userInput.value.trim();
    if (!userMessage) return; // Nếu input rỗng, không làm gì

    addMessage(userMessage, 'user'); // Thêm tin nhắn người dùng
    userInput.value = ''; // Xóa nội dung trong ô input

    // Phản hồi từ bot (thay thế bằng API nếu cần)
    addMessage('Xin chào! Đây là phản hồi mẫu.', 'bot');
}

// Xử lý sự kiện click
sendButton.addEventListener('click', sendMessage);

// Xử lý sự kiện nhấn Enter
userInput.addEventListener('keypress', (event) => {
    if (event.key === 'Enter') {
        sendMessage();
    }
});

// Chuyển đổi chế độ sáng/tối
themeToggleButton.addEventListener('click', () => {
    body.classList.toggle('light-mode');
    themeToggleButton.textContent = body.classList.contains('light-mode') ? '🌞' : '🌙';
});
