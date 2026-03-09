import os
import time
from dataclasses import dataclass

import jwt
import requests

APS_BASE_URL = "https://developer.api.autodesk.com"
AUTH_TOKEN_URL = f"{APS_BASE_URL}/authentication/v2/token"

DEFAULT_SSA_SCOPES = "code:all data:read data:write data:create data:search"


@dataclass(frozen=True)
class SsaConfig:
    """Configuration required to mint a 3-legged token via Secure Service Accounts."""

    client_id: str
    client_secret: str
    service_account_id: str
    key_id: str
    private_key: str
    scope: str

    @classmethod
    def from_env(cls) -> "SsaConfig":
        """Load SSA config from environment variables.

        Supported variables:
        - CLIENT_ID_SSA (fallback: APS_SSA_CLIENT_ID, APS_CLIENT_ID, CLIENT_ID)
        - CLIENT_SECRET_SSA (fallback: APS_SSA_CLIENT_SECRET, APS_CLIENT_SECRET, CLIENT_SECRET)
        - APS_SSA_SERVICE_ACCOUNT_ID
        - APS_SSA_KEY_ID
        - APS_SSA_PRIVATE_KEY (supports escaped newlines)
        - APS_SSA_SCOPE (default: code:all data:read data:write data:create data:search)
        """
        client_id = (
            os.getenv("CLIENT_ID_SSA")
            or os.getenv("APS_SSA_CLIENT_ID")
            or os.getenv("APS_CLIENT_ID")
            or os.getenv("CLIENT_ID")
        )
        client_secret = (
            os.getenv("CLIENT_SECRET_SSA")
            or os.getenv("APS_SSA_CLIENT_SECRET")
            or os.getenv("APS_CLIENT_SECRET")
            or os.getenv("CLIENT_SECRET")
        )
        required = {
            "CLIENT_ID_SSA": client_id,
            "CLIENT_SECRET_SSA": client_secret,
            "APS_SSA_SERVICE_ACCOUNT_ID": os.getenv("APS_SSA_SERVICE_ACCOUNT_ID"),
            "APS_SSA_KEY_ID": os.getenv("APS_SSA_KEY_ID"),
            "APS_SSA_PRIVATE_KEY": os.getenv("APS_SSA_PRIVATE_KEY"),
        }
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise RuntimeError(
                "Missing required environment variables: " + ", ".join(sorted(missing))
            )

        scope = os.getenv("APS_SSA_SCOPE", DEFAULT_SSA_SCOPES)

        return cls(
            client_id=str(required["CLIENT_ID_SSA"]),
            client_secret=str(required["CLIENT_SECRET_SSA"]),
            service_account_id=str(required["APS_SSA_SERVICE_ACCOUNT_ID"]),
            key_id=str(required["APS_SSA_KEY_ID"]),
            private_key=str(required["APS_SSA_PRIVATE_KEY"]).replace("\\n", "\n"),
            scope=" ".join(scope.split()),
        )

    @property
    def scopes(self) -> list[str]:
        values = [scope for scope in self.scope.split(" ") if scope]
        if not values:
            raise RuntimeError("APS_SSA_SCOPE must contain at least one scope")
        return values


def build_ssa_jwt(config: SsaConfig, expires_in_seconds: int = 300) -> str:
    """Build a JWT assertion for SSA token exchange.

    APS requires:
    - iss = APS client id
    - sub = Service account Oxygen id
    - aud = https://developer.api.autodesk.com/authentication/v2/token
    - exp <= now + 300 seconds
    """
    if not 1 <= expires_in_seconds <= 300:
        raise ValueError("expires_in_seconds must be between 1 and 300")

    now = int(time.time())
    claims = {
        "iss": config.client_id,
        "sub": config.service_account_id,
        "aud": AUTH_TOKEN_URL,
        "exp": now + expires_in_seconds,
        "scope": config.scopes,
    }
    headers = {
        "alg": "RS256",
        "kid": config.key_id,
    }

    return jwt.encode(
        claims,
        config.private_key,
        algorithm="RS256",
        headers=headers,
    )


def parse_token_response(payload: dict[str, object]) -> str:
    """Validate and extract the bearer access token from APS token response payload."""
    access_token = payload.get("access_token")
    token_type = str(payload.get("token_type", "")).lower()

    if not access_token or token_type != "bearer":
        raise RuntimeError(f"Unexpected SSA token response: {payload}")

    return str(access_token)


def exchange_jwt_assertion_for_token(
    client_id: str,
    client_secret: str,
    assertion: str,
    scope: str,
) -> str:
    """Call POST /authentication/v2/token with JWT bearer grant to mint a 3LO token."""
    response = requests.post(
        AUTH_TOKEN_URL,
        headers={
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": assertion,
            "scope": " ".join(scope.split()),
        },
        auth=(client_id, client_secret),
        timeout=30,
    )
    response.raise_for_status()
    return parse_token_response(response.json())


def get_ssa_3lo_token(config: SsaConfig, expires_in_seconds: int = 300) -> str:
    """Mint a 3-legged token from SSA config."""
    assertion = build_ssa_jwt(config=config, expires_in_seconds=expires_in_seconds)
    return exchange_jwt_assertion_for_token(
        client_id=config.client_id,
        client_secret=config.client_secret,
        assertion=assertion,
        scope=config.scope,
    )
