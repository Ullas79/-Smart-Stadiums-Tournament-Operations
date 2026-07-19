from fastapi import Header, HTTPException
from ..models.roles import ROLE_DESCRIPTIONS

def verify_role_token(authorization: str | None = Header(None)) -> str:
    """Verifies the custom API token and extracts the role.
    
    Expected format: Authorization: Bearer {role}_secure_token_123
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization token")
    
    parts = authorization.split(" ")
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(status_code=401, detail="Invalid token format")
        
    token_parts = parts[1].split("_")
    if len(token_parts) < 3 or token_parts[1:] != ["secure", "token", "123"]:
        raise HTTPException(status_code=403, detail="Invalid token signature")
        
    role = token_parts[0]
    if role not in ROLE_DESCRIPTIONS:
        raise HTTPException(status_code=403, detail="Unknown role in token")
        
    return role
