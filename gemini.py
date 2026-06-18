import google.genai as genai
import base64
from pathlib import Path
import os

try:
    from gizli_anahtar import API_KEY
except ImportError:
    API_KEY = os.environ.get("GEMINI_API_KEY", "")

client = genai.Client(api_key=API_KEY)

def fotograf_base64(yol):
    with open(yol, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")

def mime_tip(yol):
    uzanti = Path(yol).suffix.lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(uzanti, "image/jpeg")

def analiz_et(fotograf_yolu: str, onceki_fotograf_yolu: str = None, onceki_rapor: str = None) -> dict:
    try:
        parts = []

        # Mevcut fotoğraf
        parts.append({
            "inline_data": {
                "mime_type": mime_tip(fotograf_yolu),
                "data": fotograf_base64(fotograf_yolu)
            }
        })

        # Önceki fotoğraf varsa ekle
        if onceki_fotograf_yolu and os.path.exists(onceki_fotograf_yolu):
            parts.append({
                "inline_data": {
                    "mime_type": mime_tip(onceki_fotograf_yolu),
                    "data": fotograf_base64(onceki_fotograf_yolu)
                }
            })
            karsilastirma_talimat = f"""
İlk fotoğraf: MEVCUT durum (bugün çekildi)
İkinci fotoğraf: ÖNCEKİ durum ({onceki_rapor[:100] if onceki_rapor else 'önceki analiz'})

Bu iki fotoğrafı karşılaştırarak analiz yap."""
        else:
            karsilastirma_talimat = "Bu bitkinin ilk analizi yapılıyor."

        parts.append({
            "text": f"""Sen bir bitki hastalığı uzmanısın. {karsilastirma_talimat}

Lütfen TAM OLARAK şu formatta yanıtla, başka hiçbir şey ekleme:

HASTALIK: (SADECE hastalığın kısa adını yaz, örnek: Külleme, Citrus Canker. Sorun yoksa 'Sağlıklı' yaz)
AÇIKLAMA: (2-3 cümle açıklama)
BELİRTİLER: (görülen belirtiler)
NEDEN: (hastalığın nedenleri)
DEĞİŞİM: (önceki fotoğrafa göre ne değişti? İlk analizse 'İlk analiz' yaz)
TAHMİN: (2 hafta içinde ne olabilir? Risk artıyor mu, azalıyor mu?)
RİSK_SKORU: (1-10 arası sayı. 1=çok düşük risk, 10=acil müdahale gerekli. SADECE SAYI yaz)
TEDAVİ: (tedavi yöntemleri)
ÖNERİLEN_İLAÇ: (en uygun ilaç adı)
ÖNERİLEN_DOZ: (örn: 2g/L su)
UYGULAMA_SIKLIĞI: (örn: 7 günde bir)
ÇEVRE_ANALİZİ: (yabancı ot, toprak/sulama sorunu var mı? Yoksa 'Çevresel risk gözlenmedi' yaz)"""
        })

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[{"parts": parts}]
        )

        rapor = response.text

        def satir_deger(anahtar):
            for satir in rapor.split("\n"):
                if satir.startswith(anahtar + ":"):
                    return satir.replace(anahtar + ":", "").strip()
            return ""

        hastalik_adi = satir_deger("HASTALIK") or "Bilinmiyor"
        if hastalik_adi.startswith("("):
            hastalik_adi = "Bilinmiyor"

        risk_str = satir_deger("RİSK_SKORU")
        try:
            risk_skoru = int(''.join(filter(str.isdigit, risk_str)))
            risk_skoru = max(1, min(10, risk_skoru))
        except:
            risk_skoru = 5

        return {
            "basarili": True,
            "hastalik_adi": hastalik_adi,
            "rapor": rapor,
            "risk_skoru": risk_skoru,
            "tahmin": satir_deger("TAHMİN"),
            "degisim": satir_deger("DEĞİŞİM"),
            "onerilen_ilac": satir_deger("ÖNERİLEN_İLAÇ"),
            "onerilen_doz": satir_deger("ÖNERİLEN_DOZ"),
            "uygulama_sikligi": satir_deger("UYGULAMA_SIKLIĞI")
        }

    except Exception as e:
        return {
            "basarili": False,
            "hata": str(e)
        }