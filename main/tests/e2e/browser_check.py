"""Run against the isolated fixture container; never use a real owner profile."""
import os
from playwright.sync_api import sync_playwright, expect
BASE=os.getenv('TEST_BASE_URL','http://127.0.0.1:17860')
KEY='owui-hf.rememberedLogin.v1'
EMAIL='owner@example.com';PASSWORD='fixture-password-123'
with sync_playwright() as p:
    browser=p.chromium.launch(executable_path=os.getenv('CHROME_PATH','/usr/bin/google-chrome'),headless=True,args=['--no-sandbox'])
    context=browser.new_context()
    page=context.new_page()
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(BASE+'/auth')
    expect(page.get_by_role('button',name='Log in',exact=True)).to_be_visible(timeout=60000)
    expect(page.get_by_role('checkbox',name='Remember me on this browser')).to_be_checked()
    page.locator('input[type=email]').fill(EMAIL);page.locator('#password').fill(PASSWORD)
    page.get_by_role('button',name='Log in',exact=True).click()
    page.wait_for_url(BASE+'/',timeout=30000)
    assert page.evaluate('(k)=>JSON.parse(localStorage.getItem(k)).email',KEY)==EMAIL
    page.reload();page.wait_for_timeout(1500)
    assert '/auth' not in page.url
    # Expire both cookie and local token; one remembered sign-in should restore the session.
    context.clear_cookies();page.evaluate("localStorage.removeItem('token')")
    requests=[];page.on('request',lambda request: requests.append(request.url) if request.url.endswith('/auths/signin') else None)
    page.goto(BASE+'/auth');page.wait_for_url(BASE+'/',timeout=30000)
    assert len(requests)==1,len(requests)
    # A logout broadcast clears native and remembered state in another tab without a broadcast loop.
    other=context.new_page();other.goto(BASE+'/');other.wait_for_timeout(1500)
    page.evaluate("localStorage.removeItem('owui-hf.rememberedLogin.v1');localStorage.removeItem('token');localStorage.setItem('owui-hf.logout.v1',String(Date.now()))")
    other.wait_for_url('**/auth?state=logout',timeout=15000)
    expect(other.get_by_role('button',name='Log in',exact=True)).to_be_visible()
    assert other.evaluate('(k)=>localStorage.getItem(k)',KEY) is None
    page.goto(BASE+'/auth?state=logout');page.get_by_role('checkbox',name='Remember me on this browser').uncheck()
    page.locator('input[type=email]').fill(EMAIL);page.locator('#password').fill(PASSWORD)
    page.get_by_role('button',name='Log in',exact=True).click();page.wait_for_url(BASE+'/',timeout=30000)
    assert page.evaluate('(k)=>localStorage.getItem(k)',KEY) is None
    context.close()
    context=browser.new_context()
    context.add_init_script("Object.defineProperty(window,'localStorage',{configurable:true,get(){throw new DOMException('Blocked','SecurityError')}})")
    page=context.new_page();page.goto(BASE+'/auth')
    expect(page.get_by_role('button',name='Log in',exact=True)).to_be_visible(timeout=30000)
    page.locator('input[type=email]').fill(EMAIL);page.locator('#password').fill(PASSWORD)
    page.get_by_role('button',name='Log in',exact=True).click();page.wait_for_url(BASE+'/',timeout=30000)
    browser.close()
    assert not errors,errors[:5]
    print('PASS: manual login, remember default, reload, one expired-session auto-login, cross-tab logout, opt-out, blocked-storage login')
