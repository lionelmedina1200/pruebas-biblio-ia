// ══════════════════════════════════════════════════════════
// auth.js — sesión, avatar, historial de chat
// ══════════════════════════════════════════════════════════

let _usuario = null;
let _sesionChatId = null;

function newSesionId() {
    return 'chat_' + Date.now() + '_' + Math.random().toString(36).slice(2,7);
}

// ─── Avatar HTML ──────────────────────────────────────────
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

// ─── Menú logueado ────────────────────────────────────────
function buildUserMenu(usuario) {
    var userMenu = document.getElementById('user-menu');
    if (!userMenu) return;

    var rolBadge = usuario.rol === 'bibliotecario' ? '<span style="font-size:0.7rem;background:rgba(59,130,246,0.2);color:#93c5fd;padding:2px 8px;border-radius:50px;font-weight:600;">Bibliotecario</span>'
                 : usuario.rol === 'admin'         ? '<span style="font-size:0.7rem;background:rgba(239,68,68,0.2);color:#fca5a5;padding:2px 8px;border-radius:50px;font-weight:600;">Admin</span>'
                 : '<span style="font-size:0.7rem;background:rgba(34,197,94,0.2);color:#4ade80;padding:2px 8px;border-radius:50px;font-weight:600;">Alumno</span>';

    // Opciones según rol
    var opcionesRol = '';
    if (usuario.rol === 'alumno' || (!usuario.rol || usuario.rol === 'alumno')) {
        opcionesRol += '<a href="/mis-prestamos" class="dropdown-item" id="btn-mis-prestamos">Mis préstamos</a>';
        opcionesRol += '<a href="/resenas" class="dropdown-item">Mis reseñas</a>';
        opcionesRol += '<a href="/catalogo" class="dropdown-item">Ver catálogo</a>';
    } else if (usuario.rol === 'bibliotecario') {
        opcionesRol += '<a href="/dashboard" class="dropdown-item">Dashboard</a>';
        opcionesRol += '<a href="/libros" class="dropdown-item">Gestión de libros</a>';
        opcionesRol += '<a href="/registro" class="dropdown-item">Registrar alumno</a>';
        opcionesRol += '<a href="/resenas" class="dropdown-item">Ver reseñas</a>';
    } else if (usuario.rol === 'admin') {
        opcionesRol += '<a href="/logs" class="dropdown-item">Logs del sistema</a>';
    }

    var chatSection = (usuario.rol !== 'admin') ?
        '<hr class="dropdown-hr">' +
        '<div class="dropdown-section-label">Chats</div>' +
        '<button class="dropdown-item" id="btn-nuevo-chat">Nuevo chat</button>' +
        '<div id="historial-list" class="historial-list"><span class="hist-loading">Cargando...</span></div>'
        : '';

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
                    '<div style="margin-top:4px;">' + rolBadge + '</div>' +
                '</div>' +
            '</div>' +
            '<hr class="dropdown-hr">' +
            opcionesRol +
            chatSection +
            '<hr class="dropdown-hr">' +
            (!usuario.picture ? '<button class="dropdown-item" id="btn-cambiar-avatar">Cambiar avatar</button>' : '') +
            '<button class="dropdown-item danger" id="btn-logout">Cerrar sesión</button>' +
        '</div>';

    document.getElementById('avatar-btn').onclick = function(e) {
        e.stopPropagation();
        var dd = document.getElementById('dropdown-menu');
        dd.classList.toggle('open');
        if (dd.classList.contains('open') && usuario.rol !== 'admin') loadHistorial();
    };

    document.addEventListener('click', function() {
        var dd = document.getElementById('dropdown-menu');
        if (dd) dd.classList.remove('open');
    });

    var btnNuevo = document.getElementById('btn-nuevo-chat');
    if (btnNuevo) {
        btnNuevo.addEventListener('click', function() {
            _sesionChatId = newSesionId();
            clearChat();
            document.getElementById('dropdown-menu').classList.remove('open');
        });
    }

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

    if (usuario.rol !== 'admin') loadHistorial();
}

// ─── Historial de chats con renombrar y eliminar ──────────
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
        cont.innerHTML = data.slice(0,8).map(function(s) {
            var nombre = s.nombre_chat || (s.primer_msg || 'Chat').slice(0,30);
            return '<div class="hist-row" data-sid="'+s.sesion_id+'">' +
                '<button class="hist-item" data-sid="'+s.sesion_id+'">' +
                    '<span class="hist-text">'+nombre+'</span>' +
                '</button>' +
                '<div class="hist-actions">' +
                    '<button class="hist-action-btn" title="Renombrar" onclick="renombrarChat(\''+s.sesion_id+'\',event)">✎</button>' +
                    '<button class="hist-action-btn danger" title="Eliminar" onclick="eliminarChat(\''+s.sesion_id+'\',event)">✕</button>' +
                '</div>' +
            '</div>';
        }).join('');
        cont.querySelectorAll('.hist-item').forEach(function(btn) {
            btn.onclick = function(e) {
                e.stopPropagation();
                cargarSesionChat(btn.dataset.sid);
            };
        });
    } catch(e) {
        cont.innerHTML = '<span class="hist-empty">—</span>';
    }
}

async function renombrarChat(sesionId, e) {
    e.stopPropagation();
    var nombre = prompt('Nombre del chat:');
    if (!nombre || !nombre.trim()) return;
    await fetch('/api/chat/renombrar', {
        method: 'PUT',
        headers: {'Content-Type':'application/json'},
        body: JSON.stringify({ sesion_id: sesionId, nombre: nombre.trim() })
    });
    loadHistorial();
}

