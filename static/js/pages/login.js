/* Login page: POST /api/auth/token/, store tokens, go to the workspace. */
(function () {
  'use strict';

  var form = document.getElementById('login-form');
  var errorBox = document.getElementById('login-error');
  var submitBtn = document.getElementById('login-submit');
  var passwordInput = document.getElementById('password');

  if (API.isLoggedIn()) {
    window.location.href = '/';
    return;
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    errorBox.hidden = true;

    var username = form.username.value.trim();
    var password = form.password.value;
    if (!username || !password) {
      showError('Укажите имя пользователя и пароль.');
      return;
    }

    UI.setLoading(submitBtn, true, 'Входим…');
    API.login(username, password)
      .then(function () {
        passwordInput.value = '';
        window.location.href = '/';
      })
      .catch(function (error) {
        if (error.status === 401 || error.status === 400) {
          showError('Неверное имя пользователя или пароль.');
        } else if (error.network) {
          showError(error.message);
        } else if (error.data && error.data.detail) {
          showError(String(error.data.detail));
        } else {
          showError('Не удалось войти. Повторите попытку.');
        }
        passwordInput.value = '';
        passwordInput.focus();
      })
      .then(function () {
        UI.setLoading(submitBtn, false);
      });
  });
})();
