from database import SessionLocal
from models import Analiz, Bahce, Kullanici
from email_bildirim import email_gonder, GMAIL_KULLANICI, GMAIL_SIFRE
import smtplib
from datetime import datetime, timedelta

def yuksek_riskli_kontrol():
    """Her gün arka planda tetiklenir; tek bir SMTP oturumu ile kullanıcıları spama düşmeden uyarır."""
    db = SessionLocal()
    try:
        yedi_gun_once = datetime.utcnow() - timedelta(days=7)
        
        sorgu_sonuclari = (
            db.query(Analiz, Bahce, Kullanici)
            .join(Bahce, Analiz.bahce_id == Bahce.id)
            .join(Kullanici, Bahce.kullanici_id == Kullanici.id)
            .filter(
                Analiz.risk_skoru >= 7,
                Analiz.tarih >= yedi_gun_once
            )
            .order_by(Analiz.risk_skoru.desc())
            .all()
        )

        if not sorgu_sonuclari:
            print("🌿 Son 7 günde yüksek riskli analiz bulunmadı. Gönderim yapılmıyor.")
            return

        gonderilen_kullanicilar = set()

        # İLERİ SEVİYE OPTİMİZASYON: Tüm mailler için TEK BİR SMTP hattı açılıyor
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=10) as server:
            if GMAIL_KULLANICI and GMAIL_SIFRE:
                server.login(GMAIL_KULLANICI, GMAIL_SIFRE)
                
                for analiz, bahce, kullanici in sorgu_sonuclari:
                    if not kullanici.email or kullanici.email in gonderilen_kullanicilar:
                        continue

                    gonderilen_kullanicilar.add(kullanici.email)
                    model_etiketi_temiz = analiz.tahmin.replace("_", " ").title() if analiz.tahmin else ""

                    icerik = f"""
                    <h2 style="color: #1f2937; margin-top: 0;">Merhaba {kullanici.ad},</h2>
                    <div style="background: #fef2f2; border-left: 5px solid #dc2626; padding: 20px; border-radius: 10px; margin: 20px 0; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">
                        <h3 style="color: #dc2626; margin: 0 0 10px 0; font-size: 18px;">⚠️ Kritik Durum Uyarısı</h3>
                        <p style="margin: 6px 0; font-size: 15px;"><strong>{bahce.ad}</strong> bahçenizde son 7 gün içinde kritik eşik aşılmıştır.</p>
                        <p style="margin: 6px 0; font-size: 14px;"><strong>Teşhis:</strong> {analiz.hastalik_adi}</p>
                        <p style="margin: 6px 0; font-size: 14px;"><strong>Tehlike Derecesi:</strong> <strong style="color: #dc2626;">{analiz.risk_skoru}/10</strong></p>
                        {f'<p style="margin: 6px 0; font-size: 14px; color: #4b5563;"><strong>YOLOv8 Detayı:</strong> {model_etiketi_temiz}</p>' if analiz.tahmin else ''}
                    </div>
                    <div style="text-align: center; margin: 24px 0;">
                        <a href="https://tar-m-ai-as-l.onrender.com/gecmis"
                           style="background: #dc2626; color: white; padding: 14px 28px; border-radius: 8px; text-decoration: none; display: inline-block; font-weight: bold;">
                           Acil Eylem Planını Gör
                        </a>
                    </div>
                    """
                    
                    # Mevcut açık olan 'server' bağlantısını parametre olarak paslıyoruz
                    email_gonder(
                        kullanici.email,
                        f"⚠️ Tarım AI Kritik Uyarı — {bahce.ad}: Yüksek Risk ({analiz.risk_skoru}/10)",
                        icerik,
                        sunucu_baglantisi=server
                    )
                    print(f"🚀 Toplu kanal üzerinden mail uçuruldu: {kullanici.email}")

    except Exception as e:
        print(f"❌ Proaktif kontrol hatası: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    yuksek_riskli_kontrol()