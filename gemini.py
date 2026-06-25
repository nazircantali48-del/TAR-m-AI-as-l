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
    yolo_etiket: str = "Bilinmeyen Durum",
    hava_durumu: str = "Bilgi Yok"
) -> dict:
    try:
        parts = []

        # 1. MEVCUT FOTOĞRAF (Bugün çekilen)
        parts.append({
            "inline_data": {
                "mime_type": mime_tip(fotograf_yolu),
                "data": fotograf_base64(fotograf_yolu)
            }
        })

        # 2. ÖNCEKİ FOTOĞRAF (Varsa zaman serisi takibi için)
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

        # 3. ZİRAAT MÜHENDİSİ PROMPT'U VE SİSTEM TALİMATLARI
        # YOLOv8 çıktısını ve Hava Durumunu Gemini'a burada hammadde olarak veriyoruz.
        ziraat_uzmani_prompt = f"""
Sen Türkiye'nin Akdeniz ve Ege bölgelerindeki narenciye/portakal üretiminde uzmanlaşmış kıdemli bir Ziraat Mühendisliği yapay zekasısın.

[SİSTEM VERİLERİ]
- Yerel YOLOv8 modelinin fotoğrafta tespit ettiği ana etiket: {yolo_etiket}
- Bahçenin anlık dinamik hava durumu: {hava_durumu}
{karsilastirma_talimat}

[GÖREVİN VE SINIRLARIN]
1. Eğer YOLOv8 etiketi besin eksikliği içeriyorsa ('Azot Eksikliği', 'Mg', 'Fe' vb.), çiftçiye Akdeniz kireçli toprak yapısına uygun gübreleme reçetesi yaz.
2. Eğer YOLOv8 etiketi yabani ot içeriyorsa (örneğin DeepWeeds sınıfları), bunu Türkiye'deki karşılıkları olan Sirken, Semizotu veya Horozibiği gibi istilacılar olarak yorumla ve mekanik/organik temizlik öner.
3. YOLOv8 çıktısını ve hava durumunu (yüksek nem mantar riskini tetikler vb.) fotoğraftaki görsel kanıtlarla harmanla.

Lütfen TAM OLARAK şu formatta yanıtla, markdown kalıpları veya ekstra başlıklar/notlar ekleme:

HASTALIK: (SADECE tespit edilen durumun kısa ve net adını yaz. Örnek: Demir Eksikliği, Turunçgil Kanseri, Yabani Ot İstilası. Sorun yoksa 'Sağlıklı' yaz)
AÇIKLAMA: (Durumu özetleyen 2-3 cümlelik net açıklama)
BELİRTİLER: (Yaprakta veya çevrede gözlemlenen görsel belirtiler)
NEDEN: (Bu durumun oluşma nedenleri, toprak veya iklim ilişkisi)
DEĞİŞİM: (Önceki duruma göre iyileşme mi var kötüleşme mi? İlk analizse 'İlk analiz' yaz)
TAHMİN: (Mevcut hava durumu ve risk senaryosuna göre 2 hafta içinde ne olabilir?)
RİSK_SKORU: (1-10 arası sayı. 1=Sorunsuz, 10=Acil müdahale şart. SADECE SAYI YAZ)
TEDAVİ: (Uygulanacak ziraat ve kültürel mücadele yöntemleri)
ÖNERİLEN_İLAÇ: (En uygun organik/kimyasal ilaç veya gübre adı. Ot ise 'Mekanik Temizlik / Herbisit')
ÖNERİLEN_DOZ: (Uygulama dozu, örn: 200g / 100L su)
UYGULAMA_SIKLIĞI: (Uygulama periyodu, örn: 10 gün arayla 2 kez)
ÇEVRE_ANALİZİ: (Bahçe tabanındaki yabancı ot durumu, sulama veya toprak riskleri)
"""

        parts.append({"text": ziraat_uzmani_prompt})

        # Gemini modelini çağırıyoruz
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[{"parts": parts}]
        )

        rapor = response.text

        # Satır bazlı parser (Rapor çıktısını ayrıştırır)
        def satir_deger(anahtar):
            for satir in rapor.split("\n"):
                if satir.strip().startswith(anahtar + ":"):
                    return satir.replace(anahtar + ":", "").strip()
            return ""

        hastalik_adi = satir_deger("HASTALIK") or yolo_etiket
        if hastalik_adi.startswith("("):
            hastalik_adi = yolo_etiket

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