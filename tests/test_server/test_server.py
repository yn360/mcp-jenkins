import importlib

import pytest

import mcp_jenkins.server
from mcp_jenkins.server import JenkinsMCP


def test_http_app(mocker):
    jm = JenkinsMCP('mcp-jenkins-test')

    mock_wm = mocker.Mock()
    mocker.patch('mcp_jenkins.server.ASGIMiddleware', return_value=mock_wm)

    assert jm.http_app(path='/mcp', middleware=[mock_wm], transport='http').user_middleware.count(mock_wm) == 2


@pytest.fixture
def oidc_env(monkeypatch):
    monkeypatch.setenv('JENKINS_MCP_OIDC_ENABLED', 'true')
    monkeypatch.setenv('JENKINS_MCP_OIDC_DISCOVERY_URL', 'https://sso.example.com/.well-known/openid-configuration')
    monkeypatch.setenv('JENKINS_MCP_OIDC_CLIENT_ID', 'jenkins-mcp')
    monkeypatch.setenv('JENKINS_MCP_OIDC_CLIENT_SECRET', 'secret')
    monkeypatch.setenv('JENKINS_MCP_BASE_URL', 'https://jenkins-mcp.example.com')
    yield monkeypatch
    monkeypatch.delenv('JENKINS_MCP_OIDC_ENABLED')
    importlib.reload(mcp_jenkins.server)


def test_oidc_default_allowed_redirect_uris(oidc_env, mocker):
    mock_proxy = mocker.patch('fastmcp.server.auth.oidc_proxy.OIDCProxy')
    oidc_env.delenv('JENKINS_MCP_OIDC_ALLOWED_REDIRECT_URIS', raising=False)

    importlib.reload(mcp_jenkins.server)

    assert mock_proxy.call_args.kwargs['allowed_client_redirect_uris'] == ['http://localhost:*', 'http://127.0.0.1:*']


def test_oidc_allowed_redirect_uris_from_env(oidc_env, mocker):
    mock_proxy = mocker.patch('fastmcp.server.auth.oidc_proxy.OIDCProxy')
    oidc_env.setenv(
        'JENKINS_MCP_OIDC_ALLOWED_REDIRECT_URIS', 'http://localhost:*, claude://claude.ai/mcp-auth-callback/*,'
    )

    importlib.reload(mcp_jenkins.server)

    assert mock_proxy.call_args.kwargs['allowed_client_redirect_uris'] == [
        'http://localhost:*',
        'claude://claude.ai/mcp-auth-callback/*',
    ]
