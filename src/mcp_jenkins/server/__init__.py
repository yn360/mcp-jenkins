import os
from typing import Any, Literal

from fastmcp import FastMCP
from loguru import logger
from starlette.applications import Starlette
from starlette.middleware import Middleware as ASGIMiddleware

from mcp_jenkins.core import AuthMiddleware, LifespanContext, lifespan

__all__ = ['mcp']

_auth_provider = None

if os.getenv('JENKINS_MCP_OIDC_ENABLED', 'false').lower() == 'true':
    from fastmcp.server.auth.oidc_proxy import OIDCProxy

    _discovery_url = os.getenv('JENKINS_MCP_OIDC_DISCOVERY_URL')
    _client_id = os.getenv('JENKINS_MCP_OIDC_CLIENT_ID')
    _client_secret = os.getenv('JENKINS_MCP_OIDC_CLIENT_SECRET')
    _base_url = os.getenv('JENKINS_MCP_BASE_URL')
    # Comma-separated redirect URI patterns MCP clients may register, e.g. Claude Desktop's
    # claude://claude.ai/mcp-auth-callback/* next to Claude Code's localhost callback.
    _allowed_redirect_uris_env = os.getenv(
        'JENKINS_MCP_OIDC_ALLOWED_REDIRECT_URIS', 'http://localhost:*,http://127.0.0.1:*'
    )
    _allowed_redirect_uris = [uri.strip() for uri in _allowed_redirect_uris_env.split(',') if uri.strip()]

    if not all([_discovery_url, _client_id, _client_secret, _base_url]):
        msg = (
            'OIDC mode requires JENKINS_MCP_OIDC_DISCOVERY_URL, '
            'JENKINS_MCP_OIDC_CLIENT_ID, JENKINS_MCP_OIDC_CLIENT_SECRET, '
            'and JENKINS_MCP_BASE_URL to be set.'
        )
        raise ValueError(msg)

    _auth_provider = OIDCProxy(
        config_url=_discovery_url,
        client_id=_client_id,
        client_secret=_client_secret,
        base_url=_base_url,
        # Disable CIMD (Client-Initiated Metadata Discovery) — the server cannot
        # reach https://claude.ai to fetch Claude Code's client metadata.
        # Instead, pre-approve the allowed redirect URIs so clients can complete
        # the PKCE flow without dynamic registration.
        enable_cimd=False,
        allowed_client_redirect_uris=_allowed_redirect_uris,
    )
    logger.info('OIDC authentication enabled. Discovery URL: {}', _discovery_url)


class JenkinsMCP(FastMCP[LifespanContext]):
    def http_app(
        self,
        path: str | None = None,
        middleware: list[ASGIMiddleware] | None = None,
        transport: Literal['http', 'streamable-http', 'sse'] = 'http',
        **kwargs: Any,  # noqa: ANN401
    ) -> 'Starlette':
        """Override to add JenkinsAuthMiddleware"""
        jenkins_auth_mw = ASGIMiddleware(AuthMiddleware)

        final_middleware_list = [jenkins_auth_mw]
        if middleware:
            final_middleware_list.extend(middleware)

        return super().http_app(path=path, middleware=final_middleware_list, transport=transport, **kwargs)


mcp = JenkinsMCP('mcp-jenkins', lifespan=lifespan, auth=_auth_provider)

# Import tool modules to register them with the MCP server
# This must happen after mcp is created so the @mcp.tool() decorators can reference it
from mcp_jenkins.server import build, item, node, queue, view  # noqa: F401, E402
