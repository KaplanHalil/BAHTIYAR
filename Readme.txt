╔══════════════════════════════════════════════════════════════════════════════╗
║                     BAHTIYAR PORTFÖY YÖNETİM SİSTEMİ                         ║
║         Gelişmiş Analiz ve Tavsiye Motoru ile Akıllı Yatırım Asistanı        ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Borsa • Alım-Satım • Hesap • Tasarruf • İhtiyat • Yatırım • Analiz • Rapor  ║
╚══════════════════════════════════════════════════════════════════════════════╝

🎯 PROJE AÇIKLAMASI
═════════════════════════════════════════════════════════════════════════════════

BAHTIYAR, Türkiye Borsa İstanbul (BIST) hisselerinin teknik analizini yaparak
yatırım tavsiyesi veren bir Python-tabanlı portföy yönetim sistemidir.

⭐ ÖZELLİKLER:
─────────────────────────────────────────────────────────────────────────────────
✓ BIST100 Hisselerine Teknik Analiz
  - RSI, MACD, SMA50/200, Bollinger Bantları, Stochastic Oscillator
  - Ağırlıklı puanlama sistemi (Max 10 puan)
  - Al/Tut/Sat Tavsiyesi

✓ ALTIN VE GÜMÜŞ TİCARETİ (KUVEYT TÜRK FİYATLARI)
  - Altın (GC=F) ve Gümüş (SI=F) futures analizi
  - TCMB API ile güncel fiyatlar
  - Hisselerle aynı portföyde yönetim
  - Gram cinsinden satın alma ve satış

✓ PORTFÖY YÖNETİMİ
  - Çoklu portföy desteği (birden fazla hesap)
  - Hisse ve metal karışık portföy
  - İşlem geçmişi tutma (Kar/Zarar hesaplama)
  - Portföy değerlemesi

✓ TAVSIYE SİSTEMİ
  - Hisseler ve değerli metaller için birleştirilmiş analiz
  - Bütçeye uygun optimal portföy önerisi
  - Sinyal gücü derecelendirmesi (Güçlü/Orta/Zayıf)


🚀 BAŞLARKEN
═════════════════════════════════════════════════════════════════════════════════

1. Ortamı Hazırla:
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # veya
   venv\Scripts\activate  # Windows

2. Gerekli Paketleri Yükle:
   pip install -r requirements.txt

3. Programı Çalıştır:
   python main.py


📋 MENÜ SEÇENEKLERI
═════════════════════════════════════════════════════════════════════════════════

1. Bütçeyi Görüntüle / Güncelle
   → Başlangıç bütçenizi girin veya güncelleyin

2. Piyasayı Analiz Et ve Alım Tavsiyesi Ver ⭐
   → Hisseler + Altın/Gümüş analiz ve tavsiye
   → Bütçeye uygun portföy önerisi
   → Manuel alım seçeneği

3. Portföyümü Görüntüle ve Sat/Tut Tavsiyeleri Al
   → Mevcut portföyü göster
   → Hisse satış tavsiyesi
   → Metal satış seçeneği
   → Kar/Zarar hesaplama

4. Portföye Manuel Hisse/Metal Ekle
   → Kendini alındığını bildirdiğin hisseler ekle
   → Altın/Gümüş gramı ekle

5. Mevcut Portföyü Sıfırla veya Sil
   → Portföyü temizle veya tamamen sil

6. Diğer Portföye Geç
   → Birden fazla portföy yönet

7. Backtest Modu (Son 2 Yıl Test) 🔬
   → Sistemin gerçek performansını test et
   → Son 2 yıl verisiyle simülasyon
   → Başlangıç bütçesi belirle
   → Detaylı rapor al

8. Çıkış
   → Programdan çık


💰 ALTUN VE GÜMÜŞ KULLANIMI
═════════════════════════════════════════════════════════════════════════════════

- Altın kodu: ALTIN
- Gümüş kodu: GUMUS
- Birim: Gram
- Fiyat kaynağı: TCMB API ve Yahoo Finance

Portföy optimizasyonunda:
  - Hisse: "x lot @ y TL/lot"
  - Metal: "x gram @ y TL/gram"

🔬 BACKTEST MODU - SİSTEM PERFORMANSI TESTİ
═════════════════════════════════════════════════════════════════════════════════

"Backtest Modu" seçeneğiyle sisteminizi gerçek verilerle test edebilirsiniz.

