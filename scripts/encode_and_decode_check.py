from app.core.security import create_access_token, decode_access_token
from datetime import timedelta
token = create_access_token({'sub':'1'}, timedelta(minutes=60))
print(token)
print(token[:40], "...")

print(decode_access_token(token))
print(decode_access_token("garbage"))