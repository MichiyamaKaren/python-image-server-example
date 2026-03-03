document.addEventListener('DOMContentLoaded', function () {
    const urlPath = window.location.pathname.replace(/^\/files\/?/, '');

    // ── state ──────────────────────────────────────────────────────────────────
    let selectMode = false;
    let lastClickedFig = null;
    const selected = new Set();
    const figures = [];

    // ── DOM refs ───────────────────────────────────────────────────────────────
    const grid = document.querySelector('.image-grid');
    const btnSelectMode = document.getElementById('btn-select-mode');
    const btnSelectAll = document.getElementById('btn-select-all');
    const btnDownload = document.getElementById('btn-download');
    const btnDelete = document.getElementById('btn-delete');
    const actionBar = document.getElementById('action-bar');
    const selectedCount = document.getElementById('selected-count');
    const overlay = document.getElementById('image-overlay');
    const overlayImg = document.getElementById('overlay-img');
    const overlayActions = document.getElementById('overlay-actions');
    const sseStatus = document.getElementById('sse-status');

    // ── selection helpers ──────────────────────────────────────────────────────
    function updateActionBar() {
        selectedCount.textContent = selected.size + ' 项已选';
        actionBar.classList.toggle('visible', selected.size > 0);
    }

    function setFigureSelected(fig, on) {
        if (on) { selected.add(fig.dataset.path); fig.classList.add('selected'); }
        else    { selected.delete(fig.dataset.path); fig.classList.remove('selected'); }
    }

    function toggleSelectMode(on) {
        selectMode = on;
        btnSelectMode.classList.toggle('active', on);
        grid.classList.toggle('select-mode', on);
        if (!on) {
            selected.clear();
            lastClickedFig = null;
            figures.forEach(f => f.classList.remove('selected'));
            actionBar.classList.remove('visible');
        }
    }

    // ── overlay ────────────────────────────────────────────────────────────────
    let currentOverlayIndex = -1;

    function openOverlay(idx) {
        currentOverlayIndex = idx;
        overlayImg.src = figures[idx].querySelector('img').src;
        overlay.classList.add('active');
        overlayActions.style.display = 'flex';
    }

    function closeOverlay() {
        overlay.classList.remove('active');
        overlayActions.style.display = 'none';
    }

    // ── figure factory ─────────────────────────────────────────────────────────
    function createFigure(file) {
        const fig = document.createElement('figure');
        fig.dataset.path = file.filename;

        const checkMark = document.createElement('span');
        checkMark.className = 'check-mark';
        checkMark.innerHTML = '&#10003;';

        const img = document.createElement('img');
        img.src = '/files/' + file.filename;
        img.alt = file.filename;

        const infoBtn = document.createElement('button');
        infoBtn.className = 'info-button';
        infoBtn.textContent = 'i';

        const modal = document.createElement('div');
        modal.className = 'modal';
        const modalContent = document.createElement('div');
        modalContent.className = 'modal-content';
        const closeBtn = document.createElement('span');
        closeBtn.className = 'close-button';
        closeBtn.innerHTML = '&times;';
        const metaP = document.createElement('p');
        const metaEntries = Object.entries(file.metadata || {});
        metaP.textContent = metaEntries.length
            ? metaEntries.map(([k, v]) => k + ': ' + v).join('\n')
            : '(no metadata)';
        modalContent.appendChild(closeBtn);
        modalContent.appendChild(metaP);
        modal.appendChild(modalContent);

        fig.appendChild(checkMark);
        fig.appendChild(img);
        fig.appendChild(infoBtn);
        fig.appendChild(modal);

        img.addEventListener('click', function (e) {
            if (selectMode) return;
            if (e.ctrlKey || e.metaKey || e.shiftKey) return;
            openOverlay(figures.indexOf(fig));
        });

        fig.addEventListener('click', function (e) {
            if (e.target.classList.contains('info-button')) return;
            const isModified = e.ctrlKey || e.metaKey || e.shiftKey;
            if (!selectMode && !isModified) return;
            e.preventDefault();
            e.stopPropagation();
            if (!selectMode) toggleSelectMode(true);
            const idx = figures.indexOf(fig);
            if (e.shiftKey && lastClickedFig !== null) {
                const lastIdx = figures.indexOf(lastClickedFig);
                if (lastIdx !== -1) {
                    const lo = Math.min(lastIdx, idx);
                    const hi = Math.max(lastIdx, idx);
                    for (let i = lo; i <= hi; i++) setFigureSelected(figures[i], true);
                }
                lastClickedFig = fig;
            } else {
                setFigureSelected(fig, !fig.classList.contains('selected'));
                lastClickedFig = fig;
            }
            updateActionBar();
        });

        infoBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            modal.style.display = 'block';
        });
        modal.addEventListener('click', function (e) {
            if (e.target === modal) modal.style.display = 'none';
        });
        closeBtn.addEventListener('click', function () {
            modal.style.display = 'none';
        });

        return fig;
    }

    function addFigure(file) {
        const fig = createFigure(file);
        figures.push(fig);
        grid.appendChild(fig);
    }

    function removeFigureByFilename(filename) {
        const idx = figures.findIndex(f => f.dataset.path === filename);
        if (idx === -1) return;
        const fig = figures[idx];
        if (lastClickedFig === fig) lastClickedFig = null;
        selected.delete(fig.dataset.path);
        fig.remove();
        figures.splice(idx, 1);
        updateActionBar();
        if (overlay.classList.contains('active')) {
            if (figures.length === 0) {
                closeOverlay();
            } else if (currentOverlayIndex === idx) {
                openOverlay(Math.min(idx, figures.length - 1));
            } else if (currentOverlayIndex > idx) {
                currentOverlayIndex--;
            }
        }
    }

    // ── toolbar ────────────────────────────────────────────────────────────────
    btnSelectMode.addEventListener('click', () => toggleSelectMode(!selectMode));

    btnSelectAll.addEventListener('click', function () {
        const allSelected = figures.length === selected.size;
        figures.forEach(fig => setFigureSelected(fig, !allSelected));
        updateActionBar();
    });

    btnDownload.addEventListener('click', function () {
        selected.forEach(path => {
            const a = document.createElement('a');
            a.href = '/files/' + path;
            a.download = path.split(/[/\\]/).pop();
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        });
    });

    btnDelete.addEventListener('click', async function () {
        if (!confirm('确认删除选中的 ' + selected.size + ' 个文件？')) return;
        const paths = Array.from(selected);
        const failed = [];
        for (const p of paths) {
            const resp = await fetch('/files/' + p, { method: 'DELETE' });
            if (resp.ok) removeFigureByFilename(p);
            else failed.push(p);
        }
        if (failed.length) alert('以下文件删除失败：\n' + failed.join('\n'));
    });

    // ── overlay buttons ────────────────────────────────────────────────────────
    document.getElementById('overlay-btn-download').addEventListener('click', function (e) {
        e.stopPropagation();
        const p = figures[currentOverlayIndex].dataset.path;
        const a = document.createElement('a');
        a.href = '/files/' + p;
        a.download = p.split(/[/\\]/).pop();
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    });

    document.getElementById('overlay-btn-delete').addEventListener('click', async function (e) {
        e.stopPropagation();
        const p = figures[currentOverlayIndex].dataset.path;
        if (!confirm('确认删除该文件？')) return;
        const resp = await fetch('/files/' + p, { method: 'DELETE' });
        if (resp.ok) removeFigureByFilename(p);
        else alert('删除失败');
    });

    overlay.addEventListener('click', function (e) {
        if (e.target === this) closeOverlay();
    });

    document.addEventListener('keydown', function (e) {
        if (!overlay.classList.contains('active')) return;
        if (e.key === 'ArrowRight') openOverlay((currentOverlayIndex + 1) % figures.length);
        else if (e.key === 'ArrowLeft') openOverlay((currentOverlayIndex - 1 + figures.length) % figures.length);
        else if (e.key === 'Escape') closeOverlay();
    });

    // ── initial load ───────────────────────────────────────────────────────────
    async function loadFiles() {
        const resp = await fetch('/api/files/' + urlPath);
        if (!resp.ok) { document.querySelector('h1').textContent = 'Error loading directory'; return; }
        const data = await resp.json();
        document.title = 'Files in ' + (data.path || '/');
        document.querySelector('h1').textContent = 'Files in ' + (data.path || '/');
        data.files.forEach(file => addFigure(file));
        const ul = document.getElementById('dir-list');
        data.dirs.forEach(dir => {
            const li = document.createElement('li');
            const a = document.createElement('a');
            a.href = '/files/' + dir;
            a.textContent = dir;
            li.appendChild(a);
            ul.appendChild(li);
        });
    }

    // ── SSE ────────────────────────────────────────────────────────────────────
    function connectSSE() {
        const es = new EventSource('/api/sse/' + urlPath);
        es.onopen = () => { sseStatus.textContent = '● 实时同步'; sseStatus.style.color = '#4caf50'; };
        es.onmessage = function (e) {
            const data = JSON.parse(e.data);
            if (data.type === 'added') data.files.forEach(file => addFigure(file));
            else if (data.type === 'removed') data.filenames.forEach(fn => removeFigureByFilename(fn));
        };
        es.onerror = () => { sseStatus.textContent = '○ 连接中断，重连...'; sseStatus.style.color = '#f44336'; };
    }

    loadFiles().then(() => connectSSE());
});
