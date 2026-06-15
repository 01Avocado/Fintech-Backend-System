import os
from dotenv import load_dotenv
from passlib.context import CryptContext
from datetime import datetime, timedelta
from jose import jwt,JWTError

# Load environment variables from .env file
load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

#JWT Functions 
def create_access_tokens(data: dict):
    to_encode = data.copy() #copy the payload, we dont accidently modidy the original
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES) # Calculate expiry time (Current + 30 mins)
    to_encode.update({"exp": expire}) # Add the expiration time to the payload
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt 

def verify_access_tokens(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        return email
    except JWTError:
        raise credentials_exception

# tell  passlib to use to the bcrypt algo
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Function to hash a password
def hash_password(password: str):
    return pwd_context.hash(password)

# Function to compare password(used for login later)
def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)

# Unified helper to send emails via Resend HTTP API or SMTP
def send_email(to_email: str, subject: str, body_text: str):
    import smtplib
    import urllib.request
    import json
    from email.mime.text import MIMEText

    resend_api_key = os.getenv("RESEND_API_KEY")
    if resend_api_key:
        url = "https://api.resend.com/emails"
        headers = {
            "Authorization": f"Bearer {resend_api_key}",
            "Content-Type": "application/json"
        }
        # Resend free onboarding allows sending from onboarding@resend.dev
        sender = os.getenv("RESEND_SENDER", "onboarding@resend.dev")
        payload = {
            "from": sender,
            "to": [to_email],
            "subject": subject,
            "text": body_text
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            res_body = response.read().decode("utf-8")
            return f"Sent via Resend HTTP API. Response: {res_body}"

    # Fallback to SMTP
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = os.getenv("SMTP_PORT")
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")

    if not all([smtp_host, smtp_port, smtp_user, smtp_password]) or "your-email" in smtp_user:
        raise ValueError("SMTP credentials incomplete/not configured.")

    msg = MIMEText(body_text)
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = to_email

    port = int(smtp_port)
    if port == 465:
        with smtplib.SMTP_SSL(smtp_host, port, timeout=10) as server:
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, to_email, msg.as_string())
    else:
        with smtplib.SMTP(smtp_host, port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, to_email, msg.as_string())
    return "Sent via SMTP"