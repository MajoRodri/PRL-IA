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
}

function collapseExpanded() {
  chatPopup.classList.remove('chat-popup--expanded');
  chatWidget.classList.remove('is-expanded');
  chatExpand?.setAttribute('aria-label', 'Expandir chat');
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

/* ── Suggestion pills ─────────────────────────────────────── */
document.querySelectorAll('.chat__suggestion').forEach(btn => {
  btn.addEventListener('click', () => {
    chatInput.value = btn.textContent.trim();
    openChat();
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
