from config import AUTHENTIK_BASE_URL, AUTHENTIK_CLIENT_ID, AUTHENTIK_CLIENT_SECRET

try:
    from authlib.integrations.starlette_client import OAuth
except ImportError:
    OAuth = None

oauth = OAuth() if OAuth else None

if oauth and AUTHENTIK_BASE_URL and AUTHENTIK_CLIENT_ID and AUTHENTIK_CLIENT_SECRET:
    oauth.register(
        name='authentik',
        server_metadata_url=(
            f"{AUTHENTIK_BASE_URL.rstrip('/')}"
            "/application/o/inventory-chatbot/"
            ".well-known/openid-configuration"
        ),
        client_id=AUTHENTIK_CLIENT_ID,
        client_secret=AUTHENTIK_CLIENT_SECRET,
        client_kwargs={'scope': 'openid profile email'},
    )