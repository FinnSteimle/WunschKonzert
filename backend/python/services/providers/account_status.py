from __future__ import annotations

from models.domain import AccountStatus, ProviderAccount


def is_account_linked(provider_id: str, account: ProviderAccount | None) -> bool:
    """Return True if account has the credentials required for the given provider.

    AccountStatus.SUSPENDED is reused to represent a revoked Apple Music MUT,
    so a SUSPENDED account is treated as unlinked regardless of provider.
    """
    if account is None or account.status != AccountStatus.ACTIVE:
        return False
    if provider_id == "spotify":
        return bool(account.refreshToken)
    if provider_id == "apple-music":
        return bool(account.accessToken)
    # Unknown providers: require refreshToken (preserves original behaviour)
    return bool(account.refreshToken)
