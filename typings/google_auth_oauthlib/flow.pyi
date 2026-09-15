"""Subset of google-auth-oauthlib 1.4.1 used by this project."""

from collections.abc import Sequence
from typing import Any, Self

from google.oauth2.credentials import Credentials

class Flow:
    @classmethod
    def from_client_secrets_file(
        cls, client_secrets_file: str, scopes: Sequence[str], **kwargs: Any
    ) -> Self: ...

class InstalledAppFlow(Flow):
    def run_local_server(
        self,
        host: str = ...,
        bind_addr: str | None = ...,
        port: int = ...,
        authorization_prompt_message: str | None = ...,
        success_message: str = ...,
        open_browser: bool = ...,
        redirect_uri_trailing_slash: bool = ...,
        timeout_seconds: float | None = ...,
        token_audience: str | None = ...,
        browser: str | None = ...,
        **kwargs: Any,
    ) -> Credentials: ...
