
import os
from typing import Optional, List
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

try:
    import aiosmtplib # type: ignore
    ASYNC_SMTP_AVAILABLE = True
except ImportError:
    ASYNC_SMTP_AVAILABLE = False
    print("[WARNING] aiosmtplib not available, falling back to sync smtp")

import smtplib
import asyncio

MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD") 
MAIL_FROM = os.getenv("MAIL_FROM", MAIL_USERNAME)
MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
MAIL_USE_TLS = os.getenv("MAIL_STARTTLS", "True").lower() == "true"
MAIL_USE_SSL = os.getenv("MAIL_SSL_TLS", "False").lower() == "true"

if not all([MAIL_USERNAME, MAIL_PASSWORD, MAIL_SERVER]):
    print("[WARNING] Email configuration incomplete. Email sending will fail.")
    print(f"  MAIL_USERNAME: {'✓' if MAIL_USERNAME else '✗'}")
    print(f"  MAIL_PASSWORD: {'✓' if MAIL_PASSWORD else '✗'}")
    print(f"  MAIL_SERVER: {MAIL_SERVER if MAIL_SERVER else '✗'}")


async def send_activation_email(
    recipient_email: str,
    user_name: str, 
    activation_token: str,
    frontend_url: str = "http://localhost:3000"
) -> dict:
    """
    Send activation email with robust error handling.
    Returns dict with status and message.
    """
    
    activation_link = f"{frontend_url}/set-initial-password/{activation_token}"
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Aktivasi Akun Anda'
    msg['From'] = MAIL_FROM
    msg['To'] = recipient_email
    
    # Plain text version
    text_content = f"""
Selamat Datang, {user_name}!

Terima kasih telah bergabung dengan kami.
Satu langkah lagi untuk mengaktifkan akun Anda.

Silakan klik link di bawah untuk mengatur password Anda:
{activation_link}

Link ini akan kedaluwarsa dalam 24 jam.

Jika Anda tidak merasa mendaftar, silakan abaikan email ini.

Salam,
Tim Support
    """
    
    # HTML version
    html_content = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family: 'Segoe UI', Arial, sans-serif; line-height: 1.6; color: #333; margin: 0; padding: 0;">
    <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f5f5f5; padding: 20px 0;">
        <tr>
            <td align="center">
                <table width="600" cellpadding="0" cellspacing="0" style="background-color: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <!-- Header -->
                    <tr>
                        <td style="background: linear-gradient(135deg, #FDBA74 0%, #EA580C 100%); padding: 40px 30px; border-radius: 8px 8px 0 0;">
                            <h1 style="color: white; margin: 0; font-size: 28px; text-align: center;">
                                Selamat Datang!
                            </h1>
                        </td>
                    </tr>
                    
                    <!-- Body -->
                    <tr>
                        <td style="padding: 40px 30px;">
                            <h2 style="color: #333; margin-bottom: 10px;">Halo, {user_name}!</h2>
                            <p style="color: #666; margin-bottom: 30px;">
                                Terima kasih telah bergabung dengan kami. Anda hanya perlu satu langkah lagi untuk mengaktifkan akun Anda.
                            </p>
                            
                            <div style="text-align: center; margin: 40px 0;">
                                <a href="{activation_link}" 
                                   style="display: inline-block; background: linear-gradient(135deg, #FDBA74 0%, #EA580C 100%); 
                                          color: white; text-decoration: none; padding: 15px 40px; 
                                          border-radius: 50px; font-weight: bold; font-size: 16px;
                                          box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);">
                                    Aktivasi Akun & Set Password
                                </a>
                            </div>
                            
                            <div style="background-color: #f9f9f9; padding: 15px; border-radius: 4px; margin: 30px 0;">
                                <p style="color: #999; font-size: 12px; margin: 5px 0;">
                                    Jika tombol tidak berfungsi, salin link berikut ke browser:
                                </p>
                                <p style="color: #667eea; font-size: 12px; word-break: break-all; margin: 5px 0;">
                                    {activation_link}
                                </p>
                            </div>
                            
                            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                            
                            <p style="color: #999; font-size: 14px; margin-bottom: 10px;">
                                <strong>Penting:</strong> Link aktivasi ini akan kedaluwarsa dalam <strong>24 jam</strong>.
                            </p>
                            <p style="color: #999; font-size: 12px;">
                                Jika Anda tidak mendaftar untuk akun ini, silakan abaikan email ini.
                            </p>
                        </td>
                    </tr>
                    
                    <!-- Footer -->
                    <tr>
                        <td style="background-color: #f9f9f9; padding: 20px 30px; border-radius: 0 0 8px 8px; text-align: center;">
                            <p style="color: #999; font-size: 12px; margin: 0;">
                                Email ini dikirim secara otomatis. Mohon tidak membalas email ini.
                            </p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
    """
    
    msg.attach(MIMEText(text_content, 'plain'))
    msg.attach(MIMEText(html_content, 'html'))
    
    if ASYNC_SMTP_AVAILABLE:
        try:
            await aiosmtplib.send(
                msg,
                hostname=MAIL_SERVER,
                port=MAIL_PORT,
                start_tls=MAIL_USE_TLS,
                username=MAIL_USERNAME,
                password=MAIL_PASSWORD,
            )
            print(f"✅ [ASYNC] Email sent successfully to {recipient_email}")
            return {"success": True, "message": "Email sent successfully", "method": "async"}
            
        except Exception as e:
            print(f"❌ [ASYNC] Failed to send email: {str(e)}")
    
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _send_email_sync, msg, recipient_email)
        if result:
            print(f"✅ [SYNC] Email sent successfully to {recipient_email}")
            return {"success": True, "message": "Email sent successfully", "method": "sync"}
        else:
            raise Exception("Failed to send email")
            
    except Exception as e:
        error_msg = f"Failed to send email: {str(e)}"
        print(f"❌ [SYNC] {error_msg}")
        raise Exception(error_msg)


def _send_email_sync(msg, recipient_email: str) -> bool:
    """Synchronous email sending helper"""
    try:
        if MAIL_USE_SSL:
            server = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT)
        else:
            server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
            if MAIL_USE_TLS:
                server.starttls()
        
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
        
    except Exception as e:
        print(f"[SMTP ERROR] {str(e)}")
        return False


async def test_email_configuration() -> dict:
    """Test email configuration and connection"""
    results = {
        "config_complete": all([MAIL_USERNAME, MAIL_PASSWORD, MAIL_SERVER]),
        "async_available": ASYNC_SMTP_AVAILABLE,
        "connection_test": False,
        "send_test": False,
        "errors": []
    }
    
    try:
        if MAIL_USE_SSL:
            server = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT)
        else:
            server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
            if MAIL_USE_TLS:
                server.starttls()
        
        server.login(MAIL_USERNAME, MAIL_PASSWORD)
        server.quit()
        results["connection_test"] = True
        print("✅ SMTP connection test passed")
        
    except Exception as e:
        results["errors"].append(f"Connection test failed: {str(e)}")
        print(f"❌ SMTP connection test failed: {str(e)}")
    
    return results