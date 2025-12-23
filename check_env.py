import os
from dotenv import load_dotenv

load_dotenv()

required = [
    'GOOGLE_PROJECT_ID',
    'GOOGLE_PRIVATE_KEY_ID',
    'GOOGLE_PRIVATE_KEY',
    'GOOGLE_CLIENT_EMAIL',
    'GOOGLE_CLIENT_ID',
    'ENACTUS_SPREADSHEET_ID',
    'ENACTUS_DB_SPREADSHEET_ID'
]

print("Checking environment variables...")
for var in required:
    value = os.getenv(var)
    status = "OK" if value else "MISSING"
    if value and len(value) < 5:
        status = "WARNING (Too short)"
    print(f"{var}: {status}")
