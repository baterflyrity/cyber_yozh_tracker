/* Dashboard: task list with search/filter/sorting and the create dialog. */
(function () {
  'use strict';

  var listEl = document.getElementById('task-list');
  var statusEl = document.getElementById('list-status');
  var emptyEl = document.getElementById('empty-state');
  var createBtn = document.getElementById('create-task-btn');
  var filtersForm = document.getElementById('filters');
  var searchInput = document.getElementById('search-input');
  var statusFilter = document.getElementById('status-filter');
  var orderingSelect = document.getElementById('ordering-select');

  var dialog = document.getElementById('task-dialog');
  var taskForm = document.getElementById('task-form');
  var saveBtn = document.getElementById('task-save-btn');
  var cancelBtn = document.getElementById('task-cancel-btn');
  var assigneeSelect = document.getElementById('task-assignee');

  var searchTimer = null;

  /* --- state helpers ---------------------------------------------------- */

  function setEmpty(title, message, action) {
    emptyEl.innerHTML = '';
    emptyEl.appendChild(UI.el('p', { class: 'empty-title', text: title }));
    emptyEl.appendChild(UI.el('p', { class: 'muted', text: message }));
    if (action) emptyEl.appendChild(action);
    emptyEl.hidden = false;
  }

  function requireAuth() {
    if (API.isLoggedIn()) return true;
    createBtn.hidden = true;
    filtersForm.hidden = true;
    listEl.innerHTML = '';
    setEmpty(
      'Войдите, чтобы увидеть задачи',
      'Список задач доступен только после входа в аккаунт.',
      UI.el('a', { class: 'btn btn-primary', href: '/login/', text: 'Войти' })
    );
    UI.status(statusEl, '');
    return false;
  }

  /* --- data loading ----------------------------------------------------- */

  function buildQuery() {
    var params = [];
    if (searchInput.value.trim()) {
      params.push('search=' + encodeURIComponent(searchInput.value.trim()));
    }
    if (statusFilter.value) params.push('is_completed=' + statusFilter.value);
    if (orderingSelect.value) params.push('ordering=' + encodeURIComponent(orderingSelect.value));
    params.push('page_size=20');
    return '/api/tasks/?' + params.join('&');
  }

  function taskCard(task) {
    var done = Boolean(task.is_completed);
    var assigneeName = task.assigned_to ? task.assigned_to.username : 'не назначен';
    var meta = UI.el('div', { class: 'task-meta' }, [
      UI.el('span', { text: 'Автор: ' + (task.created_by ? task.created_by.username : '—') }),
      UI.el('span', { text: 'Исполнитель: ' + assigneeName }),
      UI.el('span', { text: 'Изменена: ' + UI.formatDate(task.updated_at) })
    ]);
    var description = (task.description || '').trim();

    return UI.el('article', { class: 'task-card' }, [
      UI.el('div', { class: 'detail-title-row' }, [
        UI.el('h2', {}, [
          UI.el('a', { href: '/tasks/' + task.id + '/', text: task.title })
        ]),
        UI.el('span', {
          class: 'badge ' + (done ? 'badge-done' : 'badge-open'),
          text: done ? 'Выполнена' : 'Не выполнена'
        })
      ]),
      description ? UI.el('p', { class: 'task-desc', text: description }) : null,
      meta
    ]);
  }

  function render(tasks) {
    listEl.innerHTML = '';
    tasks.forEach(function (task) { listEl.appendChild(taskCard(task)); });

    if (!tasks.length) {
      setEmpty('Ничего не найдено', 'Попробуйте изменить поиск или фильтр статуса.');
    } else {
      emptyEl.hidden = true;
    }
  }

  function showError(error) {
    listEl.innerHTML = '';
    var message = 'Не удалось загрузить задачи.';
    if (error && error.network) message = error.message;
    else if (error && error.status === 401) message = 'Сессия истекла, войдите заново.';
    else if (error && error.data && error.data.detail) message = String(error.data.detail);

    setEmpty(
      'Ошибка загрузки',
      message,
      UI.el('button', {
        class: 'btn btn-quiet',
        type: 'button',
        text: 'Повторить',
        onclick: load
      })
    );
    UI.status(statusEl, '');
  }

  function load() {
    if (!requireAuth()) return;
    listEl.setAttribute('aria-busy', 'true');
    UI.status(statusEl, 'Загружаем задачи…');
    emptyEl.hidden = true;

    API.request(buildQuery())
      .then(function (data) {
        var tasks = (data && data.results) || [];
        render(tasks);
        var count = (data && data.count !== undefined) ? data.count : tasks.length;
        UI.status(statusEl, count ? 'Найдено задач: ' + count : '');
      })
      .catch(showError)
      .then(function () { listEl.setAttribute('aria-busy', 'false'); });
  }

  /* --- assignee directory ---------------------------------------------- */

  function loadAssignees(select) {
    return API.request('/api/users/?page_size=100')
      .then(function (data) {
        var users = (data && data.results) || [];
        while (select.options.length > 1) select.remove(1);
        users.forEach(function (user) {
          select.appendChild(UI.el('option', { value: user.id, text: user.username }));
        });
        return users;
      })
      .catch(function () { /* keep the "not assigned" option only */ });
  }

  /* --- create dialog ---------------------------------------------------- */

  function openCreateDialog() {
    UI.clearErrors(taskForm);
    taskForm.reset();
    UI.status(document.getElementById('task-form-error'), '');
    document.getElementById('task-form-error').hidden = true;
    UI.openDialog(dialog);
    document.getElementById('task-title').focus();
    loadAssignees(assigneeSelect);
  }

  createBtn.addEventListener('click', openCreateDialog);
  cancelBtn.addEventListener('click', function () { UI.closeDialog(dialog); });

  taskForm.addEventListener('submit', function (event) {
    event.preventDefault();
    UI.clearErrors(taskForm);

    var payload = {
      title: document.getElementById('task-title').value.trim(),
      description: document.getElementById('task-description').value,
      assigned_to: assigneeSelect.value ? Number(assigneeSelect.value) : null
    };
    if (!payload.title) {
      UI.showErrors(taskForm, { title: ['Укажите заголовок задачи.'] });
      return;
    }

    UI.setLoading(saveBtn, true, 'Сохраняем…');
    API.request('/api/tasks/', { method: 'POST', body: payload })
      .then(function () {
        UI.closeDialog(dialog);
        UI.toast('Задача создана', 'success');
        load();
      })
      .catch(function (error) {
        if (error.network) UI.showErrors(taskForm, null, error.message);
        else UI.showErrors(taskForm, error.data, 'Не удалось создать задачу.');
      })
      .then(function () { UI.setLoading(saveBtn, false); });
  });

  /* --- filters ---------------------------------------------------------- */

  searchInput.addEventListener('input', function () {
    if (searchTimer) window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(load, 300);
  });
  statusFilter.addEventListener('change', load);
  orderingSelect.addEventListener('change', load);
  filtersForm.addEventListener('submit', function (event) {
    event.preventDefault();
    load();
  });

  /* --- start ------------------------------------------------------------ */

  API.syncAuthUI();
  load();
})();
