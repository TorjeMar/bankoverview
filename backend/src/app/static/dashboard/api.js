/* Bankoverview API client.
 *
 * Reads use the Postgres-backed cache. Mutations include the CSRF cookie in
 * X-CSRF-Token; the HTTP-only session cookie is sent by the browser.
 */
(function () {
  const BASE = '/api/v1';

  /* ---------- live ---------- */

  async function req(path, init) {
    const csrf = document.cookie.split('; ').find((part) => part.startsWith('csrf_token='));
    const headers = { Accept: 'application/json', ...((init && init.headers) || {}) };
    if (csrf && init && !['GET', 'HEAD'].includes(init.method || 'GET')) {
      headers['X-CSRF-Token'] = decodeURIComponent(csrf.split('=').slice(1).join('='));
    }
    const res = await fetch(BASE + path, {
      credentials: 'include',
      ...init,
      headers,
    });
    if (!res.ok) {
      const err = new Error('HTTP ' + res.status);
      err.status = res.status;
      try {
        const body = await res.json();
        err.detail = body.error ? body.error.message : body.detail;
        err.code = body.error ? body.error.code : null;
        err.requestId = body.error ? body.error.request_id : null;
      } catch (_) {}
      throw err;
    }
    return res.status === 204 ? null : res.json();
  }

  const live = {
    mode: 'live',
    loginUrl: BASE + '/login',
    me: () => req('/me'),
    overview: (days) => req('/overview?days=' + encodeURIComponent(days || 30)),
    sync: () => req('/sync', { method: 'POST' }),
    logout: () => req('/logout', { method: 'POST' }),
    listAccounts: () => req('/accounts'),
    getAccount: (id) => req('/accounts/' + encodeURIComponent(id)),
    getBalances: (id) => req('/accounts/' + encodeURIComponent(id) + '/balances'),
    getTransactions: (id) => req('/accounts/' + encodeURIComponent(id) + '/transactions'),
    startConnection: () => req('/connections/start', { method: 'POST' }),
    revokeConnection: () => req('/connections/revoke', { method: 'DELETE' }),
  };

  window.BankApi = {
    create() { return live; },
    live,
  };
})();
