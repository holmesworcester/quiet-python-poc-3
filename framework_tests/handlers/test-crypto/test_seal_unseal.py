from core.crypto import seal, unseal, get_keypair

def execute(params, identity, db):
    """Test seal and unseal operations"""
    data = params["data"]
    
    # Get keypair for identity
    keypair = get_keypair(identity)
    
    # Seal the data for this identity's public key
    sealed = seal(data, keypair["public"])
    
    # Unseal the data with private key
    unsealed = unseal(sealed, keypair["private"], keypair["public"])
    
    # Check if unsealing matches original
    matches = unsealed.decode() == data if unsealed else False
    
    return {
        "sealed": sealed,
        "unsealed": unsealed.decode() if unsealed else None,
        "matches": matches,
        "publicKey": keypair["public"]
    }