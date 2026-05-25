import hashlib


class AuthService:

    @staticmethod
    def hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()

    @staticmethod
    def validate_password(password, hashed):
        return (
            hashlib.sha256(password.encode()).hexdigest()
            == hashed
        )
