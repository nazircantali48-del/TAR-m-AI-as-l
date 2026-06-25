import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GMAIL_KULLANICI = os.environ.get("GMAIL_KULLANICI", "")
GMAIL_SIFRE = os.environ.get("GMAIL_SIFRE", "")

def email_gonder(alici: str, konu: str, icerik: str, sunucu_baglantisi=None) -> bool:
    """Gmail SMTP altyapısını kullanarak e-posta gönderir. Mevcut bir bağlantı varsa onu kullanır."""
    if not GMAIL_KULLANICI or not GMAIL_SIFRE:
        print("⚠️ E-posta kimlik bilgileri ortam değişkenlerinde bulunamadı. Gönderim atlanıyor.")
        return False
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = konu
        msg["From"] = f"Tarım AI <{GMAIL_KULLANICI}>"
        msg["To"] = alici

        html = f"""
        <html><body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; max-width: 600px; margin: 0 auto; color: #374151;">
            <div style="background: #16a34a; padding: 24px; border-radius: 12px 12px 0 0; text-align: center;">
                <h1 style="color: white; margin: 0; font-size: 24px; letter-spacing: 0.5px;">🌿 Tarım AI</h1>
                <p style="color: #dcfce7; margin: 4px 0 0 0; font-size: 14px;">Akıllı Yapay Zeka Destekli Tarımsal Teşhis Sistemi</p>
            </div>
            <div style="background: #f9fafb; padding: 24px; border-radius: 0 0 12px 12px; border: 1px solid #e5e7eb; border-top: none; line-height: 1.6;">
                {icerik}
            </div>
            <p style="color: #9ca3af; font-size: 12px; text-align: center; margin-top: 24px;">
                Bu e-posta narenciye bahçenizin sağlığını korumak amacıyla otomatik olarak üretilmiştir.<br>
                Tarım AI © 2026 — Her Hakkı Saklıdır.
            </p>
        </body></html>
        """
        msg.attach(MIMEText(html, "html"))

        # Eğer dışarıdan aktif bir SMTP oturumu verilmişse (toplu gönderim modu) onu kullan
        if sunucu_baglantisi:
            sunucu_baglantisi.sendmail(GMAIL_KULLANICI, alici, msg.as_string())
            return True

        # Tekil gönderim modu (Anlık analiz sonrası tetiklenme)
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=5) as server:
            server.login(GMAIL_KULLANICI, GMAIL_SIFRE)
            server.sendmail(GMAIL_KULLANICI, alici, msg.as_string())
        return True
    except Exception as e:
        print(f"❌ E-posta gönderimi sırasında SMTP hatası oluştu: {e}")
        return False

def analiz_emaili_gonder(alici: str, kullanici_ad: str, hastalik: str, risk: int, tahmin: str, bahce_ad: str, sunucu_baglantisi=None):
    """YOLOv8 ve Gemini analiz sonuçlarını derleyerek çiftçiye özel acil e-posta raporu gönderir."""
    risk_renk = "#16a34a" if risk <= 3 else "#d97706" if risk <= 6 else "#dc2626"
    risk_yazi = "Düşük Risk (Durum Kontrol Altında)" if risk <= 3 else "Orta Risk (Takip Edilmeli)" if risk <= 6 else "⚠️ Yüksek Risk — Acil Müdahale Gerekli!"

    model_etiketi_temiz = tahmin.replace("_", " ").title() if tahmin else ""

    icerik = f"""
    <h2 style="color: #1f2937; margin-top: 0;">Merhaba {kullanici_ad},</h2>
    <p><strong>{bahce_ad}</strong> isimli narenciye bahçenizden gönderilen son yaprak fotoğrafının yapay zeka analizi tamamlanmıştır.</p>

    <div style="background: white; border-radius: 10px; padding: 20px; margin: 20px 0; border-left: 5px solid {risk_renk}; box-shadow: 0 1px 3px rgba(0,0,0,0.05); border-top: 1px solid #f3f4f6; border-right: 1px solid #f3f4f6; border-bottom: 1px solid #f3f4f6;">
        <h3 style="color: {risk_renk}; margin: 0 0 10px 0; font-size: 18px;">Nihai Teşhis: {hastalik}</h3>
        <p style="margin: 6px 0; font-size: 15px;">Tehlike Seviyesi: <strong style="color: {risk_renk};">{risk}/10 — {risk_yazi}</strong></p>
        {f'<p style="margin: 6px 0; font-size: 14px; color: #4b5563;"><strong>YOLOv8 Model Tespiti:</strong> {model_etiketi_temiz}</p>' if tahmin else ''}
    </div>
    <p style="margin-bottom: 20px; color: #4b5563;">Hastalığın yayılmasını önlemek, önerilen zirai ilaç/gübre dozajlarını incelemek ve kültürel önlemleri hemen almak için sistem paneline giriş yapabilirsiniz:</p>
    <div style="text-align: center; margin: 24px 0;">
        <a href="https://tar-m-ai-as-l.onrender.com/gecmis"
           style="background: #16a34a; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; display: inline-block; font-weight: bold; box-shadow: 0 2px 4px rgba(22,163,74,0.2);">
           Detaylı Reçeteyi ve Raporu Gör
        </a>
    </div>
    """
    baslik = f"🌿 Tarım AI — {bahce_ad}: {hastalik} (Risk: {risk}/10)"
    return email_gonder(alici, baslik, icerik, sunucu_baglantisi=sunucu_baglantisi)