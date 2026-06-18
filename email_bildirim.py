import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL_KULLANICI = os.environ.get("GMAIL_KULLANICI", "")
GMAIL_SIFRE = os.environ.get("GMAIL_SIFRE", "")

def email_gonder(alici: str, konu: str, icerik: str) -> bool:
    """Gmail SMTP ile email gönder"""
    if not GMAIL_KULLANICI or not GMAIL_SIFRE:
        print("Email ayarları yapılmamış, atlanıyor")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = konu
        msg["From"] = GMAIL_KULLANICI
        msg["To"] = alici

        html = f"""
        <html><body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <div style="background: #16a34a; padding: 20px; border-radius: 10px 10px 0 0;">
                <h1 style="color: white; margin: 0;">🌿 Tarım AI</h1>
            </div>
            <div style="background: #f9fafb; padding: 20px; border-radius: 0 0 10px 10px; border: 1px solid #e5e7eb;">
                {icerik}
            </div>
            <p style="color: #9ca3af; font-size: 12px; text-align: center; margin-top: 20px;">
                Tarım AI — Bitki Sağlık Takip Sistemi
            </p>
        </body></html>
        """

        msg.attach(MIMEText(html, "html"))

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(GMAIL_KULLANICI, GMAIL_SIFRE)
            server.sendmail(GMAIL_KULLANICI, alici, msg.as_string())

        return True
    except Exception as e:
        print(f"Email gönderilemedi: {e}")
        return False

def analiz_emaili_gonder(alici: str, kullanici_ad: str, hastalik: str, risk: int, tahmin: str, bahce_ad: str):
    risk_renk = "#16a34a" if risk <= 3 else "#d97706" if risk <= 6 else "#dc2626"
    risk_yazi = "Düşük Risk" if risk <= 3 else "Orta Risk" if risk <= 6 else "⚠️ Yüksek Risk — Acil Müdahale!"

    icerik = f"""
    <h2 style="color: #1f2937;">Merhaba {kullanici_ad},</h2>
    <p><strong>{bahce_ad}</strong> bahçeniz için yeni analiz tamamlandı.</p>

    <div style="background: white; border-radius: 8px; padding: 16px; margin: 16px 0; border-left: 4px solid {risk_renk};">
        <h3 style="color: {risk_renk}; margin: 0 0 8px 0;">Tespit: {hastalik}</h3>
        <p style="margin: 4px 0;">Risk Skoru: <strong style="color: {risk_renk};">{risk}/10 — {risk_yazi}</strong></p>
        {f'<p style="margin: 4px 0;">Tahmin: {tahmin}</p>' if tahmin else ''}
    </div>

    <a href="https://tar-m-ai-as-l.onrender.com/gecmis"
       style="background: #16a34a; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; display: inline-block; margin-top: 8px;">
        Detayları Gör
    </a>
    """

    return email_gonder(
        alici,
        f"🌿 Tarım AI — {bahce_ad}: {hastalik} (Risk: {risk}/10)",
        icerik
    )