let currentPage = 1;
let perPage = 10;

async function loadLibros(page = 1) {
    currentPage = page;
    const busqueda = document.getElementById('admin-search')?.value || '';
    
    try {
        const res = await fetch(`/api/libros?page=${page}&per_page=${perPage}&busqueda=${encodeURIComponent(busqueda)}`);
        const data = await res.json();
        const tbody = document.getElementById('admin-tbody');
        
        tbody.innerHTML = data.libros.map(l => `
            <tr>
                <td>${l.id}</td>
                <td><strong>${l.titulo}</strong></td>
                <td>${l.autor}</td>
                <td>${l.editorial || '-'}</td>
                <td>
                    <div class="stock-control">
                        <input type="number" 
                            min="0" 
                            value="${ l.disponible }" 
                            class="stock-input"
                            data-libro-id="${ l.id }">
                        <button onclick="actualizarStock(${l.id})" class="btn-stock">
                            Actualizar
                        </button>
                    </div>
                </td>
                <td>
                    <span class="badge ${l.disponible > 0 ? 'disponible' : 'no-disponible'}">
                        ${l.disponible > 0 ? '✅ ' + l.disponible + ' en stock' : '❌ Sin stock'}
                    </span>
                </td>
                <td>
                    <div style="display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
                        <button class="btn-toggle" onclick="toggleDisp(${l.id}, ${l.disponible})">
                            ${l.disponible > 0 ? '➖ Marcar Prestado' : '➕ Marcar Devuelto'}
                        </button>
                        <button class="btn-eliminar-libro" onclick="eliminarLibro(${l.id}, this)">
                            🗑️ Eliminar
                        </button>
                    </div>
                </td>
            </tr>
        `).join('');
        
        // guardar titulos en data attribute para el botón eliminar
        data.libros.forEach(l => {
            const btn = document.querySelector(`.btn-eliminar-libro[onclick*="eliminarLibro(${l.id},"]`);
            if (btn) btn.setAttribute('data-titulo', l.titulo);
        });

        renderPagination(data.total_pages, page);
    } catch (err) {
        console.error("Error cargando libros:", err);
    }
}

function renderPagination(totalPages, current) {
    const container = document.getElementById('pagination');
    if (!container) return;
    
    let html = `<button class="page-btn" onclick="loadLibros(${current - 1})" ${current === 1 ? 'disabled' : ''}>◀ Ant</button>`;
    
    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= current - 1 && i <= current + 1)) {
            html += `<button class="page-btn ${i === current ? 'active' : ''}" onclick="loadLibros(${i})">${i}</button>`;
        } else if (i === current - 2 || i === current + 2) {
            html += `<span style="padding:8px">...</span>`;
        }
    }
    
    html += `<button class="page-btn" onclick="loadLibros(${current + 1})" ${current === totalPages ? 'disabled' : ''}>Sig ▶</button>`;
    container.innerHTML = html;
}

async function toggleDisp(id, actual) {
    const nuevoStock = actual > 0 ? actual - 1 : actual + 1;
    try {
        const res = await fetch(`/api/libros/${id}/stock`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cantidad: nuevoStock })
        });
        if (res.ok) {
            loadLibros(currentPage);
        } else {
            const data = await res.json();
            alert('Error: ' + (data.error || 'No se pudo actualizar el estado'));
        }
    } catch (err) {
        alert('Error de conexión al actualizar el estado');
    }
}

// ── Eliminar libro ───────────────────────────────────────────
async function eliminarLibro(id, btn) {
    const titulo = btn.getAttribute('data-titulo') || 'este libro';
    if (!confirm('¿Estás segura de que querés eliminar "' + titulo + '"?\nEsta acción no se puede deshacer.')) return;
    try {
        const res = await fetch('/api/libros/' + id, {
            method: 'DELETE',
            headers: { 'Content-Type': 'application/json' }
        });
        const data = await res.json();
        if (res.ok) {
            loadLibros(currentPage);
        } else {
            alert('Error: ' + (data.error || 'No se pudo eliminar el libro'));
        }
    } catch (err) {
        alert('Error de conexión al eliminar el libro');
    }
}

// ── Modal agregar libro ──────────────────────────────────────
let capitulosCount = 0;

function abrirModalAgregar() {
    document.getElementById('modal-agregar').classList.add('open');
    document.getElementById('nuevo-titulo').focus();
    document.getElementById('agregar-error').style.display = 'none';
    document.getElementById('agregar-ok').style.display = 'none';
}

