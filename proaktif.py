from database import SessionLocal
from models import Analiz, Bahce, Kullanici
from email_bildirim import email_gonder
from datetime import datetime, timedelta

def yuksek_riskli_kontrol():
    """Her gün çalışır, yüksek riskli bahçe sahiplerine email atar"""
    db = SessionLocal()
    try:
        # Son 7 günde risk skoru 7+ olan analizleri bul
        yedi_gun_once = datetime.now() - timedelta(days=7)
        
        yuksek_riskli = db.query(Analiz).filter(
            Analiz.risk_skoru >= 7,
            Analiz.tarih >= yedi_gun_once
        ).all()

        gonderilen = set()

        for analiz in yuksek_riskli:
            bahce = db.query(Bahce).filter(Bahce.id == analiz.bahce_id).first()
            if not bahce or not bahce.kullanici_id:
                continue

            kullanici = db.query(Kullanici).filter(
                Kullanici.id == bahce.kullanici_id
            ).first()

            if not kullanici or not kullanici.email:
                continue

            # Aynı kişiye bir kez gönder
            if kullanici.email in gonderilen:
                continue

            gonderilen.add(kullanici.email)

            icerik = f"""
            <h2 style="color: #1f2937;">Merhaba {kullanici.ad},</h2>
            <div style="background: #fef2f2; border-left: 4px solid #dc2626; padding: 16px; border-radius: 8px; margin: 16px 0;">
                <h3 style="color: #dc2626; margin: 0 0 8px 0;">⚠️ Yüksek Risk Uyarısı</h3>
                <p><strong>{bahce.ad}</strong> bahçenizde son 7 gün içinde yüksek risk tespit edildi.</p>
                <p>Hastalık: <strong>{analiz.hastalik_adi}</strong></p>
                <p>Risk Skoru: <strong style="color: #dc2626;">{analiz.risk_skoru}/10</strong></p>
                {f'<p>Tahmin: {analiz.tahmin}</p>' if analiz.tahmin else ''}
            </div>
            <p>Lütfen bahçenizi kontrol edin ve gerekli tedbirleri alın.</p>
            <a href="https://tar-m-ai-as-l.onrender.com/gecmis"
               style="background: #dc2626; color: white; padding: 12px 24px; border-radius: 8px; text-decoration: none; display: inline-block;">
                Analiz Detaylarını Gör
            </a>
            """

            email_gonder(
                kullanici.email,
                f"⚠️ Tarım AI Uyarı — {bahce.ad}: Yüksek Risk ({analiz.risk_skoru}/10)",
                icerik
            )
            print(f"Uyarı emaili gönderildi: {kullanici.email} — {bahce.ad}")

    finally:
        db.close()

if __name__ == "__main__":
    yuksek_riskli_kontrol()