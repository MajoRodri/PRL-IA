/* ── Lucide icons (static HTML) ───────────────────────────── */
if (typeof lucide !== 'undefined') lucide.createIcons();

/* ── Inline SVGs for dynamically created content ──────────── */
const ICON = {
  assistant: `<img src="/static/img/icon.png" alt="Paco" style="width:100%;height:100%;object-fit:contain;" />`,
  file:      `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
  copy:      `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>`,
  check:     `<svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>`,
  chevron:   `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="6 9 12 15 18 9"/></svg>`,
};

/* ── Scroll reveal ────────────────────────────────────────── */
(function initScrollReveal() {
  const targets = document.querySelectorAll(
    '.section-header, .feature-card, .step, .doc-card, .chat'
  );

  // Stagger children inside grid containers
  document.querySelectorAll('.features__grid, .documents__grid, .steps__grid').forEach(grid => {
    grid.querySelectorAll('.feature-card, .doc-card, .step').forEach((child, i) => {
      child.style.transitionDelay = `${i * 75}ms`;
    });
  });

  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });

  // Only hide and animate elements that start below the visible viewport.
  // Elements already in view at load time stay visible to avoid a flash.
  targets.forEach(el => {
    if (el.getBoundingClientRect().top >= window.innerHeight) {
      el.classList.add('scroll-reveal');
      observer.observe(el);
    }
  });
})();

/* ── Hero video: replay when hero scrolls back into view ──── */
const heroBanner = document.getElementById('heroBanner');
if (heroBanner) {
  heroBanner.addEventListener('ended', () => heroBanner.pause());

  new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        heroBanner.currentTime = 0;
        heroBanner.play();
      } else {
        heroBanner.pause();
      }
    });
  }, { threshold: 0.25 }).observe(heroBanner.closest('.hero'));
}

const chatForm     = document.getElementById('chatForm');
const chatInput    = document.getElementById('chatInput');
const chatMessages = document.getElementById('chatMessages');
const fileUpload   = document.getElementById('fileUpload');

const chatWidget = document.getElementById('chatWidget');
const chatFab    = document.getElementById('chatFab');
const chatPopup  = document.getElementById('chatPopup');
const chatClose  = document.getElementById('chatClose');
const chatExpand = document.getElementById('chatExpand');

function openChat() {
  chatFab.classList.add('is-open');
  chatFab.setAttribute('aria-expanded', 'true');
  chatPopup.classList.add('is-open');
  chatPopup.setAttribute('aria-hidden', 'false');
}

function closeChat() {
  chatFab.classList.remove('is-open');
  chatFab.setAttribute('aria-expanded', 'false');
  chatPopup.classList.remove('is-open', 'chat-popup--expanded');
  chatPopup.setAttribute('aria-hidden', 'true');
  chatWidget.classList.remove('is-expanded');
  chatExpand?.setAttribute('aria-label', 'Expandir chat');
  document.body.style.overflow = '';
}

function collapseExpanded() {
  chatPopup.classList.remove('chat-popup--expanded');
  chatWidget.classList.remove('is-expanded');
  chatExpand?.setAttribute('aria-label', 'Expandir chat');
  document.body.style.overflow = '';
}

/* Show widget once the hero is completely out of view (= white section visible) */
let chatUserClosed = false;

const heroSection = document.querySelector('.hero');
if (heroSection) {
  new IntersectionObserver((entries) => {
    if (!entries[0].isIntersecting) {
      chatWidget.classList.add('is-visible');
      chatWidget.setAttribute('aria-hidden', 'false');
      if (!chatUserClosed) openChat();
    } else {
      if (chatPopup.classList.contains('chat-popup--expanded')) return;
      chatWidget.classList.remove('is-visible');
      chatWidget.setAttribute('aria-hidden', 'true');
      closeChat();
      chatPopup.classList.remove('is-medium');
      chatUserClosed = false;
    }
  }, { threshold: 0 }).observe(heroSection);
}

chatFab?.addEventListener('click', () => {
  if (chatFab.classList.contains('is-open')) {
    chatUserClosed = true;
    closeChat();
  } else {
    chatUserClosed = false;
    openChat();
  }
});

chatClose?.addEventListener('click', () => {
  chatUserClosed = true;
  closeChat();
});

/* Input focus → medium state (sticky once triggered) */
chatInput?.addEventListener('focus', () => {
  if (!chatPopup.classList.contains('chat-popup--expanded')) {
    chatPopup.classList.add('is-medium');
  }
});

/* Expand button → full-screen centered overlay */
chatExpand?.addEventListener('click', () => {
  const isExpanded = chatPopup.classList.toggle('chat-popup--expanded');
  chatWidget.classList.toggle('is-expanded', isExpanded);
  chatExpand.setAttribute('aria-label', isExpanded ? 'Reducir chat' : 'Expandir chat');
  document.body.style.overflow = isExpanded ? 'hidden' : '';
});

/* Click on the dark overlay (outside the popup) → collapse */
chatWidget?.addEventListener('click', (e) => {
  if (e.target === chatWidget) collapseExpanded();
});

/* "Hacer una consulta" in hero → scroll past hero then open chat */
document.querySelectorAll('a[href="#chat"]').forEach(link => {
  link.addEventListener('click', e => {
    e.preventDefault();
    window.scrollBy({ top: window.innerHeight, behavior: 'smooth' });
    setTimeout(openChat, 500);
  });
});


/* ── Chat form submit ─────────────────────────────────────── */
chatForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const question = chatInput.value.trim();
  if (!question) return;

  removeWelcome();
  appendMessage('user', question);
  chatInput.value = '';
  chatInput.disabled = true;

  const loadingId = appendLoading();

  try {
    const res  = await fetch('/api/query', {
      method:  'POST',
      headers: { 'Content-Type': 'application/json' },
      body:    JSON.stringify({ question }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    removeLoading(loadingId);

    if (data.abstained) {
      appendMessage('assistant', 'No he encontrado información suficiente en los documentos disponibles para responder a esta consulta.', [], data.metrics);
    } else {
      appendMessage('assistant', data.answer, data.sources ?? [], data.metrics);
    }
  } catch {
    removeLoading(loadingId);
    appendMessage('assistant', 'Error al conectar con el servidor. Por favor, inténtalo de nuevo.');
  } finally {
    chatInput.disabled = false;
    chatInput.focus();
  }
});

/* ── File upload ──────────────────────────────────────────── */
function uploadWithProgress(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const form = new FormData();
    form.append('file', file);

    xhr.upload.addEventListener('progress', (e) => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    });
    xhr.addEventListener('load', () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { resolve(JSON.parse(xhr.responseText)); }
        catch { resolve({}); }
      } else {
        try {
          const body = JSON.parse(xhr.responseText);
          reject(new Error(body.error ?? `HTTP ${xhr.status}`));
        } catch {
          reject(new Error(`HTTP ${xhr.status}`));
        }
      }
    });
    xhr.addEventListener('error', () => reject(new Error('Error de red')));
    xhr.open('POST', '/api/upload');
    xhr.send(form);
  });
}

function appendProgress(filename) {
  const id = `prog-${Date.now()}`;
  const el = document.createElement('div');
  el.id = id;
  el.className = 'message message--assistant';
  el.innerHTML = `
    <div class="message__avatar" aria-hidden="true">${ICON.assistant}</div>
    <div class="message__body">
      <div class="message__bubble">
        <div class="upload-progress">
          <span class="upload-progress__name">${escapeHTML(filename)}</span>
          <div class="upload-progress__row">
            <div class="upload-progress__track">
              <div class="upload-progress__fill" id="${id}-fill"></div>
            </div>
            <span class="upload-progress__pct" id="${id}-pct">0%</span>
          </div>
          <span class="upload-progress__status" id="${id}-status">Subiendo...</span>
        </div>
      </div>
    </div>`;
  chatMessages.appendChild(el);
  scrollToBottom();

  return {
    setProgress(pct) {
      const fill   = document.getElementById(`${id}-fill`);
      const pctEl  = document.getElementById(`${id}-pct`);
      const status = document.getElementById(`${id}-status`);
      if (fill)   fill.style.width = `${pct}%`;
      if (pctEl)  pctEl.textContent = `${pct}%`;
      if (pct >= 100) {
        fill?.classList.add('upload-progress__fill--processing');
        if (status) status.textContent = 'Indexando fragmentos...';
      }
    },
    remove() { document.getElementById(id)?.remove(); },
  };
}

fileUpload?.addEventListener('change', async () => {
  const files = Array.from(fileUpload.files);
  if (!files.length) return;

  removeWelcome();
  fileUpload.value = '';

  for (const file of files) {
    appendMessage('user', `Cargando: ${file.name}`);
    const progress = appendProgress(file.name);

    try {
      const data = await uploadWithProgress(file, (pct) => progress.setProgress(pct));
      progress.remove();
      appendMessage('assistant', data.message ?? `"${file.name}" indexado correctamente.`);
    } catch (err) {
      progress.remove();
      const msg = (err.message && !err.message.startsWith('HTTP') && err.message !== 'Error de red')
        ? err.message
        : `No se pudo procesar "${file.name}". Comprueba el formato e inténtalo de nuevo.`;
      appendMessage('assistant', msg);
    }
  }
});

/* ── Helpers ──────────────────────────────────────────────── */
function removeWelcome() {
  document.getElementById('chatWelcome')?.remove();
}

function renderMetrics(metrics) {
  if (!metrics || typeof metrics !== 'object') return '';
  const tokens = value => Number.isInteger(value) && value >= 0
    ? value.toLocaleString('es-ES') : 'No disponible';
  const latency = typeof metrics.server_latency_ms === 'number'
    && Number.isFinite(metrics.server_latency_ms) && metrics.server_latency_ms >= 0
    ? (metrics.server_latency_ms / 1000).toLocaleString('es-ES', {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
      }) + ' s' : 'No disponible';
  return `<details class="message__metrics">
    <summary class="message__sources-summary">${ICON.chevron} Consumo y tiempo</summary>
    <dl class="message__metrics-grid">
      <div><dt>Tokens de entrada</dt><dd>${tokens(metrics.input_tokens)}</dd></div>
      <div><dt>Tokens de salida</dt><dd>${tokens(metrics.output_tokens)}</dd></div>
      <div><dt>Total de tokens</dt><dd>${tokens(metrics.total_tokens)}</dd></div>
      <div><dt>Tiempo del servidor</dt><dd>${latency}</dd></div>
    </dl>
    <p class="message__metrics-note">Entrada: instrucciones, pregunta y contexto enviado al modelo.
    Tiempo: búsqueda y generación, sin el trayecto por Internet hasta tu navegador.
    Consumo comunicado por el proveedor para esta respuesta.</p>
  </details>`;
}

function appendMessage(role, text, sources = [], metrics = null) {
  const el = document.createElement('div');
  el.className = `message message--${role}`;

  const avatarContent = role === 'user' ? 'Tú' : ICON.assistant;

  const sourcesHTML = sources.length
    ? `<details class="message__sources-details">
        <summary class="message__sources-summary">
          ${ICON.chevron} Fuentes (${sources.length})
        </summary>
        <div class="message__sources">
          ${sources.map(s => `
            <span class="source-badge">
              ${ICON.file} ${escapeHTML(s.document)}${s.page ? ` · p.&nbsp;${s.page}` : ''}
            </span>`).join('')}
        </div>
       </details>`
    : '';

  const copyBtn = role === 'assistant'
    ? `<button class="message__copy" title="Copiar respuesta" aria-label="Copiar respuesta">${ICON.copy}</button>`
    : '';

  const bubbleContent = role === 'assistant' ? renderMarkdown(text) : escapeHTML(text);
  el.innerHTML = `
    <div class="message__avatar" aria-hidden="true">${avatarContent}</div>
    <div class="message__body">
      <div class="message__bubble">${bubbleContent}${copyBtn}</div>
      ${sourcesHTML}
      ${role === 'assistant' ? renderMetrics(metrics) : ''}
    </div>`;

  chatMessages.appendChild(el);
  scrollToBottom();

  const copyEl = el.querySelector('.message__copy');
  if (copyEl) {
    copyEl.addEventListener('click', () => {
      navigator.clipboard.writeText(text).then(() => {
        copyEl.innerHTML = ICON.check;
        copyEl.classList.add('message__copy--copied');
        setTimeout(() => {
          copyEl.innerHTML = ICON.copy;
          copyEl.classList.remove('message__copy--copied');
        }, 2000);
      });
    });
  }
}

function appendLoading() {
  const id = `loading-${Date.now()}`;
  const el = document.createElement('div');
  el.id = id;
  el.className = 'message message--assistant';
  el.setAttribute('aria-label', 'El asistente está escribiendo');
  el.innerHTML = `
    <div class="message__avatar" aria-hidden="true">${ICON.assistant}</div>
    <div class="message__body">
      <div class="message__bubble">
        <div class="message__loading" aria-hidden="true">
          <span></span><span></span><span></span>
        </div>
      </div>
    </div>`;
  chatMessages.appendChild(el);
  scrollToBottom();
  return id;
}

function removeLoading(id) {
  document.getElementById(id)?.remove();
}

function scrollToBottom() {
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function escapeHTML(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function renderMarkdown(raw) {
  const lines = String(raw).split('\n');
  const out = [];
  let listTag = null;
  let tableRows = [];

  const applyInline = (s) =>
    s.replace(/\*\*\*(.*?)\*\*\*/g, '<strong><em>$1</em></strong>')
     .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
     .replace(/(?<![a-zA-Z0-9_])_(.*?)_(?![a-zA-Z0-9_])/g, '<em>$1</em>')
     .replace(/`([^`\n]+)`/g, '<code class="md-code">$1</code>')
     .replace(/&lt;br\s*\/?&gt;/gi, '<br>');

  const flushList = () => { if (listTag) { out.push(`</${listTag}>`); listTag = null; } };

  const isSeparatorRow = (l) => /^\|[\s\-|:]+\|$/.test(l.trim());
  const parseCells = (row) =>
    row.trim().replace(/^\||\|$/g, '').split('|').map(c => applyInline(escapeHTML(c.trim())));

  const flushTable = () => {
    if (!tableRows.length) return;
    const rows = tableRows.filter(l => !isSeparatorRow(l));
    if (rows.length) {
      const [head, ...body] = rows;
      const headCells = parseCells(head).map(c => `<th>${c}</th>`).join('');
      out.push(`<div class="md-table-wrap"><table class="md-table"><thead><tr>${headCells}</tr></thead>`);
      if (body.length) {
        out.push('<tbody>');
        body.forEach(row => {
          out.push(`<tr>${parseCells(row).map(c => `<td>${c}</td>`).join('')}</tr>`);
        });
        out.push('</tbody>');
      }
      out.push('</table></div>');
    }
    tableRows = [];
  };

  for (const raw_line of lines) {
    const line = raw_line.trimEnd();

    if (line.trim().startsWith('|')) {
      flushList();
      tableRows.push(line);
      continue;
    }

    flushTable();

    const trimmed = line.trim();
    const ulMatch = trimmed.match(/^[\-\*•]\s+(.+)/);
    const olMatch = trimmed.match(/^\d+[.)]\s+(.+)/);
    const hMatch  = trimmed.match(/^(#{1,6})\s+(.+)/);
    const bqMatch = trimmed.match(/^>\s*(.*)/);
    const isHR    = /^(\-{3,}|\*{3,}|_{3,})$/.test(trimmed);

    if (ulMatch) {
      if (listTag !== 'ul') { flushList(); out.push('<ul>'); listTag = 'ul'; }
      out.push(`<li>${applyInline(escapeHTML(ulMatch[1]))}</li>`);
    } else if (olMatch) {
      if (listTag !== 'ol') { flushList(); out.push('<ol>'); listTag = 'ol'; }
      out.push(`<li>${applyInline(escapeHTML(olMatch[1]))}</li>`);
    } else {
      flushList();
      if (trimmed === '') {
        out.push('<br>');
      } else if (hMatch) {
        const lvl = Math.min(hMatch[1].length + 2, 6);
        out.push(`<h${lvl} class="md-heading">${applyInline(escapeHTML(hMatch[2]))}</h${lvl}>`);
      } else if (isHR) {
        out.push('<hr class="md-hr">');
      } else if (bqMatch) {
        out.push(`<blockquote class="md-quote">${applyInline(escapeHTML(bqMatch[1]))}</blockquote>`);
      } else {
        out.push(`<p>${applyInline(escapeHTML(line))}</p>`);
      }
    }
  }
  flushList();
  flushTable();
  return out.join('');
}
