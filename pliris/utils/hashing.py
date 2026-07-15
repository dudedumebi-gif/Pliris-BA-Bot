import hashlib


def generate_hash(content: str, algorithm: str = "sha256") -> str:
    """
    Generate a hash of the given content.

    Args:
        content: Content to hash
        algorithm: Hash algorithm to use

    Returns:
        Hexadecimal hash string
    """
    hash_func = hashlib.new(algorithm)
    hash_func.update(content.encode("utf-8"))
    return hash_func.hexdigest()


def verify_hash(content: str, hash_value: str, algorithm: str = "sha256") -> bool:
    """
    Verify that content matches the given hash.

    Args:
        content: Content to verify
        hash_value: Expected hash value
        algorithm: Hash algorithm used

    Returns:
        True if hash matches, False otherwise
    """
    computed_hash = generate_hash(content, algorithm)
    return computed_hash == hash_value.lower()
