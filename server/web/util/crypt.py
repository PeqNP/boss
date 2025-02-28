#!/usr/bin/env python3
#
# Creates bcrypt passwords.
#
# I need to create users in the system directly with sqlite3 CLI
# as I don't have time to come up with a database update mechanism.
#

import bcrypt

def hash_password(password: str) -> str:
    # Generate a salt and hash the password
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')  # Convert bytes to string for storage

# Example usage
password = "Test123!"
hashed_password = hash_password(password)
print(f"Hashed Password ({hashed_password})")
