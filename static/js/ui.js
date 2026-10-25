/* Small DOM helpers. User-supplied text is only ever inserted via textContent. */
window.UI = (function () {
  'use strict';

  function el(tag, attrs, children) {
    var node = document.createElement(tag);
    if (attrs) {
      Object.keys(attrs).forEach(function (key) {
        var value = attrs[key];
        if (value === null || value === undefined || value === false) return;
        if (key === 'text') {
          node.textContent = value;
        } else if (key === 'class') {
          node.className = value;
        } else if (key.slice(0, 2) === 'on' && typeof value === 'function') {
          node.addEventListener(key.slice(2).toLowerCase(), value);
        } else {
          node.setAttribute(key, value === true ? '' : value);
        }
      });
    }
    (children || []).forEach(function (child) {
      if (child === null || child === undefined) return;
      node.appendChild(typeof child === 'string' ? document.createTextNode(child) : child);
    });
    return node;
  }

  function text(value) {
    return document.createTextNode(value === null || value === undefined ? '' : String(value));
  }

  var toastTimer = null;
  function toast(message, kind) {
    var node = document.getElementById('toast');
    if (!node) return;
    node.textContent = message;
    node.dataset.kind = kind || 'info';
    node.hidden = false;
    if (toastTimer) window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(function () { node.hidden = true; }, 3500);
  }

  function formatDate(iso) {
    if (!iso) return '—';
    var date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '—';
    return date.toLocaleString('ru-RU', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit'
    });
  }

  function openDialog(dialog) {
    if (typeof dialog.showModal === 'function') dialog.showModal();
    else dialog.setAttribute('open', '');
  }

  function closeDialog(dialog) {
    if (typeof dialog.close === 'function' && dialog.open) dialog.close();
    else dialog.removeAttribute('open');
  }

  function confirmDialog(dialog, text) {
    var message = document.getElementById('confirm-text');
    if (message) message.textContent = text;
    var okBtn = document.getElementById('confirm-ok-btn');
    var cancelBtn = document.getElementById('confirm-cancel-btn');
    return new Promise(function (resolve) {
      function finish(result) {
        okBtn.removeEventListener('click', onOk);
        cancelBtn.removeEventListener('click', onCancel);
        dialog.removeEventListener('cancel', onCancel);
        closeDialog(dialog);
        resolve(result);
      }
      function onOk() { finish(true); }
      function onCancel() { finish(false); }
      okBtn.addEventListener('click', onOk);
      cancelBtn.addEventListener('click', onCancel);
      dialog.addEventListener('cancel', onCancel);
      openDialog(dialog);
      okBtn.focus();
    });
  }

  function clearErrors(scope) {
    scope.querySelectorAll('.field-error').forEach(function (node) {
      node.hidden = true;
      node.textContent = '';
    });
    var formError = scope.querySelector('.form-error');
    if (formError) {
      formError.hidden = true;
      formError.textContent = '';
    }
  }

  /* Map DRF error payloads ({field: [messages]} or {detail}) onto the form. */
  function showErrors(scope, data, fallbackMessage) {
    clearErrors(scope);
    var fields = 0;
    if (data && typeof data === 'object') {
      Object.keys(data).forEach(function (key) {
        var target = scope.querySelector('[data-error-for="' + key + '"]');
        if (!target) return;
        var value = data[key];
        var message = Array.isArray(value) ? value.join(' ') : String(value);
        target.textContent = message;
        target.hidden = false;
        fields += 1;
      });
    }
    if (!fields) {
      var formError = scope.querySelector('.form-error');
      var message = fallbackMessage;
      if (!message && data) {
        if (typeof data.detail === 'string') message = data.detail;
        else if (Array.isArray(data.detail)) message = data.detail.join(' ');
      }
      if (!message) message = 'Не удалось выполнить запрос.';
      if (formError) {
        formError.textContent = message;
        formError.hidden = false;
      }
    }
    return fields;
  }

  function setLoading(button, loading, loadingText) {
    if (!button) return;
    if (loading) {
      button.dataset.label = button.textContent;
      button.textContent = loadingText || 'Подождите…';
      button.disabled = true;
    } else {
      if (button.dataset.label) button.textContent = button.dataset.label;
      button.disabled = false;
    }
  }

  function status(node, message) {
    if (node) node.textContent = message || '';
  }

  return {
    el: el,
    text: text,
    toast: toast,
    formatDate: formatDate,
    openDialog: openDialog,
    closeDialog: closeDialog,
    confirmDialog: confirmDialog,
    clearErrors: clearErrors,
    showErrors: showErrors,
    setLoading: setLoading,
    status: status
  };
})();
