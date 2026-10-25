/* Task detail: fields, role-based actions, assignment and comments. */
(function () {
  'use strict';

  var taskId = window.__TASK_ID__;
  var detailEl = document.getElementById('task-detail');
  var statusLine = document.getElementById('detail-status');

  var toggleBtn = document.getElementById('toggle-status-btn');
  var editBtn = document.getElementById('edit-task-btn');
  var deleteBtn = document.getElementById('delete-task-btn');
  var assignBlock = document.getElementById('assign-block');
  var assignForm = document.getElementById('assign-form');
  var assignSelect = document.getElementById('assign-select');
  var assignError = document.getElementById('assign-error');

  var editDialog = document.getElementById('edit-dialog');
  var editForm = document.getElementById('edit-form');
  var editSaveBtn = document.getElementById('edit-save-btn');
  var editCancelBtn = document.getElementById('edit-cancel-btn');
  var confirmDialogEl = document.getElementById('confirm-dialog');

  var commentForm = document.getElementById('comment-form');
  var commentList = document.getElementById('comment-list');
  var commentsEmpty = document.getElementById('comments-empty');
  var commentSubmit = document.getElementById('comment-submit');

  var task = null;
  var currentUser = null;

  function isCreator() {
    return Boolean(task && currentUser && task.created_by && task.created_by.id === currentUser.id);
  }

  function isAssignee() {
    return Boolean(task && currentUser && task.assigned_to && task.assigned_to.id === currentUser.id);
  }

  function setDisabled(button, disabled) {
    button.disabled = Boolean(disabled);
  }

  /* --- rendering -------------------------------------------------------- */

  function renderTask() {
    document.getElementById('detail-title').textContent = task.title;

    var done = Boolean(task.is_completed);
    var badge = document.getElementById('detail-status-badge');
    badge.textContent = done ? 'Выполнена' : 'Не выполнена';
    badge.className = 'badge ' + (done ? 'badge-done' : 'badge-open');

    var description = document.getElementById('detail-description');
    description.textContent = (task.description || '').trim() || 'Описание не заполнено.';

    document.getElementById('detail-author').textContent =
      task.created_by ? task.created_by.username : '—';
    document.getElementById('detail-assignee').textContent =
      task.assigned_to ? task.assigned_to.username : 'не назначен';
    document.getElementById('detail-created').textContent = UI.formatDate(task.created_at);
    document.getElementById('detail-updated').textContent = UI.formatDate(task.updated_at);

    document.title = task.title + ' — CyberYozh';

    var creator = isCreator();
    var participant = creator || isAssignee();

    toggleBtn.hidden = !participant;
    toggleBtn.textContent = done ? 'Снять отметку о выполнении' : 'Отметить выполненной';
    editBtn.hidden = !creator;
    deleteBtn.hidden = !creator;
    assignBlock.hidden = !creator;
  }

  function renderError(error) {
    detailEl.hidden = true;
    var message = 'Не удалось загрузить задачу.';
    if (error && error.status === 404) message = 'Задача не найдена или она вам недоступна.';
    else if (error && error.status === 401) message = 'Сессия истекла, войдите заново.';
    else if (error && error.data && error.data.detail) message = String(error.data.detail);
    else if (error && error.network) message = error.message;
    UI.status(statusLine, message);
  }

  function loadTask() {
    UI.status(statusLine, 'Загружаем задачу…');
    API.request('/api/tasks/' + taskId + '/')
      .then(function (data) {
        task = data;
        detailEl.hidden = false;
        UI.status(statusLine, '');
        renderTask();
        loadComments();
        if (isCreator()) loadAssignees();
      })
      .catch(renderError);
  }

  function loadAssignees() {
    API.request('/api/users/?page_size=100')
      .then(function (data) {
        var users = (data && data.results) || [];
        while (assignSelect.options.length > 1) assignSelect.remove(1);
        users.forEach(function (user) {
          assignSelect.appendChild(UI.el('option', { value: user.id, text: user.username }));
        });
        assignSelect.value = task.assigned_to ? String(task.assigned_to.id) : '';
      })
      .catch(function () { /* directory unavailable: keep "not assigned" */ });
  }

  /* --- task actions ----------------------------------------------------- */

  function patch(fields, onSuccess, errorBox) {
    API.request('/api/tasks/' + taskId + '/', { method: 'PATCH', body: fields })
      .then(function (data) {
        task = data;
        renderTask();
        if (errorBox) {
          errorBox.hidden = true;
          errorBox.textContent = '';
        }
        onSuccess();
      })
      .catch(function (error) {
        if (errorBox) {
          var message = 'Не удалось сохранить изменения.';
          if (error.network) message = error.message;
          else if (error.data && error.data.detail) {
            message = Array.isArray(error.data.detail)
              ? error.data.detail.join(' ') : String(error.data.detail);
          } else if (error.data) {
            var parts = [];
            Object.keys(error.data).forEach(function (key) {
              var value = error.data[key];
              parts.push(key + ': ' + (Array.isArray(value) ? value.join(' ') : String(value)));
            });
            if (parts.length) message = parts.join(' ');
          }
          errorBox.textContent = message;
          errorBox.hidden = false;
        } else {
          UI.toast('Не удалось сохранить изменения', 'error');
        }
      });
  }

  toggleBtn.addEventListener('click', function () {
    setDisabled(toggleBtn, true);
    patch({ is_completed: !task.is_completed }, function () {
      UI.toast(task.is_completed ? 'Задача выполнена' : 'Задача снова открыта', 'success');
      setDisabled(toggleBtn, false);
    }, null);
    window.setTimeout(function () { setDisabled(toggleBtn, false); }, 800);
  });

  editBtn.addEventListener('click', function () {
    UI.clearErrors(editForm);
    document.getElementById('edit-title').value = task.title;
    document.getElementById('edit-description').value = task.description || '';
    UI.openDialog(editDialog);
    document.getElementById('edit-title').focus();
  });

  editCancelBtn.addEventListener('click', function () { UI.closeDialog(editDialog); });

  editForm.addEventListener('submit', function (event) {
    event.preventDefault();
    UI.clearErrors(editForm);
    var payload = {
      title: document.getElementById('edit-title').value.trim(),
      description: document.getElementById('edit-description').value
    };
    if (!payload.title) {
      UI.showErrors(editForm, { title: ['Укажите заголовок задачи.'] });
      return;
    }
    UI.setLoading(editSaveBtn, true, 'Сохраняем…');
    API.request('/api/tasks/' + taskId + '/', { method: 'PATCH', body: payload })
      .then(function (updated) {
        // Re-render from the server response so the page never shows stale data.
        task = updated;
        UI.closeDialog(editDialog);
        UI.toast('Задача обновлена', 'success');
        renderTask();
      })
      .catch(function (error) {
        if (error.network) UI.showErrors(editForm, null, error.message);
        else UI.showErrors(editForm, error.data, 'Не удалось сохранить задачу.');
      })
      .then(function () { UI.setLoading(editSaveBtn, false); });
  });

  deleteBtn.addEventListener('click', function () {
    UI.confirmDialog(confirmDialogEl, 'Удалить задачу и все её комментарии?')
      .then(function (confirmed) {
        if (!confirmed) return;
        API.request('/api/tasks/' + taskId + '/', { method: 'DELETE' })
          .then(function () {
            UI.toast('Задача удалена', 'success');
            window.location.href = '/';
          })
          .catch(function () { UI.toast('Не удалось удалить задачу', 'error'); });
      });
  });

  assignForm.addEventListener('submit', function (event) {
    event.preventDefault();
    assignError.hidden = true;
    var value = assignSelect.value ? Number(assignSelect.value) : null;
    patch({ assigned_to: value }, function () {
      UI.toast('Назначение сохранено', 'success');
      renderTask();
    }, assignError);
  });

  /* --- comments --------------------------------------------------------- */

  function commentItem(comment) {
    var isMine = currentUser && comment.author && comment.author.id === currentUser.id;
    var head = UI.el('div', { class: 'comment-head' }, [
      UI.el('span', { class: 'comment-author', text: comment.author ? comment.author.username : '—' }),
      UI.el('span', { text: UI.formatDate(comment.created_at) })
    ]);
    var body = UI.el('p', { class: 'comment-body', text: comment.body });
    var item = UI.el('li', { class: 'comment' }, [head, body]);

    if (isMine) {
      var actions = UI.el('div', { class: 'comment-actions' });
      var editButton = UI.el('button', {
        class: 'btn btn-quiet btn-small', type: 'button', text: 'Изменить'
      });
      var deleteButton = UI.el('button', {
        class: 'btn btn-danger btn-small', type: 'button', text: 'Удалить'
      });

      editButton.addEventListener('click', function () {
        var textarea = UI.el('textarea', { class: 'control', rows: '3' });
        textarea.value = comment.body;
        var error = UI.el('p', { class: 'field-error', hidden: true });
        var save = UI.el('button', { class: 'btn btn-primary btn-small', type: 'button', text: 'Сохранить' });
        var cancel = UI.el('button', { class: 'btn btn-quiet btn-small', type: 'button', text: 'Отмена' });
        var editor = UI.el('div', { class: 'form' }, [textarea, error,
          UI.el('div', { class: 'form-actions' }, [save, cancel])]);

        body.replaceWith(editor);
        actions.hidden = true;
        textarea.focus();

        cancel.addEventListener('click', function () {
          editor.replaceWith(body);
          actions.hidden = false;
        });
        save.addEventListener('click', function () {
          setDisabled(save, true);
          API.request('/api/tasks/' + taskId + '/comments/' + comment.id + '/', {
            method: 'PATCH',
            body: { body: textarea.value }
          }).then(function (updated) {
            comment.body = updated.body;
            editor.replaceWith(body);
            body.textContent = updated.body;
            actions.hidden = false;
            UI.toast('Комментарий обновлён', 'success');
          }).catch(function (err) {
            var message = 'Не удалось обновить комментарий.';
            if (err.data && err.data.detail) {
              message = Array.isArray(err.data.detail)
                ? err.data.detail.join(' ') : String(err.data.detail);
            }
            error.textContent = message;
            error.hidden = false;
            setDisabled(save, false);
          });
        });
      });

      deleteButton.addEventListener('click', function () {
        UI.confirmDialog(confirmDialogEl, 'Удалить комментарий?').then(function (confirmed) {
          if (!confirmed) return;
          API.request('/api/tasks/' + taskId + '/comments/' + comment.id + '/', {
            method: 'DELETE'
          }).then(function () {
            item.remove();
            updateCommentsEmptyState();
            UI.toast('Комментарий удалён', 'success');
          }).catch(function () {
            UI.toast('Не удалось удалить комментарий', 'error');
          });
        });
      });

      actions.appendChild(editButton);
      actions.appendChild(deleteButton);
      item.appendChild(actions);
    }
    return item;
  }

  function updateCommentsEmptyState() {
    commentsEmpty.hidden = commentList.children.length > 0;
  }

  function loadComments() {
    API.request('/api/tasks/' + taskId + '/comments/?page_size=100')
      .then(function (data) {
        var comments = (data && data.results) || [];
        commentList.innerHTML = '';
        comments.forEach(function (comment) {
          commentList.appendChild(commentItem(comment));
        });
        updateCommentsEmptyState();
      })
      .catch(function () {
        UI.status(statusLine, 'Не удалось загрузить комментарии.');
      });
  }

  commentForm.addEventListener('submit', function (event) {
    event.preventDefault();
    var textarea = document.getElementById('comment-body');
    var error = document.getElementById('comment-error');
    error.hidden = true;
    var body = textarea.value.trim();
    if (!body) {
      error.textContent = 'Введите текст комментария.';
      error.hidden = false;
      textarea.focus();
      return;
    }

    UI.setLoading(commentSubmit, true, 'Отправляем…');
    API.request('/api/tasks/' + taskId + '/comments/', {
      method: 'POST',
      body: { body: body }
    }).then(function (comment) {
      textarea.value = '';
      commentList.appendChild(commentItem(comment));
      updateCommentsEmptyState();
      UI.toast('Комментарий добавлен', 'success');
    }).catch(function (err) {
      if (err.data && (err.data.body || err.data.detail)) {
        var value = err.data.body || err.data.detail;
        error.textContent = Array.isArray(value) ? value.join(' ') : String(value);
      } else if (err.network) {
        error.textContent = err.message;
      } else {
        error.textContent = 'Не удалось добавить комментарий.';
      }
      error.hidden = false;
    }).then(function () {
      UI.setLoading(commentSubmit, false);
    });
  });

  /* --- start ------------------------------------------------------------ */

  API.syncAuthUI();

  API.me().then(function (user) {
    currentUser = user;
    loadTask();
  }).catch(function (error) {
    if (error.status === 401 || error.network) {
      renderError(error);
    } else {
      currentUser = null;
      loadTask();
    }
  });
})();
