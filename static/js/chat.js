const chatMessages = document.getElementById('chat-messages');
const chatInput = document.getElementById('chat-input');
const sendBtn = document.getElementById('send-btn');

if (sendBtn) sendBtn.addEventListener('click', sendMessage);
if (chatInput) chatInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') sendMessage(); });

async function sendMessage() {
    const mensaje = chatInput.value.trim();
    if (!mensaje) return;
    addMessage(mensaje, 'user');
    chatInput.value = '';
    const typing = showTyping();
    try {
        const res = await fetch('/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ mensaje }) });
        const data = await res.json();
        typing.remove();
        addMessage(data.respuesta, 'bot');
    } catch { typing.remove(); addMessage('❌ Error de conexión. Intentá de nuevo.', 'bot'); }
}

function addMessage(text, type) {
    const div = document.createElement('div');
    div.className = `message ${type}`;
    const avatar = type === 'bot' ? '🤖' : '👤';
    const formatted = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>').replace(/\n/g, '<br>');
    div.innerHTML = `<div class="message-avatar">${avatar}</div><div class="message-content"><p>${formatted}</p></div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function showTyping() {
    const div = document.createElement('div');
    div.className = 'message bot';
    div.innerHTML = `<div class="message-avatar">🤖</div><div class="message-content"><div class="typing-indicator"><span></span><span></span><span></span></div></div>`;
    chatMessages.appendChild(div);
    chatMessages.scrollTop = chatMessages.scrollHeight;
    return div;
}