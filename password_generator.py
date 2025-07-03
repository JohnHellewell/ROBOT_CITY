import secrets
import string


def strength_check(s):
    special_chars = "!@#$%^&*~"
    
    has_lower = any(c.islower() for c in s)
    has_upper = any(c.isupper() for c in s)
    has_digit = any(c.isdigit() for c in s)
    has_special = any(c in special_chars for c in s)

    return has_lower and has_upper and has_digit and has_special


def generate_passkey(length=20):
    characters = string.ascii_letters + string.digits + "!@#$%^&*~"
    passkey = ''.join(secrets.choice(characters) for _ in range(length))
    while(not strength_check(passkey)):
        passkey = ''.join(secrets.choice(characters) for _ in range(length))
    
    return passkey

# Generate and print a passkey
print("Generated passkey:", generate_passkey())
