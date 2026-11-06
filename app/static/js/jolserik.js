'use strict';

(() => {
  const { $, api, tr } = window.Jol;
  const form = $('chat-form');
  if (!form) return;
  const input = $('chat-input');
  const log = $('chat-log');
  const send = form.querySelector('button[type=submit]');
  const turns = [];

  function append(text, role) {
    const bubble = document.createElement('p');
    bubble.className = 'chat-message chat-' + role;
    bubble.textContent = text;
    log.append(bubble);
    log.scrollTop = log.scrollHeight;
    return bubble;
  }

  form.addEventListener('submit', async event => {
    event.preventDefault();
    const message = input.value.trim();
    if (!message || send.disabled) return;
    input.value = '';
    send.disabled = true;
    append(message, 'user');
    const pending = append(tr('Jolserik жауап дайындауда…'), 'model');
    try {
      const history = [...turns.slice(-8), {text: message}];
      const {reply} = await api('/api/assistant', {method:'POST', body:{turns:history}});
      pending.textContent = reply;
      turns.push({text:message}, {text:reply});
      if (turns.length > 8) turns.splice(0, turns.length - 8);
    } catch (error) {
      pending.textContent = error.message;
      input.value = message;
    } finally {
      send.disabled = false;
      log.scrollTop = log.scrollHeight;
      input.focus();
    }
  });

  document.querySelectorAll('[data-chat-prompt]').forEach(button => {
    button.addEventListener('click', () => {
      if (send.disabled) return;
      input.value = button.dataset.chatPrompt;
      form.requestSubmit();
    });
  });
})();
