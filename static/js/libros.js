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
                        ${l.disponible > 0 ? `✅ ${l.disponible} en stock` : '❌ Sin stock'}
                    </span>
                </td>
                <td>
                    <button class="btn-toggle" onclick="toggleDisp(${l.id}, ${l.disponible})">
                        ${l.disponible > 0 ? '➖ Marcar Prestado' : '➕ Marcar Devuelto'}
                    </button>
                </td>
            </tr>
        `).join('');
        
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
    // actual = stock actual del libro
    // Si hay stock > 0, descontamos 1 (marcar prestado)
    // Si stock = 0, sumamos 1 (marcar disponible / devuelto)
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

// ── Modal agregar libro ──────────────────────────────────────
function abrirModalAgregar() {
    document.getElementById('modal-agregar').classList.add('open');
    document.getElementById('nuevo-titulo').focus();
    document.getElementById('agregar-error').style.display = 'none';
    document.getElementById('agregar-ok').style.display = 'none';
}

function cerrarModalAgregar() {
    document.getElementById('modal-agregar').classList.remove('open');
    // Limpiar campos
    ['nuevo-titulo','nuevo-autor','nuevo-editorial','nuevo-capitulo'].forEach(id => {
        document.getElementById(id).value = '';
    });
    document.getElementById('nuevo-stock').value = '1';
}

async function guardarLibro() {
    const titulo    = document.getElementById('nuevo-titulo').value.trim();
    const autor     = document.getElementById('nuevo-autor').value.trim();
    const editorial = document.getElementById('nuevo-editorial').value.trim();
    const capitulo  = document.getElementById('nuevo-capitulo').value.trim();
    const stock     = parseInt(document.getElementById('nuevo-stock').value) || 1;
    const errorEl   = document.getElementById('agregar-error');
    const okEl      = document.getElementById('agregar-ok');

    errorEl.style.display = 'none';
    okEl.style.display = 'none';

    // Validación frontend: los 3 campos obligatorios
    if (!titulo || !autor || !editorial) {
        errorEl.textContent = '⚠️ Título, autor y editorial son obligatorios.';
        errorEl.style.display = 'block';
        return;
    }

    try {
        const res = await fetch('/api/libros', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ titulo, autor, editorial, capitulo, stock })
        });
        const data = await res.json();
        if (res.ok) {
            okEl.textContent = '✅ ' + data.mensaje;
            okEl.style.display = 'block';
            setTimeout(() => {
                cerrarModalAgregar();
                loadLibros(1); // Refrescar lista
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

// ── Event Listeners con debounce para búsqueda más rápida ────
let searchDebounce = null;
if (document.getElementById('admin-search')) {
    document.getElementById('admin-search').addEventListener('input', () => {
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(() => loadLibros(1), 350); // espera 350ms antes de buscar
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
    const input = document.querySelector(`.stock-input[data-libro-id="${libroId}"]`);
    const cantidad = input.value;
    
    try {
        const response = await fetch(`/api/libros/${libroId}/stock`, {
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