📊 Backtest Nasıl Çalışır:
─────────────────────────────────────────────────────────────────────────────────
1. Son 2 yılın (veya özel dönem) Borsa İstanbul verilerini indirir
2. Başlangıç bütçesini belirlersiniz (ör: 10,000 TL)
3. Sistem her gün:
   - Tavsiye algoritmasını çalıştırır
   - Tavsiyeye göre ALIM yapar
   - Sonraki gün portföyü değerlendirir
   - SAT tavsiyesine göre SATIN ALIR
   - Kalan nakit ile yeni alımlar yapabilir
4. 2 yıl simülasyon sonunda:
   - Başlangıç ve Final Portföy Değeri
   - Toplam Kar/Zarar (TL ve %)
   - Yapılan İşlemlerin Detaylı Listesi
   - Son Yatırım Pozisyonları

💡 Backtest Örneği:
─────────────────────────────────────────────────────────────────────────────────
Başlangıç Bütçesi: 10,000 TL
Test Dönemi: 730 gün (2 yıl)
Max Hisse: 3

Sonuç Örneği:
├─ Başlangıç: 10,000 TL
├─ Son Değer: 12,500 TL
├─ Kar/Zarar: +2,500 TL (+25%)
├─ Alım Sayısı: 147
├─ Satış Sayısı: 89
└─ Gerçekleşen Kar: +1,850 TL

📄 Rapor Dosyası:
─────────────────────────────────────────────────────────────────────────────────
Backtest tamamlandıktan sonra "backtest_report_[tarih].txt" dosyası oluşturulur:
- Test özeti ve istatistikleri
- Maksimum/Minimum portföy değerleri
- Son 50 işlemin detaylı listesi
- Aktif yatırım pozisyonları
- Gerçekleşen kar/zarar detayları

⚠️ Önemli Notlar:
─────────────────────────────────────────────────────────────────────────────────
- Backtest geçmiş verilerle yapılan teorik bir testtir
- Gerçek yatırımda farklı sonuçlar çıkabilir
- Slippage, komisyon, vergiler hesaba katılmamıştır
- Likidite problemleri simüle edilmemiştir
- Baktest sonuçları geleceğin performansını garantilemez

📊 TEKNIK İNDİKATÖRLER
═════════════════════════════════════════════════════════════════════════════════

RSI (Relative Strength Index):
  → 30 altında: Aşırı satım (AL sinyali)
  → 70 üzerinde: Aşırı alım (SAT sinyali)

MACD (Moving Average Convergence Divergence):
  → Taze kesişim: Güçlü AL sinyali
  → Negatif: Zayıf SAT sinyali

SMA (Simple Moving Averages):
  → Fiyat > SMA50: Kısa vadeli yükseliş trendi
  → SMA50 > SMA200: Golden Cross (uzun vadeli yükseliş)

Bollinger Bands:
  → Alt banda temas: Fiyat ucuzlamış (AL fırsatı)
  → Sıkışma: Volatilite artışı beklenir

Volatilite:
  → Yüksek volatilite: Risk uyarısı
  → Değerli metaller için önemli risk göstergesi


📁 DOSYA YAPISI
═════════════════════════════════════════════════════════════════════════════════

main.py - Ana program, menü sistemi
data_fetcher.py - Veri çekme (yfinance, TCMB)
analyzer.py - Teknik analiz motoru
optimizer.py - Portföy optimizasyonu
budget_manager.py - Bütçe ve portföy yönetimi
logger.py - İşlem geçmişi tutma
precious_metals_fetcher.py - Altın/Gümüş fiyatları
requirements.txt - Gerekli kütüphaneler

[isim]_butce.json - Kullanıcı bütçesi ve portföyü
[isim]_islem_gecmisi.txt - İşlem geçmişi


🔐 NOTLAR
═════════════════════════════════════════════════════════════════════════════════

- Programda verilen tavsiyeler eğitim amaçlıdır
- Reel yatırım kararını yalnızca siz verebilirsiniz
- Borsa riski taşır, dikkatli karar verin
- İşlem hacimleri, komisyonlar ve vergileri göz önüne alın
- Bu program için finansal danışmanlık hizmeti sağlanmamaktadır


💾 GÜNCELLEMELER
═════════════════════════════════════════════════════════════════════════════════

v2.1 - Backtest Modu Eklendi (Sistem Performans Testi)
v2.0 - Altın ve Gümüş Desteği Eklendi (KUVEYT TÜRK FİYATLARI)
v1.0 - İlk Sürüm (Sadece BIST Hisseleri)
