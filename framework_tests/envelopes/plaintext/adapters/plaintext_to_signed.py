import json
from core.crypto import sign, get_keypair

def adapt(envelope, db, identity):
    """Adapter: plaintext -> signed"""
    if envelope.get("envelope") != "plaintext":
        return None
    
    # Get keypair for identity
    keypair = get_keypair(identity)
    
    # Create canonical representation to sign
    data = envelope.get("data", {})
    metadata = envelope.get("metadata", {})
    
    # Sign just the data
    canonical = json.dumps(data, sort_keys=True)
    signature = sign(canonical, keypair["private"])
    
    return {
        "envelope": "signed",
        "data": data,
        "metadata": {
            **metadata,
            "sender": keypair["public"],  # sender IS the public key
            "signature": signature
        }
    }

# Adapter metadata
ADAPTER = {
    "from": "plaintext",
    "to": "signed",
    "function": adapt
}