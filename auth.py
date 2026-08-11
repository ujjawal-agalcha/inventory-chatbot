from authlib.integrations.starlette_client import OAuth
from config import (
    AUTHENTIK_BASE_URL,
    AUTHENTIK_CLIENT_ID,
    AUTHENTIK_CLIENT_SECRET,
)

oauth = OAuth()

oauth.register(
    name="authentik",
    server_metadata_url=f"{AUTHENTIK_BASE_URL}/application/o/inventory-chatbot/.well-known/openid-configuration",
    client_id=AUTHENTIK_CLIENT_ID,
    client_secret=AUTHENTIK_CLIENT_SECRET,
    client_kwargs={"scope": "openid profile email"},
)