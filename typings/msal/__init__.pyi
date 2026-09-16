"""Subset of MSAL 1.38.0 used by the Microsoft connector and test script.

OAuth responses and account records remain extensible dictionaries.
These declarations affect static analysis only.
"""

from typing import Any

class SerializableTokenCache:
    has_state_changed: bool
    def __init__(self) -> None: ...
    def deserialize(self, state: str | None) -> None: ...
    def serialize(self) -> str: ...

class PublicClientApplication:
    def __init__(
        self,
        client_id: str,
        client_credential: str | dict[str, Any] | None = ...,
        *,
        authority: str | None = ...,
        token_cache: SerializableTokenCache | None = ...,
        **kwargs: Any,
    ) -> None: ...
    def get_accounts(self, username: str | None = ...) -> list[dict[str, Any]]: ...
    def acquire_token_silent(
        self,
        scopes: list[str],
        account: dict[str, Any] | None,
        authority: str | None = ...,
        force_refresh: bool = ...,
        claims_challenge: str | None = ...,
        forwarded_client_claims: dict[str, Any] | None = ...,
        auth_scheme: Any = ...,
        **kwargs: Any,
    ) -> dict[str, Any] | None: ...
    def acquire_token_interactive(
        self, scopes: list[str], **kwargs: Any
    ) -> dict[str, Any]: ...
