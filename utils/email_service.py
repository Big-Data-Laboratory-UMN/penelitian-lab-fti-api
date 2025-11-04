
from datetime import datetime
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

BASE_URL_FRONTEND = os.getenv("BASE_URL_FE", "http://localhost:3000")

if not all([MAIL_USERNAME, MAIL_PASSWORD, MAIL_SERVER]):
    print("[WARNING] Email configuration incomplete. Email sending will fail.")
    print(f"  MAIL_USERNAME: {'✓' if MAIL_USERNAME else '✗'}")
    print(f"  MAIL_PASSWORD: {'✓' if MAIL_PASSWORD else '✗'}")
    print(f"  MAIL_SERVER: {MAIL_SERVER if MAIL_SERVER else '✗'}")


async def send_activation_email(
    recipient_email: str,
    user_name: str, 
    activation_token: str,
    frontend_url: str = BASE_URL_FRONTEND
) -> dict:
    """
    Send activation email with robust error handling.
    Returns dict with status and message.
    """
    
    activation_link = f"{frontend_url}/auth/set-initial-password/{activation_token}"
    
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

async def send_email_change_verification_email(
    recipient_email: str,
    user_name: str,
    verification_token: str,
    frontend_url: str = BASE_URL_FRONTEND
) -> dict:
    """
    Kirim email verifikasi untuk perubahan alamat email.
    """
    
    verification_link = f"{frontend_url}/auth/email-verified/{verification_token}"
    
    msg = MIMEMultipart('alternative')
    msg['Subject'] = 'Konfirmasi Perubahan Alamat Email Anda'
    msg['From'] = MAIL_FROM
    msg['To'] = recipient_email
    
    # Versi teks biasa
    text_content = f"""
Halo, {user_name}!

Kami menerima permintaan untuk mengubah alamat email akun Anda menjadi email ini.
Untuk menyelesaikan proses, silakan klik tautan di bawah ini untuk memverifikasi alamat email baru Anda:
{verification_link}

Tautan ini akan kedaluwarsa dalam 24 jam.

Jika Anda tidak merasa meminta perubahan ini, Anda bisa mengabaikan email ini dengan aman.

Terima kasih,
Tim Support
    """
    
    # Versi HTML
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
                    <tr>
                        <td style="background: linear-gradient(135deg, #FDBA74 0%, #EA580C 100%); padding: 40px 30px; border-radius: 8px 8px 0 0;">
                            <h1 style="color: white; margin: 0; font-size: 28px; text-align: center;">
                                Verifikasi Email Baru Anda
                            </h1>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 40px 30px;">
                            <h2 style="color: #333; margin-bottom: 10px;">Halo, {user_name}!</h2>
                            <p style="color: #666; margin-bottom: 30px;">
                                Kami menerima permintaan untuk memperbarui email Anda. Klik tombol di bawah untuk mengonfirmasi bahwa ini adalah alamat email baru Anda.
                            </p>
                            <div style="text-align: center; margin: 40px 0;">
                                <a href="{verification_link}" 
                                   style="display: inline-block; background: linear-gradient(135deg, #FDBA74 0%, #EA580C 100%); 
                                          color: white; text-decoration: none; padding: 15px 40px; 
                                          border-radius: 50px; font-weight: bold; font-size: 16px;
                                          box-shadow: 0 4px 15px rgba(59, 130, 246, 0.4);">
                                    Verifikasi Email Ini
                                </a>
                            </div>
                            <div style="background-color: #f9f9f9; padding: 15px; border-radius: 4px; margin: 30px 0;">
                                <p style="color: #999; font-size: 12px; margin: 5px 0;">
                                    Jika tombol tidak berfungsi, salin link berikut ke browser:
                                </p>
                                <p style="color: #3B82F6; font-size: 12px; word-break: break-all; margin: 5px 0;">
                                    {verification_link}
                                </p>
                            </div>
                            <hr style="border: none; border-top: 1px solid #eee; margin: 30px 0;">
                            <p style="color: #999; font-size: 14px; margin-bottom: 10px;">
                                <strong>Penting:</strong> Tautan verifikasi ini akan kedaluwarsa dalam <strong>24 jam</strong>.
                            </p>
                            <p style="color: #999; font-size: 12px;">
                                Jika Anda tidak meminta perubahan email ini, silakan abaikan email ini.
                            </p>
                        </td>
                    </tr>
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
            print(f"✅ [ASYNC] Email verification for email change sent successfully to {recipient_email}")
            return {"success": True, "message": "Email sent successfully", "method": "async"}
            
        except Exception as e:
            print(f"❌ [ASYNC] Failed to send email: {str(e)}")
    
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _send_email_sync, msg, recipient_email)
        if result:
            print(f"✅ [SYNC] Email verification for email change sent successfully to {recipient_email}")
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

