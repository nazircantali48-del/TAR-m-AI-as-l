import urllib.request
import json

def hava_durumu_al(enlem: float = 37.0, boylam: float = 35.0) -> dict:
    """Open-Meteo API ile narenciye bahçesinin koordinatlarına özel hava durumu verilerini çeker."""
    try:
        # API verilerini saatlik trendlerden (hourly) çekerek günlük ve haftalık analizleri daha doğru yapıyoruz.
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={enlem}&longitude={boylam}"
            f"&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
            f"&hourly=relative_humidity_2m"  # Nem trendini saatlik alıp maksimumu koddos hesaplayacağız
            f"&daily=temperature_2m_max,temperature_2m_min,precipitation_sum"
            f"&forecast_days=7&timezone=auto"
        )
        with urllib.request.urlopen(url, timeout=5) as response:
            veri = json.loads(response.read())

        guncel = veri.get("current", {})
        gunluk = veri.get("daily", {})
        saatlik = veri.get("hourly", {})

        # Saatlik nem verileri içinden önümüzdeki günlerin maksimum nem oranını güvenli bir şekilde süzüyoruz.
        saatlik_nem_listesi = saatlik.get("relative_humidity_2m", [0])
        max_nem_7gun = max(saatlik_nem_listesi) if saatlik_nem_listesi else guncel.get("relative_humidity_2m", 0)

        return {
            "basarili": True,
            "sicaklik": guncel.get("temperature_2m", 0),
            "nem": guncel.get("relative_humidity_2m", 0),
            "yagis": guncel.get("precipitation", 0),
            "ruzgar": guncel.get("wind_speed_10m", 0),
            "7gun_max_nem": max_nem_7gun,
            "7gun_toplam_yagis": sum(gunluk.get("precipitation_sum", [0])),
            "ozet": f"Sıcaklık: {guncel.get('temperature_2m')}°C, Nem: {guncel.get('relative_humidity_2m')}%, Yağış: {guncel.get('precipitation')}mm, Rüzgar: {guncel.get('wind_speed_10m')}km/h"
        }
    except Exception as e:
        return {
            "basarili": False,
            "ozet": "Hava durumu verileri API hatası nedeniyle şu an alınamadı.",
            "hata": str(e)
        }

def hastalik_riski_hesapla(nem: float, sicaklik: float) -> str:
    """Hava koşullarına göre Akdeniz/Ege narenciye hastalıkları risk matrisini hesaplar."""
    riskler = []

    # Akdeniz mantar ve bakteri hastalıkları tetiklenme şartları (İsli Küf, Melanose, Yağlı Nokta)
    if nem > 85:
        riskler.append("Kritik nem seviyesi (%{:.0f}): Mantar sporlarının yaprağa tutunması ve İsli Küf yayılımı için ortam çok uygun.".format(nem))
    
    if 20 <= sicaklik <= 28 and nem > 75:
        riskler.append("Ilık ve nemli hava kombinasyonu: Turunçgillerde Yağlı Nokta (Greasy Spot) ve Melanose hastalık riskini ciddi oranda artırıyor.")
        
    if ruzgar := 0 > 25 and nem > 70:  # Rüzgar parametresi ana koda entegre edilirse tetiklenebilir
        riskler.append("Yüksek rüzgar ve nem: Dal sürtünmelerinden kaynaklı mikro yaralardan Turunçgil Kanseri ve Uçkurutan bakterisinin sızma riski var.")

    if sicaklik > 36:
        riskler.append("Aşırı yüksek sıcaklık bitkiyi stoma kapatmaya zorlar; sıcaklık stresi bitkinin bağışıklık direncini düşürüyor.")
        
    if sicaklik < 4:
        riskler.append("Düşük sıcaklık sınırı: Don riski mevcut. Limon ve portakal sürgünlerinde doku hasarı oluşabilir, Uçkurutan hastalığına zemin hazırlar.")

    if not riskler:
        return "Mevcut meteorolojik koşullar narenciye zararlıları ve hastalık gelişimi için düşük risk taşıyor."
        
    return " | ".join(riskler)