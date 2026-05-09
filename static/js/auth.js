document.addEventListener('DOMContentLoaded', () => {
    const userMenu = document.getElementById('user-menu');
    const navDashboard = document.getElementById('nav-dashboard');
    const navRegistro = document.getElementById('nav-registro');
    const navLibros = document.getElementById('nav-libros');
    const loginModal = document.getElementById('login-modal');
    const loginForm = document.getElementById('login-form');
    const loginError = document.getElementById('login-error');
    const closeModal = document.getElementById('close-login');
    const navCatalogo = document.getElementById('nav-catalogo');

    // Función para vaciar el chat y dejar mensaje inicial
    function clearChat() {
        const chatMessages = document.getElementById('chat-messages');
        if (chatMessages) {
            chatMessages.innerHTML = `
                <div class="message bot">
                    <div class="message-avatar">🤖</div>
                    <div class="message-content"><p>¡Hola! 👋 Soy el asistente de la biblioteca. ¿En qué libro te puedo ayudar hoy?</p></div>
                </div>`;
        }
    }

function updateUI(usuario) {
    if (!userMenu) return;

    if (!usuario) {
        userMenu.innerHTML = `
            <div class="avatar" id="avatar-login" title="Iniciar sesión">
                <svg viewBox="0 0 100 100" width="40" height="40">
                    <circle cx="50" cy="35" r="22" fill="#fff"/>
                    <ellipse cx="50" cy="85" rx="35" ry="25" fill="#fff"/>
                    <circle cx="50" cy="50" r="48" fill="none" stroke="#c0392b" stroke-width="4"/>
                </svg>
            </div>`;
        document.getElementById('avatar-login').onclick = () => { if(loginModal) loginModal.style.display = 'block'; };
        if(navDashboard) navDashboard.style.display = 'none';
        if(navRegistro) navRegistro.style.display = 'none';
        if(navLibros) navLibros.style.display = 'none';
        if(navCatalogo) navCatalogo.style.display = 'none';
    } else {
        userMenu.innerHTML = `
            <div class="user-info">
                <span>Hola, ${usuario.nombre}</span>
                <button id="btn-logout" class="btn-logout">Salir</button>
            </div>`;
        document.getElementById('btn-logout').onclick = async () => {
            await fetch('/api/logout', { method: 'POST' });
            alert('✅ Se cerró tu sesión correctamente.');
            clearChat();
            window.location.href = '/';
        };

        if (usuario.rol === 'bibliotecario') {
            if(navDashboard) navDashboard.style.display = 'block';
            if(navRegistro) navRegistro.style.display = 'block';
            if(navLibros) navLibros.style.display = 'block';
            if(navCatalogo) navCatalogo.style.display = 'none';
        } else if (usuario.rol === 'admin') {
            if(navDashboard) navDashboard.style.display = 'none';
            if(navRegistro) navRegistro.style.display = 'none';
            if(navLibros) navLibros.style.display = 'none';
            if(navCatalogo) navCatalogo.style.display = 'none';
            // Si el admin está en una página que no es /logs, redirigirlo
            if (!window.location.pathname.startsWith('/logs')) {
                window.location.href = '/logs';
            }
        } else {
            if(navCatalogo) navCatalogo.style.display = 'block';
        }
    }
}

    // Verificar sesión al cargar
    fetch('/api/session')
        .then(res => res.json())
        .then(data => {
            updateUI(data.logged_in ? data.usuario : null);
            clearChat(); // Siempre limpiar chat al entrar a la página
        })
        .catch(() => { updateUI(null); clearChat(); });

    // Modal handlers
    if (closeModal) closeModal.onclick = () => loginModal.style.display = 'none';
    window.onclick = (e) => { if (e.target == loginModal) loginModal.style.display = 'none'; };

    // Login handler
    if (loginForm) {
        loginForm.onsubmit = async (e) => {
            e.preventDefault();
            const username = document.getElementById('login-username').value.trim();
            const password = document.getElementById('login-password').value;

            try {
                const res = await fetch('/api/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                const data = await res.json();
                if (res.ok) {
                    loginModal.style.display = 'none';
                    updateUI(data.usuario);
                    clearChat(); // Vaciar chat al iniciar sesión
                    loginError.style.display = 'none';
                } else {
                    loginError.textContent = data.error;
                    loginError.style.display = 'block';
                }
            } catch {
                loginError.textContent = 'Error de conexión';
                loginError.style.display = 'block';
            }
        };
    }
});