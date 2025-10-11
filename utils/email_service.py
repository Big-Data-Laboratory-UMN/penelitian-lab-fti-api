import os
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig

conf = ConnectionConfig(
    MAIL_USERNAME = os.getenv("MAIL_USERNAME"),
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD"),
    MAIL_FROM = os.getenv("MAIL_FROM"),
    MAIL_PORT = int(os.getenv("MAIL_PORT", 587)),
    MAIL_SERVER = os.getenv("MAIL_SERVER"),
    MAIL_STARTTLS = os.getenv("MAIL_STARTTLS", "True").lower() == "true",
    MAIL_SSL_TLS = os.getenv("MAIL_SSL_TLS", "False").lower() == "true",
    USE_CREDENTIALS = True,
    VALIDATE_CERTS = True
)

async def send_activation_email(recipient_email: str, user_name: str, activation_token: str):
    activation_link = f"http://frontend.com/set-password?token={activation_token}"

    html_body = f"""
    <html>
        <body>
            <h2>Selamat Datang, {user_name}!</h2>
            <p>Satu langkah lagi untuk mengaktifkan akun Anda. Silakan klik tombol di bawah untuk mengatur password Anda:</p>
            <a href="{activation_link}" style="background-color: #4CAF50; color: white; padding: 14px 25px; text-align: center; text-decoration: none; display: inline-block;">
                Aktivasi Akun & Set Password
            </a>
            <p>Link ini akan kedaluwarsa dalam 24 jam.</p>
            <p>Jika Anda tidak merasa mendaftar, silakan abaikan email ini.</p>
        </body>
    </html>
    """

    message = MessageSchema(
        subject="Aktivasi Akun Anda",
        recipients=[recipient_email],
        body=html_body,
        subtype="html"
    )

    fm = FastMail(conf)
    try:
        await fm.send_message(message)
        print(f"Email aktivasi berhasil dikirim ke {recipient_email}")
    except Exception as e:
        print(f"Gagal mengirim email ke {recipient_email}. Error: {e}")
        raise