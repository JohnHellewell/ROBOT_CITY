import secrets
import string

def generate_passkey(length=20):
    characters = string.ascii_letters + string.digits + string.punctuation
    passkey = ''.join(secrets.choice(characters) for _ in range(length))
    return passkey

# Generate and print a passkey
print("Generated passkey:", generate_passkey())
