from .models import RevokedToken
from . import db

# Create fuctions to revoke jwt tokns which will help in logout

def add_token_to_blocklist(jti):
    """
    Adds the token's unique identifier (JTI) to the revoked tokens table.
    """
    revoked_token = RevokedToken(jti=jti)
    db.session.add(revoked_token)
    db.session.commit()

def is_token_revoked(jwt_payload):
    """
    Checks if the token's unique identifier (JTI) is in the revoked tokens table.
    """
    jti = jwt_payload["jti"]
    # Query the database to check if this JTI exists in the revoked tokens table
    token = RevokedToken.query.filter_by(jti=jti).first()
    return token is not None  # If found, it means the token is revoked