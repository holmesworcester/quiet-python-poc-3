from core.crypto import kdf

def execute(params, identity, db):
    """Test key derivation function"""
    password = params["password"]
    salt = params.get("salt")  # Optional
    
    # Derive key from password
    result = kdf(password, salt)
    
    return result