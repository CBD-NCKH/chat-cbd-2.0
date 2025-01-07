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
    }

    messagesDiv.appendChild(messageDiv);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// Chuyển chế độ sáng/tối
themeToggleButton.addEventListener('click', () => {
    body.classList.toggle('light-mode');
    themeToggleButton.textContent = body.classList.contains('light-mode') ? '🌞' : '🌙';
});
