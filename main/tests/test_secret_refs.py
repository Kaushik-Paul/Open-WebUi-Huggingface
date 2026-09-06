import pytest
from fastapi import HTTPException
from open_webui.utils.secret_refs import resolve_secret, connection_credential

@pytest.fixture(autouse=True)
def env(monkeypatch):
    monkeypatch.setenv('PROVIDER_SECRET_NAMES', 'SURPLUS_API_KEY')
    monkeypatch.setenv('SURPLUS_API_KEY', 'provider-canary-one')

@pytest.mark.parametrize('name', ['', 'SURPLUS_AI_KEY', 'WEBUI_SECRET_KEY', '${SURPLUS_API_KEY}', 'surplus_api_key', 'OTHER'])
def test_rejects_names(name):
    with pytest.raises(HTTPException):
        resolve_secret(name, 'secret')

def test_resolution_is_request_local(monkeypatch):
    config = {'key_source': 'secret'}
    assert connection_credential('https://provider.example/v1', ' SURPLUS_API_KEY ', config) == 'provider-canary-one'
    monkeypatch.setenv('SURPLUS_API_KEY', 'provider-canary-two')
    assert connection_credential('https://provider.example/v1', 'SURPLUS_API_KEY', config) == 'provider-canary-two'
    assert config == {'key_source': 'secret'}

def test_literal_noauth_no_recursion(monkeypatch):
    assert resolve_secret('SURPLUS_API_KEY') == 'SURPLUS_API_KEY'
    assert resolve_secret('') == ''
    monkeypatch.setenv('SURPLUS_API_KEY', 'SURPLUS_API_KEY')
    assert resolve_secret('SURPLUS_API_KEY', 'secret') == 'SURPLUS_API_KEY'

@pytest.mark.parametrize('value', ['', '  ', 'one\ntwo', 'one\rtwo'])
def test_bad_values(value, monkeypatch):
    monkeypatch.setenv('SURPLUS_API_KEY', value)
    with pytest.raises(HTTPException): resolve_secret('SURPLUS_API_KEY', 'secret')

@pytest.mark.parametrize('config', [{'key_source':'secret','auth_type':'session'}, {'key_source':'secret','headers':{'aUtHoRiZaTiOn':'x'}}, {'key_source':'unknown'}])
def test_unsupported_combinations(config):
    with pytest.raises(HTTPException): connection_credential('https://provider.example/v1', 'SURPLUS_API_KEY', config)

@pytest.mark.parametrize('url', ['http://example.com/v1', 'https://user:pass@example.com/v1', 'https://example.com/v1?key=x', 'file:///tmp/key'])
def test_destinations(url):
    with pytest.raises(HTTPException): connection_credential(url, 'key')

def test_allowlist_required(monkeypatch):
    monkeypatch.delenv('PROVIDER_SECRET_NAMES')
    with pytest.raises(HTTPException): resolve_secret('SURPLUS_API_KEY', 'secret')
