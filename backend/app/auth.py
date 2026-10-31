from functools import lru_cache
from fastapi import Header, HTTPException
from jose import jwt, JWTError
import httpx
from .settings import settings

@lru_cache(maxsize=1)
def _load_jwks():
    if not settings.supabase_url:
        raise HTTPException(500,"SUPABASE_URL is required to verify Supabase signing keys")
    try:
        response=httpx.get(settings.supabase_url.rstrip("/")+"/auth/v1/.well-known/jwks.json",timeout=5)
        response.raise_for_status()
        return response.json().get("keys",[])
    except (httpx.HTTPError,ValueError) as exc:
        raise HTTPException(503,"Could not retrieve Supabase signing keys") from exc

def require_user(authorization: str|None=Header(default=None)):
    if settings.auth_disabled: return {"sub":"local-test-user"}
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401,"Bearer access token required")
    try:
        token=authorization[7:]
        header=jwt.get_unverified_header(token)
        algorithm=header.get("alg")
        if algorithm=="HS256":
            if not settings.supabase_jwt_secret: raise HTTPException(500,"SUPABASE_JWT_SECRET is required for HS256 tokens")
            key=settings.supabase_jwt_secret
        elif algorithm in {"ES256","RS256"}:
            key=next((item for item in _load_jwks() if item.get("kid")==header.get("kid") and item.get("alg")==algorithm),None)
            if not key: raise JWTError("matching Supabase signing key not found")
        else:
            raise JWTError("unsupported signing algorithm")
        issuer=settings.supabase_url.rstrip("/")+"/auth/v1"
        payload=jwt.decode(token,key,algorithms=[algorithm],audience="authenticated",issuer=issuer)
        if not payload.get("sub"): raise JWTError("subject missing")
        return payload
    except JWTError as exc: raise HTTPException(401,"Invalid or expired access token") from exc
