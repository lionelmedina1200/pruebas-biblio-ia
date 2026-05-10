// ══════════════════════════════════════════════════════════
// auth.js — sesión, avatar, historial de chat
// ══════════════════════════════════════════════════════════

let _usuario = null;
let _sesionChatId = null;

function newSesionId() {
    return 'chat_' + Date.now() + '_' + Math.random().toString(36).slice(2,7);
}

// ─── Avatar HTML ─────────────────────────────────────────────
function getAvatarHTML(usuario, size) {
    size = size || 36;
    if (!usuario) return anonSVG(size);
    if (usuario.picture) {
        return '<img src="' + usuario.picture + '" width="' + size + '" height="' + size + '" style="border-radius:50%;object-fit:cover;" alt="">';
    }
    var idx    = Number(usuario.avatar_id) || 1;
    var colors = ['#6366f1','#0ea5e9','#10b981','#f59e0b','#ef4444','#ec4899','#8b5cf6','#14b8a6'];
    var color  = colors[(idx - 1) % colors.length] || '#6366f1';
    var letter = (usuario.nombre || usuario.username || 'U')[0].toUpperCase();
    return colorSVG(color, letter, size);
}

function anonSVG(s) {
    return '<svg viewBox="0 0 100 100" width="'+s+'" height="'+s+'"><circle cx="50" cy="35" r="22" fill="#94a3b8"/><ellipse cx="50" cy="85" rx="35" ry="25" fill="#94a3b8"/><circle cx="50" cy="50" r="48" fill="none" stroke="#c0392b" stroke-width="4"/></svg>';
}

function colorSVG(color, letter, s) {
    return '<svg viewBox="0 0 100 100" width="'+s+'" height="'+s+'"><circle cx="50" cy="50" r="50" fill="'+color+'"/><text x="50" y="64" font-size="44" text-anchor="middle" fill="#fff" font-family="sans-serif" font-weight="700">'+letter+'</text></svg>';
}

// ─── Menú logueado ────────────────────────────────────────────
function buildUserMenu(usuario) {
    var userMenu = document.getElementById('user-menu');
    if (!userMenu) return;

    userMenu.innerHTML =
        '<div class="avatar-wrapper" id="avatar-btn" title="Mi cuenta">' +
            '<div class="avatar-circle">' + getAvatarHTML(usuario) + '</div>' +
        '</div>' +
        '<div class="dropdown-menu" id="dropdown-menu">' +
            '<div class="dropdown-header">' +
                '<div class="dh-avatar">' + getAvatarHTML(usuario, 44) + '</div>' +
                '<div>' +
                    '<div class="dh-name">' + (usuario.nombre || usuario.username) + '</div>' +
                    '<div class="dh-email">' + (usuario.email || '') + '</div>' +
                '</div>' +
            '</div>' +
            '<hr class="dropdown-hr">' +
            '<button class="dropdown-item" id="btn-nuevo-chat">💬 Nuevo chat</button>' +
            '<div class="dropdown-section-label">Chats recientes</div>' +
            '<div id="historial-list" class="historial-list"><span class="hist-loading">Cargando...</span></div>' +
            '<hr class="dropdown-hr">' +
            (!usuario.picture ? '<button class="dropdown-item" id="btn-cambiar-avatar">🎨 Cambiar avatar</button>' : '') +
            '<button class="dropdown-item danger" id="btn-logout">🚪 Cerrar sesión</button>' +
        '</div>';

    document.getElementById('avatar-btn').onclick = function(e) {
        e.stopPropagation();
        var dd = document.getElementById('dropdown-menu');
        dd.classList.toggle('open');
        if (dd.classList.contains('open')) loadHistorial();
    };

    document.addEventListener('click', function() {
        var dd = document.getElementById('dropdown-menu');
        if (dd) dd.classList.remove('open');
    });

    document.getElementById('btn-nuevo-chat').addEventListener('click', function() {
        _sesionChatId = newSesionId();
        clearChat();
        document.getElementById('dropdown-menu').classList.remove('open');
    });

    document.getElementById('btn-logout').addEventListener('click', async function() {
        await fetch('/api/logout', { method: 'POST' });
        clearChat();
        window.location.href = '/';
    });

    var btnAvatar = document.getElementById('btn-cambiar-avatar');
    if (btnAvatar) {
        btnAvatar.addEventListener('click', function() {
            document.getElementById('dropdown-menu').classList.remove('open');
            abrirSelectorAvatar(usuario);
        });
    }

    loadHistorial();
}