function cerrarModalAgregar() {
    document.getElementById('modal-agregar').classList.remove('open');
    ['nuevo-titulo','nuevo-autor','nuevo-editorial'].forEach(id => {
        document.getElementById(id).value = '';
    });
    document.getElementById('nuevo-stock').value = '10';
    // Limpiar capítulos y resetear contador
    document.getElementById('capitulos-lista').innerHTML = '';
    document.getElementById('capitulos-vacio').style.display = 'block';
    capitulosCount = 0;
}

function agregarCapituloInput() {
    capitulosCount++;
    const lista = document.getElementById('capitulos-lista');
    document.getElementById('capitulos-vacio').style.display = 'none';
    const row = document.createElement('div');
    row.className = 'capitulo-row';
    row.id = 'cap-row-' + capitulosCount;
    const idx = capitulosCount;
    row.innerHTML =
        '<span class="cap-num">' + idx + '.</span>' +
        '<input type="text" id="cap-' + idx + '" class="form-input cap-input" placeholder="Ej: Introducción a la biología" onkeydown="capKeydown(event,' + idx + ')">' +
        '<button type="button" class="btn-del-cap" onclick="eliminarCapitulo(' + idx + ')" title="Eliminar">✕</button>';
    lista.appendChild(row);
    document.getElementById('cap-' + idx).focus();
}

function eliminarCapitulo(idx) {
    const row = document.getElementById('cap-row-' + idx);
    if (row) row.remove();
    // Si no quedan capítulos, mostrar hint y RESETEAR contador al 0
    if (document.querySelectorAll('.capitulo-row').length === 0) {
        document.getElementById('capitulos-vacio').style.display = 'block';
        capitulosCount = 0; // FIX: la próxima vez arranca desde 1
    }
}

function capKeydown(event, idx) {
    if (event.key === 'Enter') {
        event.preventDefault();
        agregarCapituloInput();
    }
}

function obtenerCapitulos() {
    const inputs = document.querySelectorAll('.cap-input');
    const caps = [];
    inputs.forEach(inp => {
        const val = inp.value.trim();
        if (val) caps.push(val);
    });
    return caps;
}

async function guardarLibro() {
    const titulo    = document.getElementById('nuevo-titulo').value.trim();
    const autor     = document.getElementById('nuevo-autor').value.trim();
    const editorial = document.getElementById('nuevo-editorial').value.trim();
    const capitulos = obtenerCapitulos();
    const stock     = parseInt(document.getElementById('nuevo-stock').value) || 10;
    const errorEl   = document.getElementById('agregar-error');
    const okEl      = document.getElementById('agregar-ok');

    errorEl.style.display = 'none';
    okEl.style.display = 'none';

    if (!titulo || !autor || !editorial) {
        errorEl.textContent = '⚠️ Título, autor y editorial son obligatorios.';
        errorEl.style.display = 'block';
        return;
    }

    const capituloStr = capitulos.join(' || ');

    try {
        const res = await fetch('/api/libros', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ titulo, autor, editorial, capitulo: capituloStr, stock })
        });
        const data = await res.json();
        if (res.ok) {
            okEl.textContent = '✅ ' + data.mensaje;
            okEl.style.display = 'block';
            setTimeout(() => {
                cerrarModalAgregar();
                loadLibros(1);
            }, 1200);
        } else {
            errorEl.textContent = '❌ ' + (data.error || 'Error al guardar el libro');
            errorEl.style.display = 'block';
        }
    } catch (err) {
        errorEl.textContent = '❌ Error de conexión. Intentá de nuevo.';
        errorEl.style.display = 'block';
    }
}

// Cerrar modal con Escape
document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') cerrarModalAgregar();
});

// ── Event Listeners con debounce ─────────────────────────────
let searchDebounce = null;
if (document.getElementById('admin-search')) {
    document.getElementById('admin-search').addEventListener('input', () => {
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(() => loadLibros(1), 350);
    });
}

if (document.getElementById('admin-per-page')) {
    document.getElementById('admin-per-page').addEventListener('change', (e) => { 
        perPage = parseInt(e.target.value); 
        loadLibros(1); 
    });
}

if (document.getElementById('admin-tbody')) {
    loadLibros(1);
}

async function actualizarStock(libroId) {
    const input = document.querySelector('.stock-input[data-libro-id="' + libroId + '"]');
    const cantidad = input.value;
    
    try {
        const response = await fetch('/api/libros/' + libroId + '/stock', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cantidad: cantidad })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            loadLibros(currentPage);
        } else {
            alert('Error: ' + data.error);
        }
    } catch (error) {
        console.error('Error al actualizar stock:', error);
        alert('Error al actualizar el stock');
    }
}