async function eliminarChat(sesionId, e) {
    e.stopPropagation();
    if (!confirm('¿Eliminar este chat?')) return;
    await fetch('/api/chat/eliminar/' + sesionId, { method: 'DELETE' });
    if (_sesionChatId === sesionId) {
        _sesionChatId = newSesionId();
        clearChat();
    }
    loadHistorial();
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
        var avatarHTML = m.rol === 'user' ? getAvatarHTML(_usuario, 32) : '<svg viewBox="0 0 36 36" width="36" height="36"><circle cx="18" cy="18" r="18" fill="#1e3a5f"/><text x="18" y="23" font-size="16" text-anchor="middle" fill="#fff">IA</text></svg>';
        var txt = m.mensaje.replace(/</g,'&lt;').replace(/\*\*(.*?)\*\*/g,'<strong>$1</strong>').replace(/\n/g,'<br>');
        div.innerHTML = '<div class="message-avatar">'+avatarHTML+'</div><div class="message-content"><p>'+txt+'</p></div>';
        cont.appendChild(div);
    });
    cont.scrollTop = cont.scrollHeight;
}

// ─── Selector de avatar ───────────────────────────────────
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
            '<h3 style="color:var(--azul-claro);margin-bottom:1.2rem;">Elegí tu avatar</h3>' +
            '<div class="avatar-grid">' + opts + '</div>' +
            '<p style="color:var(--text-muted);font-size:0.8rem;margin-top:1rem;">Tocá uno para elegirlo</p>' +
        '</div>';
    modal.style.display = 'flex';
    document.getElementById('close-avatar').onclick = function() { modal.style.display='none'; };
    modal.querySelectorAll('.avatar-opt').forEach(function(btn) {
        btn.onclick = async function() {
            var idx = Number(btn.dataset.idx);
            await fetch('/api/avatar', { method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ avatar_id: idx }) });
            _usuario.avatar_id = idx;
            modal.style.display = 'none';
            buildUserMenu(_usuario);
        };
    });
}

// ─── Menú guest ───────────────────────────────────────────
function buildGuestMenu() {
    var userMenu = document.getElementById('user-menu');
    if (!userMenu) return;
    userMenu.innerHTML = '<div class="avatar-wrapper" id="avatar-btn" title="Iniciar sesión"><div class="avatar-circle">'+anonSVG(36)+'</div></div>';
    document.getElementById('avatar-btn').onclick = function() {
        var m = document.getElementById('login-modal');
        if (m) m.style.display='flex';
    };
}

// ─── Nav según rol ────────────────────────────────────────
function updateNav(usuario) {
    var ids = ['nav-dashboard','nav-registro','nav-libros','nav-catalogo','nav-resenas','nav-prestamos'];
    ids.forEach(function(id) { var el=document.getElementById(id); if(el) el.style.display='none'; });
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

// ─── clearChat ────────────────────────────────────────────
function clearChat() {
    var cont = document.getElementById('chat-messages');
    if (!cont) return;
    _sesionChatId = newSesionId();
    var iaAvatar = '<svg viewBox="0 0 36 36" width="36" height="36"><circle cx="18" cy="18" r="18" fill="#1e3a5f"/><text x="18" y="23" font-size="16" text-anchor="middle" fill="#fff">IA</text></svg>';
    cont.innerHTML =
        '<div class="message bot">' +
            '<div class="message-avatar">'+iaAvatar+'</div>' +
            '<div class="message-content"><p>Hola, soy el asistente de la biblioteca. ¿En qué libro te puedo ayudar hoy?</p></div>' +
        '</div>';
}

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

// ─── Login form ───────────────────────────────────────────
function bindLoginForm() {
    var loginForm  = document.getElementById('login-form');
    var loginError = document.getElementById('login-error');
    var loginModal = document.getElementById('login-modal');
    var closeModal = document.getElementById('close-login');
    if (closeModal) closeModal.onclick = function() { if(loginModal) loginModal.style.display='none'; };
    window.addEventListener('click', function(e) { if (e.target===loginModal) loginModal.style.display='none'; });
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
                _usuario = data.usuario; _sesionChatId = newSesionId();
                buildUserMenu(_usuario); updateNav(_usuario); clearChat();
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

// ─── Init ─────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async function() {
    _sesionChatId = newSesionId();
    bindLoginForm();
    try {
        var res  = await fetch('/api/session');
        var data = await res.json();
        if (data.logged_in && data.usuario) {
            _usuario = data.usuario;
            buildUserMenu(_usuario); updateNav(_usuario); clearChat();
            updateChatLockBanner(true);
            if (window._onUserLoaded) window._onUserLoaded(_usuario);
        } else {
            buildGuestMenu(); updateNav(null); clearChat(); updateChatLockBanner(false);
        }
    } catch(e) {
        buildGuestMenu(); updateNav(null); updateChatLockBanner(false);
    }
});

function updateChatLockBanner(loggedIn) {
    var banner = document.getElementById('chat-lock-banner');
    var input  = document.getElementById('chat-input');
    if (banner) banner.style.display = 'none';
    if (input) {
        input.disabled = false;
        input.placeholder = loggedIn ? 'Escribí tu consulta...' : 'Escribí tu pregunta...';
    }
}
window._updateChatLockBanner = updateChatLockBanner;