// ─── Historial de chats ───────────────────────────────────────
async function loadHistorial() {
    var cont = document.getElementById('historial-list');
    if (!cont) return;
    try {
        var res  = await fetch('/api/chat/historial');
        var data = await res.json();
        if (!data.length) {
            cont.innerHTML = '<span class="hist-empty">Sin chats anteriores</span>';
            return;
        }
        cont.innerHTML = data.slice(0,6).map(function(s) {
            var txt = (s.primer_msg || 'Chat').slice(0,38);
            return '<button class="hist-item" data-sid="'+s.sesion_id+'">' +
                   '<span class="hist-icon">💬</span>' +
                   '<span class="hist-text">'+txt+'…</span></button>';
        }).join('');
        cont.querySelectorAll('.hist-item').forEach(function(btn) {
            btn.onclick = function() { cargarSesionChat(btn.dataset.sid); };
        });
    } catch(e) {
        cont.innerHTML = '<span class="hist-empty">—</span>';
    }
}

async function cargarSesionChat(sesionId) {
    _sesionChatId = sesionId;
    var dd = document.getElementById('dropdown-menu');
    if (dd) dd.classList.remove('open');
    var res  = await fetch('/api/chat/historial/' + sesionId);
    var msgs = await res.json();
    var cont = document.getElementById('chat-messages');
    if (!cont) return;
    cont.innerHTML = '';
    msgs.forEach(function(m) {
        var div = document.createElement('div');
        div.className = 'message ' + (m.rol === 'user' ? 'user' : 'bot');
        var avatarHTML = m.rol === 'user' ? getAvatarHTML(_usuario, 32) : '🤖';
        var txt = m.mensaje.replace(/</g,'&lt;').replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>');
        div.innerHTML = '<div class="message-avatar">'+avatarHTML+'</div><div class="message-content"><p>'+txt+'</p></div>';
        cont.appendChild(div);
    });
    cont.scrollTop = cont.scrollHeight;
}

// ─── Selector de avatar ───────────────────────────────────────
function abrirSelectorAvatar(usuario) {
    var modal = document.getElementById('modal-avatar');
    if (!modal) {
        modal = document.createElement('div');
        modal.id = 'modal-avatar';
        modal.className = 'modal';
        modal.style.display = 'none';
        document.body.appendChild(modal);
    }
    var colors = ['#6366f1','#0ea5e9','#10b981','#f59e0b','#ef4444','#ec4899','#8b5cf6','#14b8a6'];
    var letter = (usuario.nombre || usuario.username || 'U')[0].toUpperCase();
    var currentIdx = Number(usuario.avatar_id) || 1;
    var opts = colors.map(function(color, i) {
        var sel = (currentIdx - 1 === i) ? ' selected' : '';
        return '<button class="avatar-opt'+sel+'" data-idx="'+(i+1)+'" style="background:'+color+';border:3px solid '+(currentIdx-1===i?'#fff':'transparent')+';">' +
               '<svg viewBox="0 0 100 100" width="52" height="52"><circle cx="50" cy="50" r="50" fill="'+color+'"/><text x="50" y="64" font-size="44" text-anchor="middle" fill="#fff" font-family="sans-serif" font-weight="700">'+letter+'</text></svg>' +
               '</button>';
    }).join('');
    modal.innerHTML =
        '<div class="modal-content" style="max-width:380px;text-align:center;">' +
            '<span class="close-modal" id="close-avatar">&times;</span>' +
            '<h3 style="color:var(--azul-claro);margin-bottom:1.2rem;">🎨 Elegí tu avatar</h3>' +
            '<div class="avatar-grid">' + opts + '</div>' +
            '<p style="color:var(--text-muted);font-size:0.8rem;margin-top:1rem;">Tocá uno para elegirlo</p>' +
        '</div>';

    modal.style.display = 'flex';

    document.getElementById('close-avatar').onclick = function() { modal.style.display='none'; };

    modal.querySelectorAll('.avatar-opt').forEach(function(btn) {
        btn.onclick = async function() {
            var idx = Number(btn.dataset.idx);
            await fetch('/api/avatar', {
                method:'PUT', headers:{'Content-Type':'application/json'},
                body: JSON.stringify({ avatar_id: idx })
            });
            _usuario.avatar_id = idx;
            modal.style.display = 'none';
            buildUserMenu(_usuario);
        };
    });
}

// ─── Menú guest (sin login) ───────────────────────────────────
function buildGuestMenu() {
    var userMenu = document.getElementById('user-menu');
    if (!userMenu) return;
    userMenu.innerHTML = '<div class="avatar-wrapper" id="avatar-btn" title="Iniciar sesión"><div class="avatar-circle">'+anonSVG(36)+'</div></div>';
    document.getElementById('avatar-btn').onclick = function() {
        var m = document.getElementById('login-modal');
        if (m) { m.style.display='flex'; }
    };
}

