/**
 * ConcertArr — app.js
 *
 * O que esse arquivo faz:
 * 1. Navega entre as telas
 * 2. Carrega config salva do servidor
 * 3. Inicia o scan e atualiza o progresso em tempo real
 * 4. Monta a tela de resultado
 * 5. Busca manual via link do Discogs
 * 6. Mosaico de capas com filtro e seleção
 */

// ─── URL base da API ──────────────────────────────────────────
// Em produção (Docker) usa o mesmo host
// Em desenvolvimento local, aponta pro servidor
const API = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
  ? 'http://localhost:8090'
  : '';

// ─── Estado global ────────────────────────────────────────────
let allShows       = [];    // todos os shows da pasta
let notFoundShows  = [];    // shows sem capa após o scan
let scanInterval   = null;  // timer de polling do progresso
let mosaicFilter   = 'all'; // filtro atual do mosaico
let selectedShow   = null;  // show selecionado no mosaico

// ─── Navegação entre telas ────────────────────────────────────

function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  window.scrollTo(0, 0);
}

// ─── Inicialização ────────────────────────────────────────────

window.addEventListener('DOMContentLoaded', async () => {
  // Tenta carregar configuração salva
  try {
    const cfg = await fetch(`${API}/api/config`).then(r => r.json());
    if (cfg.shows_dir)     document.getElementById('input-folder').value  = cfg.shows_dir;
    if (cfg.tmdb_key)      document.getElementById('input-tmdb').value    = cfg.tmdb_key;
    if (cfg.discogs_token) document.getElementById('input-discogs').value = cfg.discogs_token;
  } catch (e) {
    // Backend ainda não disponível, ignora
  }
  showScreen('screen-folder');
});

// ─── Tela 1 → Tela 2 (valida a pasta) ────────────────────────

async function goToAPIs() {
  const folder = document.getElementById('input-folder').value.trim();
  if (!folder) {
    alert('Informe o caminho da pasta dos shows');
    return;
  }
  showScreen('screen-apis');
}

// ─── Tela 2 → Tela 3 (inicia o scan) ─────────────────────────

