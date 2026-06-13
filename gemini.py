import google.genai as genai
import base64
from pathlib import Path

from gizli_anahtar import API_KEY

client = genai.Client(api_key=API_KEY)

def analiz_et(fotograf_yolu: str) -> dict:
    try:
        with open(fotograf_yolu, "rb") as f:
            fotograf_verisi = base64.b64encode(f.read()).decode("utf-8")

        uzanti = Path(fotograf_yolu).suffix.lower()
        mime_tipleri = {
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".png": "image/png",
        }
        mime_tip = mime_tipleri.get(uzanti, "image/jpeg")

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime_tip,
                                "data": fotograf_verisi,
                            }
                        },
                        {
                            "text": """Bu bitkide/meyvede hastalık var mı? 
                            Lütfen tam olarak şu formatta yanıtla, başka hiçbir şey ekleme:

HASTALIK: (SADECE hastalığın kısa adını yaz, örnek: Külleme, Citrus Canker, Yeşillenme. Sorun yoksa tek kelime 'Sağlıklı' yaz. Açıklama veya parantez YAZMA.)
AÇIKLAMA: (2-3 cümle açıklama)
BELİRTİLER: (görülen belirtiler)
NEDEN: (hastalığın nedenleri)
TEDAVİ: (tedavi yöntemleri)
ÖNERİLEN_İLAÇ: (en uygun ilaç adı, sadece ilaç adı)
ÖNERİLEN_DOZ: (örn: 2g/L su, 10ml/100L su gibi)
UYGULAMA_SIKLIĞI: (örn: 7 günde bir, 2 haftada bir)
ÇEVRE_ANALİZİ: (fotoğrafta yabancı ot, istilacı bitki, toprak/sulama sorunu gibi çevresel riskler var mı? Varsa ne olduğunu, neden risk oluşturduğunu ve ne yapılması gerektiğini yaz. Sorun yoksa 'Çevresel risk gözlenmedi' yaz)"""
                        }
                    ]
                }
            ]
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

        onerilen_ilac = satir_deger("ÖNERİLEN_İLAÇ")
        onerilen_doz = satir_deger("ÖNERİLEN_DOZ")
        uygulama_sikligi = satir_deger("UYGULAMA_SIKLIĞI")

        return {
            "basarili": True,
            "hastalik_adi": hastalik_adi,
            "rapor": rapor,
            "onerilen_ilac": onerilen_ilac,
            "onerilen_doz": onerilen_doz,
            "uygulama_sikligi": uygulama_sikligi
        }

    except Exception as e:
        return {
            "basarili": False,
            "hata": str(e)
        }