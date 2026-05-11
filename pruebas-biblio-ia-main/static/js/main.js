document.addEventListener('DOMContentLoaded', () => {
    const modal = document.getElementById('welcome-modal');
    const startBtn = document.getElementById('start-btn');
    if (modal) {
        if (sessionStorage.getItem('visited')) {
            modal.style.display = 'none';
        }
        if (startBtn) {
            startBtn.addEventListener('click', () => {
                modal.style.opacity = '0';
                setTimeout(() => { modal.style.display = 'none'; document.getElementById('chat-input')?.focus(); }, 300);
                sessionStorage.setItem('visited', 'true');
            });
        }
    }
});

function quickSearch(term) {
    const input = document.getElementById('chat-input');
    if (input) { input.value = term; input.focus(); sendMessage(); }
}