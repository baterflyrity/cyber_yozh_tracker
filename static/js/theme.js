/* Theme mode handling: system / light / dark with persistence in localStorage. */
(function () {
  'use strict';

  var STORAGE_KEY = 'cyberyozh.theme';
  var VALID = { system: true, light: true, dark: true };

  function readMode() {
    try {
      var value = window.localStorage.getItem(STORAGE_KEY);
      return VALID[value] ? value : 'system';
    } catch (e) {
      return 'system';
    }
  }

  function resolve(mode) {
    if (mode !== 'system') return mode;
    return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
      ? 'dark'
      : 'light';
  }

  function apply(mode, persist) {
    if (!VALID[mode]) mode = 'system';
    document.documentElement.dataset.theme = resolve(mode);
    document.documentElement.dataset.themeMode = mode;
    if (persist) {
      try { window.localStorage.setItem(STORAGE_KEY, mode); } catch (e) { /* storage disabled */ }
    }
    var select = document.getElementById('theme-select');
    if (select && select.value !== mode) select.value = mode;
  }

  // React to OS-level colour scheme changes while the page is open.
  var media = window.matchMedia ? window.matchMedia('(prefers-color-scheme: dark)') : null;
  function onSystemChange() {
    if (readMode() === 'system') apply('system', false);
  }
  if (media) {
    if (media.addEventListener) media.addEventListener('change', onSystemChange);
    else if (media.addListener) media.addListener(onSystemChange);
  }

  var select = document.getElementById('theme-select');
  if (select) {
    select.value = readMode();
    select.addEventListener('change', function () { apply(select.value, true); });
  }

  apply(readMode(), false);

  window.Theme = { apply: apply, read: readMode };
})();
