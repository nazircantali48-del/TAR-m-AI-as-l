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

def analiz_et(
    fotograf_yolu: str,
    onceki_fotograf_yolu: str = None,
    onceki_rapor: str = None,
    hava_durumu: str = "Bilgi Yok"
) -> dict:
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
İlk fotoğraf: MEVCUT durum (bugün çekildi).
İkinci fotoğraf: ÖNCEKİ durum (Geçmiş rapor özeti: {onceki_rapor[:120] if onceki_rapor else 'Önceki analiz'}).
Lütfen bu iki fotoğraf arasındaki gelişim/iyileşme/kötüleşme durumunu DEĞİŞİM alanında kıyasla."""
        else:
            karsilastirma_talimat = "Bu bitkinin/bahçenin ilk analizi yapılıyor, geçmiş kaydı yok."

        # Gemini prompt
        prompt = f"""
Sen Türkiye'nin Akdeniz ve Ege bölgelerindeki narenciye/portakal üretiminde uzmanlaşmış kıdemli bir Ziraat Mühendisliği yapay zekasısın.

[SİSTEM VERİLERİ]
- Bahçenin anlık hava durumu: {hava_durumu}
{karsilastirma_talimat}

[GÖREVİN]
Fotoğraftaki bitkiyi analiz et:
1. Hastalık, zararlı böcek, besin eksikliği veya yabani ot varsa tespit et
2. Hava durumunu hastalık riski açısından değerlendir
3. Akdeniz/Türkiye koşullarına uygun tedavi ve ilaçlama planı yaz
4. Yabani ot varsa Türkiye'deki karşılıklarıyla (sirken, semizotu, horozibiği vb.) yorumla

Lütfen TAM OLARAK şu formatta yanıtla, başka hiçbir şey ekleme:

HASTALIK: (tespit edilen durumun kısa adı. Örnek: Demir Eksikliği, Turunçgil Kanseri, Yabani Ot İstilası. Sorun yoksa 'Sağlıklı' yaz)
AÇIKLAMA: (2-3 cümle açıklama)
BELİRTİLER: (görülen belirtiler)
NEDEN: (bu durumun nedenleri)
DEĞİŞİM: (önceki duruma göre değişim. İlk analizse 'İlk analiz' yaz)
TAHMİN: (mevcut hava ve risk durumuna göre 2 hafta içinde ne olabilir?)
RİSK_SKORU: (1-10 arası sayı. 1=sorunsuz, 10=acil müdahale. SADECE SAYI yaz)
TEDAVİ: (uygulanacak tedavi yöntemleri)
ÖNERİLEN_İLAÇ: (en uygun ilaç veya gübre adı)
ÖNERİLEN_DOZ: (uygulama dozu, örn: 200g/100L su)
UYGULAMA_SIKLIĞI: (örn: 10 gün arayla 2 kez)
ÇEVRE_ANALİZİ: (yabani ot, sulama veya toprak riski varsa yaz, yoksa 'Çevresel risk gözlenmedi' yaz)
"""

        parts.append({"text": prompt})

        response = client.models.generate_content(
    model="gemini-2.0-flash",  # bunu dene
    contents=[{"parts": parts}]
)

        rapor = response.text

        def satir_deger(anahtar):
            for satir in rapor.split("\n"):
                if satir.strip().startswith(anahtar + ":"):
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