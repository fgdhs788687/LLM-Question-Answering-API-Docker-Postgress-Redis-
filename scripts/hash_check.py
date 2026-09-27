from app.core.security import hash_password, verify_password

h = hash_password('secret123')
print(h)

print(verify_password('secret123',h))
print(verify_password('wrong',h))