/* ── Lucide icons (static HTML) ───────────────────────────── */
lucide.createIcons();

/* ── Inline SVGs for dynamically created content ──────────── */
const ICON = {
  assistant: `<img src="/static/img/icon.png" alt="PRL Assistant" style="width:100%;height:100%;object-fit:contain;" />`,
  file:      `<svg xmlns="http://www.w3.org/2000/svg" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>`,
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

/* ── Suggestion pills ─────────────────────────────────────── */
document.querySelectorAll('.chat__suggestion').forEach(btn => {
  btn.addEventListener('click', () => {
    chatInput.value = btn.textContent.trim();
    chatInput.focus();
    document.getElementById('chat').scrollIntoView({ behavior: 'smooth' });
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
      appendMessage('assistant', 'No he encontrado información suficiente en los documentos disponibles para responder a esta consulta.', []);
    } else {
      appendMessage('assistant', data.answer, data.sources ?? []);
    }
  } catch {
    removeLoading(loadingId);
    appendMessage('assistant', 'Error al conectar con el servidor. Por favor, inténtalo de nuevo.');
  } finally {
    chatInput.disabled = false;
    chatInput.focus();
  }
});

/* ── File upload (placeholder) ────────────────────────────── */
fileUpload?.addEventListener('change', async () => {
  const file = fileUpload.files[0];
  if (!file) return;

  removeWelcome();
  appendMessage('user', `Cargando documento: ${file.name}`);

  const loadingId = appendLoading();
  const form = new FormData();
  form.append('file', file);

  try {
    const res = await fetch('/api/upload', { method: 'POST', body: form });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    removeLoading(loadingId);
    appendMessage('assistant', `Documento "${file.name}" procesado e indexado correctamente. Ya puedes hacer preguntas sobre él.`);
  } catch {
    removeLoading(loadingId);
    appendMessage('assistant', 'No se pudo procesar el documento. Comprueba el formato e inténtalo de nuevo.');
  }

  fileUpload.value = '';
});

/* ── Helpers ──────────────────────────────────────────────── */
function removeWelcome() {
  document.getElementById('chatWelcome')?.remove();
}

function appendMessage(role, text, sources = []) {
  const el = document.createElement('div');
  el.className = `message message--${role}`;

  const avatarContent = role === 'user' ? 'Tú' : ICON.assistant;

  const sourcesHTML = sources.length
    ? `<div class="message__sources">
        ${sources.map(s => `
          <span class="source-badge">
            ${ICON.file} ${escapeHTML(s.document)}${s.page ? ` · p.&nbsp;${s.page}` : ''}
          </span>`).join('')}
       </div>`
    : '';

  el.innerHTML = `
    <div class="message__avatar" aria-hidden="true">${avatarContent}</div>
    <div class="message__body">
      <div class="message__bubble">${escapeHTML(text)}</div>
      ${sourcesHTML}
    </div>`;

  chatMessages.appendChild(el);
  scrollToBottom();
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