def create_styled_html_body(
    title: str,
    main_content: str,
    button_text: Optional[str] = None,
    button_url: Optional[str] = None,
    footer_note: str = "Ini adalah email otomatis, mohon tidak membalas."
) -> str:
    """
    Helper baru untuk nge-generate body HTML email yang konsisten
    sesuai styling email aktivasi.
    """
    
    # Style ini gw copy-paste dari fungsi send_activation_email lu
    style = """
    <style>
        .container {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            margin: 20px;
            padding: 20px;
            border: 1px solid #ddd;
            border-radius: 5px;
            max-width: 600px;
        }
        .header {
            font-size: 24px;
            font-weight: bold;
            color: #333;
        }
        .content {
            margin-top: 20px;
        }
        .button {
            display: inline-block;
            background-color: #007bff;
            color: #ffffff;
            padding: 12px 25px;
            text-decoration: none;
            border-radius: 5px;
            font-weight: bold;
            margin-top: 20px;
        }
        .footer {
            margin-top: 30px;
            font-size: 12px;
            color: #888;
        }
        ul {
            padding-left: 20px;
        }
        li {
            margin-bottom: 5px;
        }
    </style>
    """
    
    # Bikin tombol kalo ada
    button_html = ""
    if button_text and button_url:
        button_html = f"""
        <a href="{button_url}" class="button" style="color: #ffffff; text-decoration: none;">
            {button_text}
        </a>
        """

    # Gabungin semua
    body_html = f"""
    <html>
    <head>
        <meta charset="UTF-8">
        {style}
    </head>
    <body>
        <div class="container">
            <div class="header">{title}</div>
            <div class="content">
                {main_content}
            </div>
            {button_html}
            <div class="footer">
                <p>{footer_note}</p>
                <p>&copy; {datetime.now().year} Tim Lab FTI</p>
            </div>
        </div>
    </body>
    </html>
    """
    return body_html


async def send_email_async(
    recipients: List[str],
    subject: str,
    html_content: str
) -> bool:
    """
    Pengirim email ASYNC generik untuk banyak penerima.
    """
    if not all([MAIL_USERNAME, MAIL_PASSWORD, MAIL_SERVER]):
        print("[EMAIL ERROR] Konfigurasi email tidak lengkap. Email gagal dikirim.")
        return False
        
    if not recipients:
        print("[EMAIL WARN] Tidak ada penerima. Email tidak dikirim.")
        return True

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = MAIL_FROM
    msg['To'] = ", ".join(recipients) 
    msg.attach(MIMEText(html_content, 'html'))

    if ASYNC_SMTP_AVAILABLE:
        try:
            
            await aiosmtplib.send(
                msg,
                hostname=MAIL_SERVER,
                port=MAIL_PORT,
                
                use_tls=MAIL_USE_SSL, 
                
                start_tls=MAIL_USE_TLS, 
                
                username=MAIL_USERNAME,
                password=MAIL_PASSWORD,
                
                recipients=recipients
            )
            return True 
        
        except Exception as e:
            if "Connection already using TLS" in str(e):
                print(f"[ASYNC SMTP ERROR] {str(e)}. Coba cek .env. Kemungkinan MAIL_USE_SSL dan MAIL_USE_TLS sama-sama True.")
            else:
                print(f"[ASYNC SMTP ERROR] {str(e)}")
            return False 
    else:
        print("[EMAIL FALLBACK] aiosmtplib tidak ketemu. Pake sync sender...")
        try:
            if MAIL_USE_SSL:
                server = smtplib.SMTP_SSL(MAIL_SERVER, MAIL_PORT)
            else:
                server = smtplib.SMTP(MAIL_SERVER, MAIL_PORT)
                if MAIL_USE_TLS:
                    server.starttls()
            
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            
            server.send_message(msg, from_addr=MAIL_FROM, to_addrs=recipients)
            server.quit()
            return True
        except Exception as e:
            print(f"[SYNC SMTP ERROR] {str(e)}")
            return False
        
        
async def send_booking_status_email(
    recipient_email: str,
    user_name: str,
    booking_code: str,
    lab_name: str,
    activity: str,
    new_status_str: str, # "Disetujui" atau "Ditolak"
    reviewer_name: str,
    reviewed_at: datetime
) -> bool:
    """
    Kirim email notifikasi status booking (Disetujui/Ditolak) ke user.
    """
    
    subject = f"[Update Booking] Booking Anda {booking_code} telah {new_status_str}"
    
    # Bikin konten emailnya
    details_html = f"""
    <p>Halo, {user_name},</p>
    <p>Ada update untuk booking Anda ({booking_code}) di <strong>{lab_name}</strong>.</p>
    
    <div style="background-color: #f9f9f9; padding: 20px; border-radius: 8px; margin: 25px 0;">
        <h3 style="margin-top: 0; color: {'#16a34a' if new_status_str == 'Disetujui' else '#dc2626'};">
            Status: {new_status_str.upper()}
        </h3>
        <ul style="padding-left: 20px; line-height: 1.8;">
            <li><strong>Aktivitas:</strong> {activity}</li>
            <li><strong>Lab:</strong> {lab_name}</li>
            <li><strong>Kode Booking:</strong> {booking_code}</li>
            <li><strong>Direview oleh:</strong> {reviewer_name}</li>
            <li><strong>Waktu Review:</strong> {reviewed_at.strftime('%Y-%m-%d %H:%M:%S')}</li>
        </ul>
    </div>
    
    <p>Anda bisa melihat detail booking Anda kapan saja melalui tombol di bawah ini.</p>
    """

    base_url = BASE_URL_FRONTEND 
    review_url = f"{base_url}/booking" 

    html_content = create_styled_html_body(
            title=f"Booking {new_status_str}",
            main_content=details_html,
            button_text="Lihat Booking Saya",
            button_url=review_url,
            footer_note="Email ini dikirim otomatis sebagai notifikasi update status booking Anda."
        )

    try:
        email_sukses = await send_email_async(
                recipients=[recipient_email],
                subject=subject,
                html_content=html_content
            )
        
        if email_sukses:
            print(f"✅ [Notify User] Sukses kirim notifikasi status '{new_status_str}' untuk booking {booking_code} ke {recipient_email}")
            return True
        else:
            print(f"❌ [Notify User] Gagal kirim email (setelah styling) untuk booking {booking_code}")
            return False
            
    except Exception as e:
        print(f"❌ [Notify User ERROR] Gagal proses notifikasi untuk booking {booking_code}: {str(e)}")
        return False
    
    