async function startScan() {
  const folder   = document.getElementById('input-folder').value.trim();
  const tmdbKey  = document.getElementById('input-tmdb').value.trim();
  const discogs  = document.getElementById('input-discogs').value.trim();

  if (!tmdbKey || !discogs) {
    alert('Preencha as duas chaves de API');
    return;
  }

  // Vai pra tela de scan
  showScreen('screen-scanning');
  document.getElementById('scan-results').innerHTML = '';
  document.getElementById('btn-ver-resultado').classList.add('hidden');
  document.getElementById('scan-current-name').textContent = 'Iniciando...';

  // Dispara o scan no backend
  try {
    await fetch(`${API}/api/scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        shows_dir:      folder,
        tmdb_key:       tmdbKey,
        discogs_token:  discogs,
      })
    });
  } catch (e) {
    alert('Erro ao conectar com o servidor. Verifique se o ConcertArr está rodando.');
    showScreen('screen-apis');
    return;
  }

  // Polling: checa o progresso a cada 1 segundo
  let lastCount = 0;
  scanInterval = setInterval(async () => {
    try {
      const state = await fetch(`${API}/api/scan/status`).then(r => r.json());

      // Atualiza barra de progresso
      const pct = state.total > 0 ? Math.round((state.current / state.total) * 100) : 0;
      document.getElementById('scan-progress').style.width    = `${pct}%`;
      document.getElementById('scan-percent').textContent     = `${pct}%`;
      document.getElementById('scan-count').textContent       = `${state.current} de ${state.total}`;
      document.getElementById('scan-current-name').textContent = state.current_name || '...';

      // Adiciona novos resultados na lista
      const lista = document.getElementById('scan-results');
      for (let i = lastCount; i < state.results.length; i++) {
        const r = state.results[i];
        const dot   = r.status === 'not_found' ? 'missing' : r.status === 'skip' ? 'skip' : 'ok';
        const badge = r.status === 'not_found' ? 'warn' : '';
        const label = r.status === 'tmdb'      ? 'TMDb'
                    : r.status === 'discogs'   ? 'Discogs'
                    : r.status === 'skip'      ? 'já tinha'
                    : 'não encontrado';

        const item = document.createElement('div');
        item.className = 'result-item';
        item.innerHTML = `
          <div class="result-dot ${dot}"></div>
          <span class="result-name">${r.filename.replace(/\.[^.]+$/, '')}</span>
          <span class="result-source ${badge}">${label}</span>
        `;
        lista.appendChild(item);
        // Auto scroll pra acompanhar
        lista.scrollTop = lista.scrollHeight;
      }
      lastCount = state.results.length;

      // Terminou?
      if (state.done) {
        clearInterval(scanInterval);
        notFoundShows = state.not_found || [];
        document.getElementById('btn-ver-resultado').classList.remove('hidden');

        // Pré-carrega resultado
        prepareResult(state.stats, state.total);
      }
    } catch (e) {
      // Ignora erros temporários de rede
    }
  }, 1000);
}

// ─── Tela 3 → Tela 4 ─────────────────────────────────────────

function showResult() {
  showScreen('screen-result');
  loadMosaic(); // já carrega o mosaico em background
}

function prepareResult(stats, total) {
  document.getElementById('result-total').textContent =
    `${total} shows processados`;
  document.getElementById('stat-tmdb').textContent     = stats.tmdb    || 0;
  document.getElementById('stat-discogs').textContent  = stats.discogs || 0;
  document.getElementById('stat-notfound').textContent = stats.not_found || 0;

  // Mostra o card "busca manual" só se houver não encontrados
  const menuManual = document.getElementById('menu-manual');
  const badge      = document.getElementById('badge-notfound');
  if (notFoundShows.length > 0) {
    menuManual.classList.remove('hidden');
    badge.textContent = `${notFoundShows.length} shows`;
    buildManualList();
  } else {
    menuManual.classList.add('hidden');
  }
}

// ─── Tela 5 — Busca manual ────────────────────────────────────

function buildManualList() {
  const container = document.getElementById('manual-list');
  container.innerHTML = '';

  notFoundShows.forEach((filename, i) => {
    const name = filename.replace(/\.[^.]+$/, ''); // tira a extensão

    const div = document.createElement('div');
    div.className = 'manual-item';
    div.id = `manual-item-${i}`;
    div.innerHTML = `
      <div class="manual-item-header">
        <div class="manual-num" id="manual-num-${i}">${i + 1}</div>
        <div class="manual-name">${name}</div>
        <span class="manual-skip" onclick="skipManual(${i})">pular</span>
      </div>
      <div class="url-row">
        <input type="text" id="manual-url-${i}"
               placeholder="https://www.discogs.com/release/..." />
        <button class="btn-fetch" onclick="fetchManual('${filename}', ${i})">Baixar</button>
      </div>
      <p class="hint" style="margin-top:6px">Cole o link do release ou master no Discogs</p>
    `;
    container.appendChild(div);
  });
}

function skipManual(i) {
  const item = document.getElementById(`manual-item-${i}`);
  item.style.opacity = '0.4';
}

async function fetchManual(filename, i) {
  const url = document.getElementById(`manual-url-${i}`).value.trim();
  if (!url) { alert('Cole um link do Discogs'); return; }

  const btn = document.querySelector(`#manual-item-${i} .btn-fetch`);
  btn.textContent = 'Baixando...';
  btn.disabled = true;

  try {
    const res = await fetch(`${API}/api/manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, discogs_url: url })
    });

    if (res.ok) {
      const item = document.getElementById(`manual-item-${i}`);
      const num  = document.getElementById(`manual-num-${i}`);
      item.classList.add('done');
      num.classList.add('done');
      num.textContent = '✓';
      item.querySelector('.url-row').innerHTML =
        '<div class="done-badge">✓ Capa baixada com sucesso!</div>';
      item.querySelector('.hint').style.display = 'none';

      // Atualiza o mosaico
      loadMosaic();
    } else {
      alert('Não foi possível baixar. Verifique o link do Discogs.');
      btn.textContent = 'Baixar';
      btn.disabled = false;
    }
  } catch (e) {
    alert('Erro de conexão com o servidor');
    btn.textContent = 'Baixar';
    btn.disabled = false;
  }
}

// ─── Tela 6 — Mosaico ────────────────────────────────────────

async function loadMosaic() {
  try {
    const folder = document.getElementById('input-folder').value.trim();
    allShows = await fetch(`${API}/api/shows?shows_dir=${encodeURIComponent(folder)}`)
                      .then(r => r.json());
    renderMosaic();
  } catch (e) {
    // Silencioso
  }
}

function getFilteredShows() {
  const q = (document.getElementById('mosaic-search')?.value || '').toLowerCase();
  return allShows.filter(s => {
    const matchQ = s.name.toLowerCase().includes(q);
    const matchF = mosaicFilter === 'all'
                || (mosaicFilter === 'missing' && !s.complete)
                || (mosaicFilter === 'ok'      &&  s.complete);
    return matchQ && matchF;
  });
}

function renderMosaic() {
  const grid = document.getElementById('mosaic-grid');
  if (!grid) return;
  const shows = getFilteredShows();
  grid.innerHTML = '';

  shows.forEach((show, i) => {
    const card = document.createElement('div');
    card.className = 'poster-card' + (selectedShow === show.filename ? ' selected' : '');
    card.onclick = () => selectMosaicShow(show, i);

    // Iniciais do nome como placeholder
    const initials = show.name.split(' ').slice(0,2).map(w => w[0]).join('').toUpperCase();

    // Cor de fundo aleatória mas consistente por nome
    const hue = show.name.split('').reduce((acc, c) => acc + c.charCodeAt(0), 0) % 360;
    const bg  = `hsl(${hue}, 30%, 20%)`;

    card.innerHTML = `
      ${show.poster_path
        ? `<img src="${API}${show.poster_path}" alt="${show.name}" loading="lazy" />`
        : `<div class="poster-initials" style="background:${bg}">${initials}</div>`
      }
      <div class="poster-label">${show.name}</div>
      ${!show.complete
        ? '<div class="poster-badge warn">!</div>'
        : ''
      }
      <div class="poster-badge check">✓</div>
    `;
    grid.appendChild(card);
  });
}

function filterMosaic() { renderMosaic(); }

function setMosaicFilter(filter, btn) {
  mosaicFilter = filter;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  renderMosaic();
}

function selectMosaicShow(show, i) {
  selectedShow = show.filename;
  renderMosaic();

  // Mostra o painel de edição
  const panel = document.getElementById('selected-panel');
  panel.classList.remove('hidden');
  document.getElementById('selected-name').textContent = show.name;
  document.getElementById('selected-url').value = '';

  // Miniatura
  const thumb = document.getElementById('selected-thumb');
  if (show.poster_path) {
    thumb.innerHTML = `<img src="${API}${show.poster_path}" alt="${show.name}" />`;
  } else {
    thumb.innerHTML = '🎬';
  }

  document.getElementById('selected-url').focus();
}

async function manualFetch() {
  const url = document.getElementById('selected-url').value.trim();
  if (!url)         { alert('Cole um link do Discogs'); return; }
  if (!selectedShow){ alert('Selecione um show'); return; }

  const btn = document.querySelector('.btn-fetch');
  btn.textContent = 'Baixando...';
  btn.disabled = true;

  try {
    const res = await fetch(`${API}/api/manual`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename: selectedShow, discogs_url: url })
    });

    if (res.ok) {
      // Recarrega o mosaico com a nova capa
      await loadMosaic();
      document.getElementById('selected-panel').classList.add('hidden');
      selectedShow = null;
      alert('✓ Capa atualizada!');
    } else {
      alert('Não foi possível baixar. Verifique o link do Discogs.');
    }
  } catch (e) {
    alert('Erro de conexão com o servidor');
  } finally {
    btn.textContent = 'Baixar';
    btn.disabled = false;
  }
}

// ─── File Browser ─────────────────────────────────────────────

let fbSelectedPath = null;

async function openFileBrowser() {
  fbSelectedPath = null;
  document.getElementById('fb-confirm').disabled = true;
  document.getElementById('fb-selected-label').textContent = 'Nenhuma pasta selecionada';
  document.getElementById('modal-filebrowser').classList.remove('hidden');
  await fbNavigate('/');
}

function closeFileBrowser(event) {
  // Fecha só se clicar no overlay, não no modal em si
  if (event && event.target !== document.getElementById('modal-filebrowser')) return;
  document.getElementById('modal-filebrowser').classList.add('hidden');
}

async function fbNavigate(path) {
  document.getElementById('fb-path').textContent = path;
  document.getElementById('fb-list').innerHTML = '<div class="fb-loading">Carregando...</div>';

  try {
    const data = await fetch(`${API}/api/browse?path=${encodeURIComponent(path)}`).then(r => r.json());
    renderFbList(data);
  } catch (e) {
    document.getElementById('fb-list').innerHTML =
      '<div class="fb-loading">Erro ao carregar. Verifique o servidor.</div>';
  }
}

function renderFbList(data) {
  const list = document.getElementById('fb-list');
  list.innerHTML = '';

  // Botão voltar para pasta pai
  if (data.parent !== null) {
    const parent = document.createElement('div');
    parent.className = 'fb-item fb-item-parent';
    parent.innerHTML = `<span class="fb-icon">⬆️</span><span class="fb-name">.. (voltar)</span>`;
    parent.onclick = () => fbNavigate(data.parent);
    list.appendChild(parent);
  }

  // Só mostra pastas (não arquivos)
  const dirs = data.items.filter(i => i.is_dir);

  if (dirs.length === 0) {
    const empty = document.createElement('div');
    empty.className = 'fb-loading';
    empty.textContent = 'Nenhuma subpasta encontrada';
    list.appendChild(empty);
  }

  dirs.forEach(item => {
    const div = document.createElement('div');
    div.className = 'fb-item' + (fbSelectedPath === item.path ? ' selected' : '');
    div.innerHTML = `<span class="fb-icon">📁</span><span class="fb-name">${item.name}</span><span style="font-size:11px;color:var(--text-hint)">→</span>`;

    // Clique simples — seleciona a pasta
    div.onclick = () => {
      fbSelectedPath = item.path;
      document.querySelectorAll('.fb-item').forEach(el => el.classList.remove('selected'));
      div.classList.add('selected');
      document.getElementById('fb-selected-label').textContent = item.path;
      document.getElementById('fb-confirm').disabled = false;
    };

    // Duplo clique — navega para dentro
    div.ondblclick = () => fbNavigate(item.path);

    list.appendChild(div);
  });
}

function confirmFolder() {
  if (!fbSelectedPath) return;
  document.getElementById('input-folder').value = fbSelectedPath;
  document.getElementById('modal-filebrowser').classList.add('hidden');
}

function goToMosaic() {
  showScreen('screen-mosaic');
  loadMosaic();
}
