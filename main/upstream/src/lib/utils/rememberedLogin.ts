export const REMEMBERED_LOGIN = 'owui-hf.rememberedLogin.v1';
export const LOGOUT_EVENT = 'owui-hf.logout.v1';
export const storageGet = (key: string): string | null => {
    try { return localStorage.getItem(key); } catch { return null; }
};
export const storageSet = (key: string, value: string) => {
    try { localStorage.setItem(key, value); } catch { /* Cookies still support manual login. */ }
};
export const storageRemove = (key: string) => {
    try { localStorage.removeItem(key); } catch { /* Storage may be blocked. */ }
};
export function readRememberedLogin(): { email: string; password: string } | null {
    try {
        const value = JSON.parse(storageGet(REMEMBERED_LOGIN) || 'null');
        if (value && typeof value.email === 'string' && typeof value.password === 'string' && value.email && value.password) return value;
    } catch { /* Malformed records never authenticate. */ }
    storageRemove(REMEMBERED_LOGIN);
    return null;
}
export function rememberLogin(email: string, password: string, enabled: boolean) {
    if (enabled) storageSet(REMEMBERED_LOGIN, JSON.stringify({ email, password }));
    else storageRemove(REMEMBERED_LOGIN);
}
export function clearLogin(broadcast = true) {
    storageRemove(REMEMBERED_LOGIN);
    storageRemove('token');
    if (broadcast) storageSet(LOGOUT_EVENT, String(Date.now()));
}
export function localRedirect(path: string | null): string {
    if (!path || !path.startsWith('/') || path.startsWith('//') || /[\\\u0000-\u0020]/.test(path)) return '/';
    try {
        const url = new URL(path, 'https://local.invalid');
        return url.origin === 'https://local.invalid' ? url.pathname + url.search + url.hash : '/';
    } catch { return '/'; }
}
export async function rememberedSignIn(email: string, password: string) {
    const response = await fetch('/api/v1/auths/signin', { method: 'POST', credentials: 'include',
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email, password }) });
    if (!response.ok) {
        if ([400, 401, 403].includes(response.status)) { storageRemove(REMEMBERED_LOGIN); storageRemove('token'); }
        throw new Error(response.status === 429 ? 'Too many attempts. Retry in one minute.' :
            response.status >= 500 ? 'Login is temporarily unavailable. Please retry.' : 'Login failed. Check your credentials and retry.');
    }
    return response.json();
}