async def send_pending_reminder_email(
    recipient_email: str,
    user_name: str,
    pending_count: int,
    bookings_html_list: str # Ini adalah string HTML <ul>...</ul>
) -> bool:
    """
    Kirim email reminder ke Admin/PIC 
    yang isinya daftar booking yang masih pending.
    """
    
    subject = f"[Reminder] Anda memiliki {pending_count} Booking Lab yang Menunggu Persetujuan"
    
    # Bikin konten emailnya
    main_content_html = f"""
    <p>Halo, {user_name},</p>
    <p>Ini adalah pengingat otomatis bahwa ada <strong>{pending_count} booking</strong> 
    yang masih berstatus 'Pending' di lab/departemen yang Anda kelola dan 
    memerlukan review (Approve/Reject) dari Anda:</p>
    
    <div style="background-color: #f9f9f9; padding: 20px; border-radius: 8px; margin: 25px 0;">
        {bookings_html_list}
    </div>
    
    <p>Silakan login ke sistem untuk segera menindaklanjuti booking tersebut.</p>
    """

    base_url = BASE_URL_FRONTEND 
    review_url = f"{base_url}/management/monitoring/booking" # Arahin ke halaman list booking

    html_content = create_styled_html_body(
            title="Reminder Booking Pending",
            main_content=main_content_html,
            button_text="Review Booking Sekarang",
            button_url=review_url,
            footer_note="Email ini dikirim otomatis karena Anda terdaftar sebagai PIC/Admin."
        )

    try:
        email_sukses = await send_email_async(
                recipients=[recipient_email],
                subject=subject,
                html_content=html_content
            )
        
        if email_sukses:
            print(f"✅ [Reminder] Sukses kirim notifikasi pending ({pending_count} item) ke {recipient_email}")
            return True
        else:
            print(f"❌ [Reminder] Gagal kirim email (setelah styling) ke {recipient_email}")
            return False
            
    except Exception as e:
        print(f"❌ [Reminder ERROR] Gagal proses notifikasi ke {recipient_email}: {str(e)}")
        return False

async def send_documentation_reminder_email(
    recipient_email: str,
    user_name: str,
    pending_count: int,
    bookings_html_list: str
):
    """
    Mengirim email pengingat ke USER untuk segera upload dokumentasi.
    """
    
    subject = f"Reminder: {pending_count} Booking Anda Menunggu Dokumentasi"
    
    main_content_html = f"""
    <p>Halo, <strong>{user_name}</strong>!</p>
    <p>Sistem kami mencatat ada <strong>{pending_count} booking</strong> Anda yang telah selesai namun 
    belum diunggah dokumentasi kegiatannya. Berikut adalah daftarnya:</p>
    
    <div style="background-color: #f9f9f9; padding: 20px; border-radius: 8px; margin: 25px 0;">
        {bookings_html_list}
    </div>
    
    <p>Mohon untuk segera mengunggah dokumentasi agar Anda dapat melakukan booking kembali di masa mendatang.</p>
    """

    base_url = BASE_URL_FRONTEND 
    # Arahkan ke halaman 'My Bookings' user
    my_bookings_url = f"{base_url}/booking" 

    html_content = create_styled_html_body(
            title="Reminder Upload Dokumentasi",
            main_content=main_content_html,
            button_text="Upload Dokumentasi Sekarang",
            button_url=my_bookings_url,
            footer_note="Email ini dikirim otomatis karena booking Anda terdeteksi belum melengkapi dokumentasi."
        )

    try:
        email_sukses = await send_email_async(
                recipients=[recipient_email],
                subject=subject,
                html_content=html_content
            )
        
        if email_sukses:
            print(f"✅ [Doc Reminder] Sukses kirim notifikasi ({pending_count} item) ke {recipient_email}")
            return True
        else:
            print(f"❌ [Doc Reminder] Gagal kirim email (setelah retry) ke {recipient_email}")
            return False
            
    except Exception as e:
        print(f"❌ [Doc Reminder] Error saat kirim email ke {recipient_email}: {e}")
        return False