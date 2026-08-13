"""
signal_tracker.py — AI vs Teknik Strateji Sinyal Takipçisi
===========================================================
Her analiz çalıştırıldığında AL sinyallerini (teknik skor + AI sentiment skoru)
kayıt altına alır. N gün sonra fiyatı kontrol ederek gerçek getiriyi ölçer.

Bu sayede zamanla:
  - "Saf teknik" sinyallerin ortalama getirisini
  - "AI katkılı" sinyallerin ortalama getirisini
  - AI'ın kaç sinyali olumlu/olumsuz yönde etkilediğini
anlayabiliriz.

Dosya: signal_log.json
"""

import json
import yfinance as yf
from datetime import datetime, timedelta, date
from pathlib import Path

SIGNAL_LOG_FILE = "signal_log.json"
DEFAULT_EVAL_DAYS = [5, 10, 20]   # sinyal sonrası kaç günde ölçüm yapılır


# ═══════════════════════════════════════════════════════════════════ #
#  DOSYA YÖNETİMİ
# ═══════════════════════════════════════════════════════════════════ #

def _load_log() -> list[dict]:
    if not Path(SIGNAL_LOG_FILE).exists():
        return []
    try:
        with open(SIGNAL_LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


def _save_log(signals: list[dict]):
    try:
        with open(SIGNAL_LOG_FILE, 'w', encoding='utf-8') as f:
            json.dump(signals, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e:
        print(f"  [HATA] signal_log.json kaydedilemedi: {e}")


# ═══════════════════════════════════════════════════════════════════ #
#  SİNYAL KAYIT
# ═══════════════════════════════════════════════════════════════════ #

def record_signals(recommendations: list[dict], sentiment_results: dict = None):
    """
    Analiz sonuçlarındaki AL tavsiyelerini sinyal loğuna kaydeder.

    Args:
        recommendations : analyze_stocks() çıktısı (teknik tavsiyeler)
        sentiment_results: {'THYAO': {skor, etiket, ...}, ...}  (opsiyonel)
    """
    signals = _load_log()
    today   = datetime.now().date().isoformat()
    new_count = 0

    for r in recommendations:
        ticker = r.get('Hisse', '')
        if not ticker:
            continue

        # Bugün aynı ticker için zaten kayıt var mı?
        already = any(
            s['ticker'] == ticker and s['tarih'] == today
            for s in signals
        )
        if already:
            continue

        sent = (sentiment_results or {}).get(ticker, {})
        teknik_skor  = r.get('Skor', 0)
        ai_skor      = int(sent.get('skor', 0)) if sent else 0
        efektif_skor = teknik_skor + ai_skor

        sinyal = {
            'id'            : f"{ticker}_{today}",
            'tarih'         : today,
            'ticker'        : ticker,
            'giris_fiyati'  : r.get('Fiyat', 0),
            'teknik_skor'   : teknik_skor,
            'teknik_sinyal' : r.get('Sinyal', ''),
            'ai_skor'       : ai_skor,
            'ai_etiket'     : sent.get('etiket', 'NOTR') if sent else 'YOK',
            'ai_ozet'       : sent.get('ozet', '')[:60] if sent else '',
            'efektif_skor'  : efektif_skor,
            # Ölçüm sonuçları (sonradan doldurulur)
            'sonuclar'      : {}   # {'5g': {'fiyat': X, 'getiri_pct': Y}, ...}
        }
        signals.append(sinyal)
        new_count += 1

    _save_log(signals)
    return new_count


# ═══════════════════════════════════════════════════════════════════ #
#  SONUÇ GÜNCELLEME
# ═══════════════════════════════════════════════════════════════════ #

def update_outcomes(eval_days: list[int] = None):
    """
    Kaydedilmiş sinyallerin fiyat sonuçlarını günceller.
    yfinance'ten güncel kapanış fiyatları çekilir.

    Args:
        eval_days: Kaç gün sonra ölçülsün (ör: [5, 10, 20])

    Returns:
        int: Güncellenen kayıt sayısı
    """
    if eval_days is None:
        eval_days = DEFAULT_EVAL_DAYS

    signals  = _load_log()
    updated  = 0
    today    = datetime.now().date()

    # Güncellenmesi gereken ticker'ları topla
    pending = {}   # ticker -> [sinyal_index_listesi]
    for i, s in enumerate(signals):
        tarih = date.fromisoformat(s['tarih'])
        for n in eval_days:
            key = f"{n}g"
            if key not in s.get('sonuclar', {}):
                hedef = tarih + timedelta(days=n)
                if today >= hedef:
                    pending.setdefault(s['ticker'], []).append((i, n))

    if not pending:
        return 0

    # Fiyatları toplu çek
    print(f"  {len(pending)} hisse için geçmiş fiyatlar çekiliyor...")
    for ticker, entries in pending.items():
        try:
            # Sinyal tarihinden itibaren yeterli veriyi çek
            earliest_idx = min(e[0] for e in entries)
            start = date.fromisoformat(signals[earliest_idx]['tarih'])
            fetch_start = start - timedelta(days=5)
            fetch_end   = today + timedelta(days=1)

            df = yf.download(
                f"{ticker}.IS",
                start=fetch_start.isoformat(),
                end=fetch_end.isoformat(),
                progress=False,
                auto_adjust=False
            )
            if df.empty:
                continue

            close = df['Close'].squeeze()

            for idx, n_days in entries:
                s = signals[idx]
                tarih  = date.fromisoformat(s['tarih'])
                hedef  = tarih + timedelta(days=n_days)
                key    = f"{n_days}g"

                # Hedef tarihte veya sonrasındaki ilk kapanışı al
                future_prices = close[close.index.date >= hedef]
                if future_prices.empty:
                    continue

                hedef_fiyat = float(future_prices.iloc[0])
                giris       = s.get('giris_fiyati', 0)
                getiri      = ((hedef_fiyat - giris) / giris * 100) if giris > 0 else 0

                if 'sonuclar' not in signals[idx]:
                    signals[idx]['sonuclar'] = {}

                signals[idx]['sonuclar'][key] = {
                    'fiyat'      : round(hedef_fiyat, 2),
                    'getiri_pct' : round(getiri, 2),
                    'tarih'      : hedef.isoformat()
                }
                updated += 1

        except Exception:
            continue

    _save_log(signals)
    return updated


# ═══════════════════════════════════════════════════════════════════ #
#  PERFORMANS RAPORU
# ═══════════════════════════════════════════════════════════════════ #

def generate_performance_report(eval_days: list[int] = None) -> dict:
    """
    Kaydedilen sinyalleri analiz eder ve AI katkısını ölçer.

    Returns:
        dict: {
            'toplam_sinyal': int,
            'donem_analizi': {
                '5g': {
                    'teknik_only_ort': float,   # AI skoru 0 olan sinyaller
                    'ai_pozitif_ort' : float,   # AI skoru > 0 olan sinyaller
                    'ai_negatif_ort' : float,   # AI skoru < 0 olan sinyaller
                    'ai_kazandirdi_pct': float  # AI+ sinyaller > AI-siz sinyaller mi?
                }, ...
            },
            'en_iyi': list,
            'en_kotu': list
        }
    """
    if eval_days is None:
        eval_days = DEFAULT_EVAL_DAYS

    signals = _load_log()
    if not signals:
        return {'hata': 'Henüz kayıtlı sinyal yok.'}

    rapor = {
        'toplam_sinyal': len(signals),
        'donem_analizi': {},
        'en_iyi': [],
        'en_kotu': []
    }

    for n in eval_days:
        key = f"{n}g"
        teknik_only = []   # ai_skor == 0
        ai_pozitif  = []   # ai_skor > 0
        ai_negatif  = []   # ai_skor < 0

        for s in signals:
            sonuc = s.get('sonuclar', {}).get(key)
            if not sonuc:
                continue
            getiri   = sonuc['getiri_pct']
            ai_skor  = s.get('ai_skor', 0)

            if ai_skor == 0:
                teknik_only.append(getiri)
            elif ai_skor > 0:
                ai_pozitif.append(getiri)
            else:
                ai_negatif.append(getiri)

        def ort(lst):
            return round(sum(lst) / len(lst), 2) if lst else None

        t_ort = ort(teknik_only)
        p_ort = ort(ai_pozitif)
        n_ort = ort(ai_negatif)

        ai_fark = None
        if p_ort is not None and t_ort is not None:
            ai_fark = round(p_ort - t_ort, 2)

        rapor['donem_analizi'][key] = {
            'teknik_only_sinyal_sayisi': len(teknik_only),
            'ai_pozitif_sinyal_sayisi' : len(ai_pozitif),
            'ai_negatif_sinyal_sayisi' : len(ai_negatif),
            'teknik_only_ort_getiri'   : t_ort,
            'ai_pozitif_ort_getiri'    : p_ort,
            'ai_negatif_ort_getiri'    : n_ort,
            'ai_katkisi_pct'           : ai_fark,   # + ise AI faydalı
        }

    # En iyi / en kötü sinyaller (20 günlük getiriye göre)
    olcumlu = [
        s for s in signals
        if s.get('sonuclar', {}).get('20g')
    ]
    olcumlu.sort(key=lambda x: x['sonuclar']['20g']['getiri_pct'], reverse=True)
    rapor['en_iyi']  = olcumlu[:5]
    rapor['en_kotu'] = olcumlu[-5:][::-1]

    return rapor


def print_performance_report():
    """Performans raporunu formatlı olarak ekrana basar."""
    print("\nSinyal sonuçları güncelleniyor...")
    guncellenen = update_outcomes()
    print(f"  {guncellenen} yeni ölçüm tamamlandı.")

    rapor = generate_performance_report()

    if 'hata' in rapor:
        print(f"\n  {rapor['hata']}")
        print("  Not: Önce Piyasa Analizi (Menü 2) çalıştırın; sinyaller kaydedilecek.")
        return

    print("\n" + "=" * 80)
    print("  🧪 AI vs TEKNİK ANALİZ — KARŞILAŞTIRMALI PERFORMANS RAPORU")
    print("=" * 80)
    print(f"  Toplam kayıtlı sinyal: {rapor['toplam_sinyal']}")
    print()

    for donem, veri in rapor['donem_analizi'].items():
        print(f"  📅 {donem.upper()} DÖNEM SONUÇLARI")
        print("  " + "-" * 50)

        t = veri['teknik_only_ort_getiri']
        p = veri['ai_pozitif_ort_getiri']
        n = veri['ai_negatif_ort_getiri']
        katkisi = veri['ai_katkisi_pct']

        t_str = f"%{t:>+.2f}" if t is not None else "Veri yok"
        p_str = f"%{p:>+.2f}" if p is not None else "Veri yok"
        n_str = f"%{n:>+.2f}" if n is not None else "Veri yok"

        print(f"  Saf Teknik (AI skoru=0)  : Ort. Getiri = {t_str}  ({veri['teknik_only_sinyal_sayisi']} sinyal)")
        print(f"  AI Destekli (AI skoru>0) : Ort. Getiri = {p_str}  ({veri['ai_pozitif_sinyal_sayisi']} sinyal)")
        print(f"  AI Baskılı  (AI skoru<0) : Ort. Getiri = {n_str}  ({veri['ai_negatif_sinyal_sayisi']} sinyal)")

        if katkisi is not None:
            isaretli = f"%{katkisi:>+.2f}"
            yorum = "✅ AI KATKI SAĞLIYOR" if katkisi > 0 else "⚠️  AI KATKI SAĞLAMIYOR"
            print(f"\n  AI Katkısı (AI+ - Teknik): {isaretli}  →  {yorum}")
        print()

    # En iyi sinyaller
    if rapor['en_iyi']:
        print("  🏆 EN İYİ 5 SİNYAL (20 gün getirisi)")
        print("  " + "-" * 50)
        _print_signal_table(rapor['en_iyi'], '20g')

    # En kötü sinyaller
    if rapor['en_kotu']:
        print("\n  ⛔ EN KÖTÜ 5 SİNYAL (20 gün getirisi)")
        print("  " + "-" * 50)
        _print_signal_table(rapor['en_kotu'], '20g')

    print("=" * 80)
    print("  NOT: Bu rapor ileriye dönük (forward test) gerçek verilere dayanır.")
    print("  Yeterli sonuç birikimi için birkaç hafta beklenmesi gerekir.")
    print("=" * 80)


def _print_signal_table(sigs: list[dict], key: str):
    print(f"  {'Ticker':<8} {'Tarih':<12} {'Giriş':>8} {'Çıkış':>8} {'Getiri':>8} {'AI Skor':>8} {'Etiket':<14}")
    print("  " + "-" * 70)
    for s in sigs:
        sonuc = s.get('sonuclar', {}).get(key, {})
        getiri_str = f"%{sonuc.get('getiri_pct', 0):>+.2f}" if sonuc else "-"
        print(
            f"  {s['ticker']:<8} {s['tarih']:<12} "
            f"{s['giris_fiyati']:>8.2f} "
            f"{sonuc.get('fiyat', 0):>8.2f} "
            f"{getiri_str:>8} "
            f"{s.get('ai_skor', 0):>+8} "
            f"{s.get('ai_etiket', 'YOK'):<14}"
        )
