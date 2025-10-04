from cryptography.fernet import Fernet, InvalidToken
import logging

logger = logging.getLogger(__name__)

# Generate a key at application startup. 
# This key is ephemeral and will be lost on restart, which is fine for this use case
# as the encrypted IDs are only used for the duration of the server's runtime.
_key = Fernet.generate_key()
_cipher_suite = Fernet(_key)

def encrypt_player_id(player_id: str) -> str:
    """Encrypts a player ID into a URL-safe string."""
    try:
        encoded_id = player_id.encode('utf-8')
        encrypted_id = _cipher_suite.encrypt(encoded_id)
        return encrypted_id.decode('utf-8')
    except Exception as e:
        logger.error(f"Error encrypting player ID: {e}")
        return ""

def decrypt_player_id(encrypted_id: str) -> str | None:
    """Decrypts an encrypted player ID."""
    try:
        encrypted_bytes = encrypted_id.encode('utf-8')
        decrypted_bytes = _cipher_suite.decrypt(encrypted_bytes)
        return decrypted_bytes.decode('utf-8')
    except (InvalidToken, TypeError, ValueError) as e:
        logger.warning(f"Failed to decrypt player ID '{encrypted_id}': {e}")
        return None
    except Exception as e:
        logger.error(f"An unexpected error occurred during decryption: {e}")
        return None