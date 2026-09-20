from typing import Annotated

from fastapi import Depends
from fastapi_sso.sso.google import GoogleSSO

from api.common.config import settings

def get_google_sso() -> GoogleSSO:
    return GoogleSSO(
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        redirect_uri=settings.GOOGLE_REDIRECT_URL,
        allow_insecure_http=settings.DEBUG,
    )

GoogleSSODep = Annotated[GoogleSSO, Depends(get_google_sso)]