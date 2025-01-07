const sendButton = document.getElementById('send-button');
const userInput = document.getElementById('user-input');
const messagesDiv = document.getElementById('messages');
const themeToggleButton = document.getElementById('theme-toggle-button');
const body = document.body;

// Hàm thêm tin nhắn vào giao diện
function addMessage(content, sender, isMarkdown = false, typingSpeed = 100) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);

    if (isMarkdown) {
        content = marked.parse(content);
    }

    if (sender === 'bot') {
        const tempContainer = document.createElement('div');
        tempContainer.innerHTML = content;
        const nodes = Array.from(tempContainer.childNodes);

        let currentNodeIndex = 0;
        let currentCharIndex = 0;

        const typeEffect = setInterval(() => {
            if (currentNodeIndex < nodes.length) {
                const currentNode = nodes[currentNodeIndex];
                if (currentNode.nodeType === Node.TEXT_NODE) {
                    if (currentCharIndex < currentNode.textContent.length) {
                        messageDiv.appendChild(document.createTextNode(currentNode.textContent[currentCharIndex]));
                        currentCharIndex++;
                    } else {
                        currentCharIndex = 0;
                        currentNodeIndex++;
                    }
                } else if (currentNode.nodeType === Node.ELEMENT_NODE) {
                    messageDiv.appendChild(currentNode.cloneNode(true));
                    currentNodeIndex++;
                }
            } else {
                clearInterval(typeEffect);
            }
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        }, typingSpeed);
    } else {
        messageDiv.innerHTML = content;
        messagesDiv.appendChild(messageDiv);
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    }

    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Hàm hiển thị hiệu ứng "đang gõ"
function showTypingIndicator() {
    const typingDiv = document.createElement('div');
    typingDiv.classList.add('message', 'bot', 'typing');
    typingDiv.innerHTML = `
        <div class="typing-indicator">
            <span></span>
            <span></span>
            <span></span>
        </div>
    `;
    messagesDiv.appendChild(typingDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Hàm xóa hiệu ứng "đang gõ"
function removeTypingIndicator() {
    const typingDiv = document.querySelector('.typing');
    if (typingDiv) {
        typingDiv.remove();
    }
}

// Hàm gửi yêu cầu tới API
async function sendMessage() {
    const userMessage = userInput.value.trim();
    if (!userMessage) return;

    addMessage(userMessage, 'user');
    userInput.value = '';

    showTypingIndicator(); // Hiển thị hiệu ứng "đang gõ"

    try {
        const response = await fetch('https://chat-cbd-2-0.onrender.com/api', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: userMessage }),
        });

        const data = await response.json();

        removeTypingIndicator(); // Xóa hiệu ứng "đang gõ"

        if (data.reply) {
            addMessage(data.reply, 'bot', true, 30); // Tốc độ gõ từng ký tự
        } else {
            addMessage('Không nhận được phản hồi từ server.', 'bot');
        }
    } catch (error) {
        removeTypingIndicator(); // Xóa hiệu ứng "đang gõ"
        addMessage('Không thể kết nối tới server.', 'bot');
    }
}

// Xử lý sự kiện click vào nút "Gửi"
sendButton.addEventListener('click', sendMessage);

// Xử lý sự kiện nhấn phím Enter
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
