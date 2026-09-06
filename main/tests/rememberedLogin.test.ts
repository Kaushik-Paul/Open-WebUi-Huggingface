import { describe, it, expect, beforeEach, vi } from '../upstream/node_modules/vitest/dist/index.js';
import { REMEMBERED_LOGIN, localRedirect, readRememberedLogin, rememberLogin, clearLogin, rememberedSignIn } from '../upstream/src/lib/utils/rememberedLogin';
const values = new Map<string,string>();
beforeEach(() => {
    values.clear();
    vi.stubGlobal('localStorage', { getItem: (key: string) => values.get(key) ?? null,
        setItem: (key: string, value: string) => values.set(key,value), removeItem: (key: string) => values.delete(key) });
});
describe('remembered credentials', () => {
    it('validates local redirects', () => {
        for (const value of ['https://evil.example','//evil.example','/\\evil.example','/\nevil.example']) expect(localRedirect(value)).toBe('/');
        expect(localRedirect('/c/123?q=1')).toBe('/c/123?q=1');
    });
    it('handles corrupt storage and opt out', () => {
        values.set(REMEMBERED_LOGIN,'{');expect(readRememberedLogin()).toBeNull();
        rememberLogin('owner@example.com','password',true);expect(readRememberedLogin()?.password).toBe('password');
        rememberLogin('owner@example.com','password',false);expect(readRememberedLogin()).toBeNull();
    });
    it('clears failed remembered credentials', async () => {
        rememberLogin('owner@example.com','bad',true);
        vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:400}));
        await expect(rememberedSignIn('owner@example.com','bad')).rejects.toThrow();
        expect(readRememberedLogin()).toBeNull();
    });
    it('preserves saved credentials on throttling and network errors', async () => {
        rememberLogin('owner@example.com','password',true);
        vi.stubGlobal('fetch',vi.fn().mockResolvedValue({ok:false,status:429}));
        await expect(rememberedSignIn('owner@example.com','password')).rejects.toThrow();
        expect(readRememberedLogin()).not.toBeNull();
        vi.stubGlobal('fetch',vi.fn().mockRejectedValue(new Error('network')));
        await expect(rememberedSignIn('owner@example.com','password')).rejects.toThrow();
        expect(readRememberedLogin()).not.toBeNull();
    });
    it('logout clears token and saved password', () => {
        rememberLogin('owner@example.com','password',true);values.set('token','session');clearLogin();
        expect(values.has('token')).toBe(false);expect(readRememberedLogin()).toBeNull();
    });
});
