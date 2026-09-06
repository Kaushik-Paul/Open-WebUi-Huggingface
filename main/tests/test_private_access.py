import pytest
from open_webui.utils.private_deployment import LoginLimiter, prepare_environment, POLICY

def test_rate_limit_bounded():
    limiter=LoginLimiter()
    assert all(limiter.allow('host', 0) for _ in range(10))
    assert not limiter.allow('host', 1)
    assert limiter.allow('host', 61)
    for i in range(3000): limiter.allow(str(i), 120+i*61)
    assert len(limiter.clients) <= 2048

def test_missing_configuration_fails(monkeypatch):
    monkeypatch.delenv('WEBUI_ADMIN_PASSWORD', raising=False)
    with pytest.raises(RuntimeError): prepare_environment()

def test_auth_disabled_fails(monkeypatch):
    monkeypatch.setenv('WEBUI_AUTH','false')
    with pytest.raises(RuntimeError,match='WEBUI_AUTH'): prepare_environment()

def test_immutable_environment(monkeypatch):
    import os
    for key,value in {'WEBUI_ADMIN_EMAIL':'owner@example.com','WEBUI_ADMIN_PASSWORD':'valid-test-password','WEBUI_SECRET_KEY':'s'*40,'WEBUI_AUTH':'true','ENABLE_SIGNUP':'true','WEBUI_AUTH_TRUSTED_EMAIL_HEADER':'X-User'}.items(): monkeypatch.setenv(key,value)
    prepare_environment()
    assert os.environ['ENABLE_SIGNUP'] == 'false'
    assert os.environ['ENABLE_DIRECT_CONNECTIONS'] == 'false'
    assert os.environ['WEBUI_AUTH_TRUSTED_EMAIL_HEADER'] == ''
    assert POLICY['ui.enable_login_form'] is True
