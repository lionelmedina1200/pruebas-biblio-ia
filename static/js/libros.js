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
                <td>${l.capitulo || '-'}</td>
                <td>${l.ubicacion || '-'}</td>
                <td>
                    <span class="badge ${l.disponible ? 'disponible' : 'no-disponible'}">
                        ${l.disponible ? '✅ Disp.' : '❌ Prestado'}
                    </span>
                </td>
                <td>
                    <button class="btn-toggle" onclick="toggleDisp(${l.id}, ${l.disponible})">
                        ${l.disponible ? 'Marcar Prestado' : 'Marcar Disp.'}
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
    await fetch(`/api/libros/${id}`, { 
        method: 'PUT', 
        headers: { 'Content-Type': 'application/json' }, 
        body: JSON.stringify({ disponible: !actual }) 
    });
    loadLibros(currentPage);
}

// Event Listeners
if (document.getElementById('admin-search')) {
    document.getElementById('admin-search').addEventListener('input', () => loadLibros(1));
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