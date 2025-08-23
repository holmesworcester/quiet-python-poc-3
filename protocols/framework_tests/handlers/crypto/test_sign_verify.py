from core.crypto import sign, verify, get_keypair

def execute(params, identity, db):
    """Test sign and verify operations"""
    data = params["data"]
    
    # Get keypair for identity
    keypair = get_keypair(identity)
    
    # Sign the data
    signature = sign(data, keypair["private"])
    
    # Verify the signature
    verified = verify(data, signature, keypair["public"])
    
    return {
        "signature": signature,
        "verified": verified,
        "publicKey": keypair["public"],
        "privateKey": keypair["private"]
    }