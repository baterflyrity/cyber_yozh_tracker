/* REST API client: JWT storage (sessionStorage), single refresh retry,
   network/HTTP error handling and header auth state. */
window.API = (function () {
  'use strict';

  var ACCESS_KEY = 'cyberyozh.access';
  var REFRESH_KEY = 'cyberyozh.refresh';

  function getAccess() { return window.sessionStorage.getItem(ACCESS_KEY); }
  function getRefresh() { return window.sessionStorage.getItem(REFRESH_KEY); }

  function setTokens(access, refresh) {
    if (access) window.sessionStorage.setItem(ACCESS_KEY, access);
    if (refresh) window.sessionStorage.setItem(REFRESH_KEY, refresh);
  }

  function clearTokens() {
    window.sessionStorage.removeItem(ACCESS_KEY);
    window.sessionStorage.removeItem(REFRESH_KEY);
  }

  function isLoggedIn() { return Boolean(getAccess() || getRefresh()); }

  function onUnauthorized() {
    clearTokens();
    var path = window.location.pathname;
    if (path !== '/login/' && path !== '/register/') {
      window.location.href = '/login/';
    }
  }

  function parseResponse(res) {
    return res.text().then(function (raw) {
      var data = null;
      if (raw) {
        try { data = JSON.parse(raw); } catch (e) { data = null; }
      }
      if (!res.ok) {
        var error = new Error('HTTP ' + res.status);
        error.status = res.status;
        error.data = data;
        throw error;
      }
      return data;
    });
  }

  function tryRefresh() {
    var refresh = getRefresh();
    if (!refresh) return Promise.resolve(false);
    return fetch('/api/auth/token/refresh/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      body: JSON.stringify({ refresh: refresh })
    }).then(function (res) {
      if (!res.ok) return false;
      return res.json().then(function (data) {
        if (data && data.access) {
          setTokens(data.access, null);
          return true;
        }
        return false;
      });
    }).catch(function () { return false; });
  }

  function request(path, options) {
    options = options || {};
    var headers = { 'Accept': 'application/json' };
    var body = options.body;

    if (body !== undefined && body !== null) {
      headers['Content-Type'] = 'application/json';
      body = JSON.stringify(body);
    }
    Object.keys(options.headers || {}).forEach(function (key) {
      headers[key] = options.headers[key];
    });

    var needsAuth = options.auth !== false;
    if (needsAuth && getAccess()) {
      headers['Authorization'] = 'Bearer ' + getAccess();
    }

    return fetch(path, {
      method: options.method || 'GET',
      headers: headers,
      body: body
    }).catch(function () {
      var error = new Error('Не удалось соединиться с сервером.');
      error.network = true;
      throw error;
    }).then(function (res) {
      if (res.status === 401 && needsAuth && !options._retried) {
        // At most one refresh attempt and one replay of the original request.
        return tryRefresh().then(function (refreshed) {
          if (refreshed) {
            var retry = Object.assign({}, options, { _retried: true });
            return request(path, retry);
          }
          onUnauthorized();
          var error = new Error('Сессия истекла, войдите заново.');
          error.status = 401;
          throw error;
        });
      }
      return parseResponse(res);
    });
  }

  function login(username, password) {
    return request('/api/auth/token/', {
      method: 'POST',
      auth: false,
      body: { username: username, password: password }
    }).then(function (data) {
      setTokens(data.access, data.refresh);
      return data;
    });
  }

  function register(payload) {
    return request('/api/auth/register/', { method: 'POST', auth: false, body: payload });
  }

  function logout() {
    clearTokens();
    window.location.href = '/login/';
  }

  function me() { return request('/api/auth/me/'); }

  function syncAuthUI() {
    var userChip = document.getElementById('current-user');
    var logoutBtn = document.getElementById('logout-btn');
    var loginLink = document.getElementById('login-link');
    var registerLink = document.getElementById('register-link');
    var authed = isLoggedIn();

    if (logoutBtn) logoutBtn.hidden = !authed;
    if (userChip) userChip.hidden = !authed;
    if (loginLink) loginLink.hidden = authed;
    if (registerLink) registerLink.hidden = authed;

    if (authed && userChip) {
      me().then(function (user) {
        userChip.textContent = user.username;
        userChip.hidden = false;
      }).catch(function () { /* handled by the refresh flow */ });
    }
    if (logoutBtn && !logoutBtn.dataset.bound) {
      logoutBtn.dataset.bound = '1';
      logoutBtn.addEventListener('click', logout);
    }
  }

  return {
    request: request,
    login: login,
    register: register,
    logout: logout,
    me: me,
    isLoggedIn: isLoggedIn,
    setTokens: setTokens,
    clearTokens: clearTokens,
    syncAuthUI: syncAuthUI
  };
})();
