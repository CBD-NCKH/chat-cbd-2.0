const sendButton = document.getElementById('send-button');
const userInput = document.getElementById('user-input');
const messagesDiv = document.getElementById('messages');

function addMessage(content, sender, isMarkdown = false) {
    const messageDiv = document.createElement('div');
    messageDiv.classList.add('message', sender);
    if (isMarkdown) {
        content = marked.parse(content);
    }
    messageDiv.innerHTML = content;
    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

async function sendMessage() {
    const userMessage = userInput.value.trim();
    if (!userMessage) return;

    addMessage(userMessage, 'user');
    userInput.value = '';

    try {
        const response = await fetch('https://chat-cbd.onrender.com/api', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: userMessage }),
        });

        const data = await response.json();
        addMessage(data.reply || 'Có l?i x?y ra.', 'bot', true);
    } catch (error) {
        addMessage('Không th? k?t n?i t?i server.', 'bot');
    }
}

sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (event) => {
    if (event.key === 'Enter') {
        sendMessage();
    }
});
