# auth.py
import jwt
import requests
from functools import wraps
from flask import request, jsonify

TENANT_ID = "<YOUR_TENANT_ID>"
CLIENT_ID = "<YOUR_BACKEND_APP_CLIENT_ID>"  # Backend App Registration (API)
AUTHORITY = f"https://login.microsoftonline.com/{TENANT_ID}"
JWKS_URL = f"{AUTHORITY}/discovery/v2.0/keys"

# Cache JWKS (public keys)
jwks = requests.get(JWKS_URL).json()


def get_token_auth_header():
    """Extracts the access token from the Authorization header"""
    auth = request.headers.get("Authorization", None)
    if not auth:
        raise Exception("Authorization header missing")

    parts = auth.split()

    if parts[0].lower() != "bearer" or len(parts) != 2:
        raise Exception("Authorization header must be in the format 'Bearer <token>'")

    return parts[1]


def requires_auth(required_roles=None):
    """Decorator to enforce Azure AD token validation and optional RBAC"""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            try:
                token = get_token_auth_header()
                unverified_header = jwt.get_unverified_header(token)

                rsa_key = {}
                for key in jwks["keys"]:
                    if key["kid"] == unverified_header["kid"]:
                        rsa_key = {
                            "kty": key["kty"],
                            "kid": key["kid"],
                            "use": key["use"],
                            "n": key["n"],
                            "e": key["e"]
                        }

                if not rsa_key:
                    return jsonify({"error": "No valid signing key found"}), 401

                payload = jwt.decode(
                    token,
                    key=rsa_key,
                    algorithms=["RS256"],
                    audience=CLIENT_ID,
                    issuer=f"{AUTHORITY}/v2.0"
                )

                # Optional: check roles
                if required_roles:
                    user_roles = payload.get("roles", [])
                    if not any(role in user_roles for role in required_roles):
                        return jsonify({"error": "Forbidden - insufficient role"}), 403

                # Attach user info to request for later use
                request.user = payload

            except jwt.ExpiredSignatureError:
                return jsonify({"error": "Token expired"}), 401
            except jwt.JWTClaimsError as e:
                return jsonify({"error": f"Invalid claims: {str(e)}"}), 401
            except Exception as e:
                return jsonify({"error": f"Token validation failed: {str(e)}"}), 401

            return f(*args, **kwargs)
        return wrapper
    return decorator
