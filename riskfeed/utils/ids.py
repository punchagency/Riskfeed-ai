import uuid

def new_id(prefix: str) -> str:
    """Generate a new unique ID with a prefix"""
    return f"{prefix}{uuid.uuid4().hex}"