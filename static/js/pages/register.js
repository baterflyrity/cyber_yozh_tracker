/* Registration page: POST /api/auth/register/ then sign in automatically. */
(function () {
  'use strict';

  var form = document.getElementById('register-form');
  var errorBox = document.getElementById('register-error');
  var submitBtn = document.getElementById('register-submit');
  var passwordInput = document.getElementById('password');

  if (API.isLoggedIn()) {
    window.location.href = '/';
    return;
  }

  form.addEventListener('submit', function (event) {
    event.preventDefault();
    UI.clearErrors(form);

    var payload = {
      username: form.username.value.trim(),
      password: passwordInput.value
    };
    var email = form.email.value.trim();
    if (email) payload.email = email;

    if (!payload.username) {
      UI.showErrors(form, { username: ['Укажите имя пользователя.'] });
      form.username.focus();
      return;
    }
    if (!payload.password) {
      UI.showErrors(form, { password: ['Укажите пароль.'] });
      passwordInput.focus();
      return;
    }

    UI.setLoading(submitBtn, true, 'Создаём…');
    API.register(payload)
      .then(function () {
        return API.login(payload.username, payload.password);
      })
      .then(function () {
        passwordInput.value = '';
        window.location.href = '/';
      })
      .catch(function (error) {
        if (error.network) {
          UI.showErrors(form, null, error.message);
        } else {
          UI.showErrors(form, error.data, 'Не удалось зарегистрироваться.');
        }
        passwordInput.value = '';
      })
      .then(function () {
        UI.setLoading(submitBtn, false);
      });
  });
})();