// ─── Nav según rol ────────────────────────────────────────────
function updateNav(usuario) {
    var ids = ['nav-dashboard','nav-registro','nav-libros','nav-catalogo','nav-resenas'];
    ids.forEach(function(id) {
        var el = document.getElementById(id);
        if (el) el.style.display = 'none';
    });
    if (!usuario) return;
    var show = function(id) { var el=document.getElementById(id); if(el) el.style.display='flex'; };
    show('nav-resenas');
    if (usuario.rol === 'bibliotecario') {
        show('nav-dashboard'); show('nav-registro'); show('nav-libros');
    } else if (usuario.rol === 'admin') {
        if (!window.location.pathname.startsWith('/logs')) window.location.href='/logs';
    } else {
        show('nav-catalogo');
        show('nav-prestamos');
    }
}

// ─── clearChat ────────────────────────────────────────────────
function clearChat() {
    var cont = document.getElementById('chat-messages');
    if (!cont) return;
    _sesionChatId = newSesionId();
    cont.innerHTML =
        '<div class="message bot">' +
            '<div class="message-avatar">🤖</div>' +
            '<div class="message-content"><p>¡Hola! 👋 Soy el asistente de la biblioteca. ¿En qué libro te puedo ayudar hoy?</p></div>' +
        '</div>';
}

// ─── Exponer helpers globales para chat.js ────────────────────
window.guardarMensajeChat = async function(rol, mensaje) {
    if (!_usuario || !_sesionChatId) return;
    try {
        await fetch('/api/chat/guardar', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ sesion_id: _sesionChatId, rol: rol, mensaje: mensaje })
        });
    } catch(e) {}
};

window.isChatUnlocked = function() { return !!_usuario; };
window.getAvatarHTML  = getAvatarHTML;
window.getCurrentUser = function() { return _usuario; };

// ─── Login form ───────────────────────────────────────────────
function bindLoginForm() {
    var loginForm  = document.getElementById('login-form');
    var loginError = document.getElementById('login-error');
    var loginModal = document.getElementById('login-modal');
    var closeModal = document.getElementById('close-login');

    if (closeModal) closeModal.onclick = function() { if(loginModal) loginModal.style.display='none'; };
    window.addEventListener('click', function(e) {
        if (e.target === loginModal) loginModal.style.display='none';
    });
    if (!loginForm) return;

    loginForm.onsubmit = async function(e) {
        e.preventDefault();
        var username = document.getElementById('login-username').value.trim();
        var password = document.getElementById('login-password').value;
        try {
            var res  = await fetch('/api/login', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({username, password}) });
            var data = await res.json();
            if (res.ok) {
                if (loginModal) loginModal.style.display='none';
                _usuario      = data.usuario;
                _sesionChatId = newSesionId();
                buildUserMenu(_usuario);
                updateNav(_usuario);
                clearChat();
                if (loginError) loginError.style.display='none';
                if (window._onUserLoaded) window._onUserLoaded(_usuario);
            } else {
                if (loginError) { loginError.textContent=data.error; loginError.style.display='block'; }
            }
        } catch(err) {
            if (loginError) { loginError.textContent='Error de conexión'; loginError.style.display='block'; }
        }
    };
}

// ─── Init ─────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async function() {
    _sesionChatId = newSesionId();
    bindLoginForm();
    try {
        var res  = await fetch('/api/session');
        var data = await res.json();
        if (data.logged_in && data.usuario) {
            _usuario = data.usuario;
            buildUserMenu(_usuario);
            updateNav(_usuario);
            clearChat();
            updateChatLockBanner(true);
            if (window._onUserLoaded) window._onUserLoaded(_usuario);
        } else {
            buildGuestMenu();
            updateNav(null);
            clearChat();
            updateChatLockBanner(false);
        }
    } catch(e) {
        buildGuestMenu();
        updateNav(null);
        updateChatLockBanner(false);
    }
});

// Mostrar/ocultar banner de "necesitás iniciar sesión" en el chat
function updateChatLockBanner(loggedIn) {
    var banner = document.getElementById('chat-lock-banner');
    var input  = document.getElementById('chat-input');
    if (!banner) return;
    if (loggedIn) {
        banner.style.display = 'none';
        if (input) { input.disabled = false; input.placeholder = 'Ej: ¿Qué libros de programación tenés?'; }
    } else {
        banner.style.display = 'none';
        if (input) { input.disabled = false; input.placeholder = 'Escribí tu pregunta...'; }
    }
}

// Patch init para controlar el banner
var _origDomLoaded = document.addEventListener;
document.addEventListener('DOMContentLoaded', function() {
    // Este listener corre después del init principal
    setTimeout(function() {
        updateChatLockBanner(!!_usuario);
    }, 600);
});

// Exponer para que el init principal lo llame
window._updateChatLockBanner = updateChatLockBanner;