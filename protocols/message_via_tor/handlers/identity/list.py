def execute(input_data, identity, db):
    """
    Provides a list of all client identities
    """
    # Get all identities from state
    identities = db.get('state', {}).get('identities', [])
    
    # Return list of identities (without private keys)
    identity_list = [
        {
            "pubkey": id_data.get("pubkey"),
            "name": id_data.get("name")
        }
        for id_data in identities
    ]
    
    return {
        "return": f"Found {len(identity_list)} identities",
        "identities": identity_list
    }