import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, SMAIndicator, ADXIndicator
from ta.volatility import BollingerBands, AverageTrueRange
from ta.volume import MFIIndicator

# ============================================================================
#  GELİŞMİŞ TEKNİK ANALİZ VE RİSK YÖNETİM MOTORU
#  Kullanılan Göstergeler ve Analizler:
#    1. RSI (14) & Pozitif/Negatif Uyumsuzluk (Divergence)
#    2. MACD (12,26,9) - Taze kesişim ve trend ivmesi
#    3. SMA 50 & SMA 200 - Trend takibi, Golden/Death Cross & Eğim
#    4. Bollinger Bantları (20,2) - Volatilite ve kanal sıkışması
#    5. Stochastic Oscillator (14,3) - Momentum doğrulama
#    6. ADX (14) - Trend gücü ve yatay piyasa (testere) filtresi
#    7. MFI (14) - Akıllı Para Akışı Endeksi (Money Flow Index)
#    8. ATR (14) - Dinamik Stop-Loss ve Hedef Fiyat (Risk/Ödül) hesabı
#    9. Göreceli Güç (Relative Strength) - BIST100 endeksine karşı Alpha
#   10. Hacim Analizi - İşlem hacmi ve likidite doğrulaması
# ============================================================================

MAX_SKOR = 15  # Ağırlıklı puanlama sistemindeki maksimum puan
MIN_STOCK_HISTORY_DAYS = 200
MIN_AVG_TURNOVER_TL = 3_000_000
MIN_BUY_SCORE = 6
MARKET_INDEX = 'XU100.IS'
MARKET_REGIME_SMA_DAYS = 200


def get_market_regime(data_dict):
    """BIST genel piyasa rejimini döndürür. Endeks yoksa hisse alımını engellemez."""
    df = data_dict.get(MARKET_INDEX)
    if df is None or df.empty or len(df) < MARKET_REGIME_SMA_DAYS:
        return {
            'available': False,
            'allow_stocks': True,
            'reason': 'BIST endeks verisi yok; hisse filtresi uygulanmadı.'
        }

    try:
        close_prices = df['Close'].squeeze()
        if isinstance(close_prices, pd.DataFrame):
            close_prices = close_prices.iloc[:, 0]
        close_prices = close_prices.dropna()
        if len(close_prices) < MARKET_REGIME_SMA_DAYS:
            return {
                'available': False,
                'allow_stocks': True,
                'reason': 'BIST endeks geçmişi yetersiz; hisse filtresi uygulanmadı.'
            }

        sma200 = SMAIndicator(close=close_prices, window=MARKET_REGIME_SMA_DAYS).sma_indicator()
        last_price = float(close_prices.iloc[-1])
        last_sma200 = float(sma200.iloc[-1])
        allow_stocks = last_price >= last_sma200

        return {
            'available': True,
            'allow_stocks': allow_stocks,
            'index_price': last_price,
            'sma200': last_sma200,
            'reason': 'BIST endeksi SMA200 üzerinde.' if allow_stocks else 'BIST endeksi SMA200 altında; hisse alımları kapatıldı.'
        }
    except Exception:
        return {
            'available': False,
            'allow_stocks': True,
            'reason': 'BIST endeks rejimi hesaplanamadı; hisse filtresi uygulanmadı.'
        }


def analyze_stocks(data_dict):
    """
    BIST hisselerini gelişmiş teknik analiz, risk yönetimi (ATR) ve
    puanlama motoru ile değerlendirir (Maks: 15 puan).
    """
    market_regime = get_market_regime(data_dict)
    if not market_regime['allow_stocks']:
        return []

    # BIST100 endeks getirisini hesapla (Göreceli güç hesabı için)
    bist_ret_20d = 0.0
    bist_df = data_dict.get(MARKET_INDEX)
    if bist_df is not None and not bist_df.empty:
        try:
            bist_close = bist_df['Close'].squeeze()
            if isinstance(bist_close, pd.DataFrame):
                bist_close = bist_close.iloc[:, 0]
            bist_close = bist_close.dropna()
            if len(bist_close) >= 20:
                b_now = float(bist_close.iloc[-1])
                b_prev = float(bist_close.iloc[-20])
                if b_prev > 0:
                    bist_ret_20d = (b_now - b_prev) / b_prev
        except Exception:
            bist_ret_20d = 0.0

    recommendations = []

    for ticker, df in data_dict.items():
        if ticker == MARKET_INDEX or not ticker.endswith('.IS'):
            continue

        if len(df) < MIN_STOCK_HISTORY_DAYS:
            continue

        try:
            close_prices = df['Close'].squeeze()
            if isinstance(close_prices, pd.DataFrame):
                close_prices = close_prices.iloc[:, 0]

            high_prices = df['High'].squeeze()
            if isinstance(high_prices, pd.DataFrame):
                high_prices = high_prices.iloc[:, 0]

            low_prices = df['Low'].squeeze()
            if isinstance(low_prices, pd.DataFrame):
                low_prices = low_prices.iloc[:, 0]

            volume = df['Volume'].squeeze() if 'Volume' in df.columns else None
            if isinstance(volume, pd.DataFrame):
                volume = volume.iloc[:, 0]

            close_prices = close_prices.dropna()
            high_prices = high_prices.dropna()
            low_prices = low_prices.dropna()

            if len(close_prices) < MIN_STOCK_HISTORY_DAYS:
                continue

            last_price = float(close_prices.iloc[-1])

            # ---- GÖSTERGE HESAPLAMALARI ----

            # 1. RSI (14 Günlük)
            rsi = RSIIndicator(close=close_prices, window=14).rsi()
            last_rsi = float(rsi.iloc[-1])

            # 2. MACD
            macd_indicator = MACD(close=close_prices)
            macd_diff = macd_indicator.macd_diff()
            last_macd_diff = float(macd_diff.iloc[-1])
            prev_macd_diff = float(macd_diff.iloc[-2]) if len(macd_diff) > 1 else 0

            # 3. SMA 50 & 200
            sma50 = SMAIndicator(close=close_prices, window=50).sma_indicator()
            last_sma50 = float(sma50.iloc[-1])

            has_sma200 = len(close_prices) >= 200
            last_sma200 = None
            sma50_slope = 0.0
            if has_sma200:
                sma200 = SMAIndicator(close=close_prices, window=200).sma_indicator()
                last_sma200 = float(sma200.iloc[-1])
                sma50_prev = float(sma50.iloc[-6]) if len(sma50) >= 6 and not pd.isna(sma50.iloc[-6]) else last_sma50
                sma50_slope = (last_sma50 - sma50_prev) / sma50_prev if sma50_prev > 0 else 0

            # 4. Bollinger Bantları (20 günlük, 2 standart sapma)
            bb = BollingerBands(close=close_prices, window=20, window_dev=2)
            bb_lower = float(bb.bollinger_lband().iloc[-1])
            bb_upper = float(bb.bollinger_hband().iloc[-1])
            bb_middle = float(bb.bollinger_mavg().iloc[-1])
            bb_width = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0

            # 5. Stochastic Oscillator (14, 3)
            stoch = StochasticOscillator(
                high=high_prices, low=low_prices, close=close_prices,
                window=14, smooth_window=3
            )
            last_stoch_k = float(stoch.stoch().iloc[-1])

            # 6. ADX (14) - Trend Gücü
            adx_val = 0.0
            try:
                adx_ind = ADXIndicator(high=high_prices, low=low_prices, close=close_prices, window=14)
                adx_series = adx_ind.adx().dropna()
                if len(adx_series) > 0:
                    adx_val = float(adx_series.iloc[-1])
            except Exception:
                adx_val = 0.0

            # 7. MFI (14) - Akıllı Para Akışı
            last_mfi = 50.0
            if volume is not None and len(volume) >= 14:
                try:
                    mfi_ind = MFIIndicator(
                        high=high_prices, low=low_prices, close=close_prices,
                        volume=volume, window=14
                    )
                    mfi_series = mfi_ind.money_flow_index().dropna()
                    if len(mfi_series) > 0:
                        last_mfi = float(mfi_series.iloc[-1])
                except Exception:
                    last_mfi = 50.0

            # 8. ATR (14) - Volatilite ve Risk Hesaplama
            last_atr = 0.0
            try:
                atr_ind = AverageTrueRange(high=high_prices, low=low_prices, close=close_prices, window=14)
                atr_series = atr_ind.average_true_range().dropna()
                if len(atr_series) > 0:
                    last_atr = float(atr_series.iloc[-1])
            except Exception:
                last_atr = 0.0

            if last_atr > 0:
                stop_loss = round(max(last_price - 2.0 * last_atr, last_price * 0.85), 2)
                target_price = round(last_price + 3.0 * last_atr, 2)
                risk = last_price - stop_loss
                reward = target_price - last_price
                risk_reward = round(reward / risk, 2) if risk > 0 else 1.5
            else:
                stop_loss = round(last_price * 0.95, 2)
                target_price = round(last_price * 1.10, 2)
                risk_reward = 2.0

            # 9. Hacim ve Likidite Analizi
            volume_confirmed = False
            avg_turnover = 0.0
            if volume is not None and len(volume) >= 20:
                avg_volume = float(volume.iloc[-20:].mean())
                last_volume = float(volume.iloc[-1])
                volume_confirmed = last_volume > avg_volume * 1.2
                avg_turnover = avg_volume * last_price

            price_change_20d = 0.0
            stock_ret_20d = 0.0
            if len(close_prices) >= 20:
                price_20d_ago = float(close_prices.iloc[-20])
                if price_20d_ago > 0:
                    stock_ret_20d = (last_price - price_20d_ago) / price_20d_ago
                    price_change_20d = stock_ret_20d * 100

            if avg_turnover and avg_turnover < MIN_AVG_TURNOVER_TL:
                continue

            trend_ok = bool(
                has_sma200
                and last_sma200 is not None
                and last_price > last_sma200 * 0.98
                and last_sma50 > last_sma200 * 0.98
            )
            falling_knife = price_change_20d < -12 and last_macd_diff <= 0
            if falling_knife:
                continue

            # 10. RSI Pozitif Uyumsuzluk (Bullish Divergence) Tespiti
            bullish_divergence = False
            if len(close_prices) >= 20 and len(rsi) >= 20:
                past_min_price = float(close_prices.iloc[-20:-5].min())
                recent_min_price = float(close_prices.iloc[-5:].min())
                past_min_rsi = float(rsi.iloc[-20:-5].min())
                recent_min_rsi = float(rsi.iloc[-5:].min())
                if recent_min_price < past_min_price and recent_min_rsi > past_min_rsi + 2.0:
                    bullish_divergence = True

            # 11. Endekse Göre Göreceli Güç (Relative Strength / Alpha)
            rel_strength_ok = (stock_ret_20d - bist_ret_20d) > 0.04

            # ---- AĞIRLIKLI PUANLAMA SİSTEMİ (MAKS 15 PUAN) ----
            score = 0
            reasons = []

            # Kriter 1: RSI Analizi
            if last_rsi < 30 and trend_ok:
                score += 1
                reasons.append(f"RSI Aşırı Satım ({last_rsi:.1f})")
            elif 35 <= last_rsi <= 60:
                score += 1
                reasons.append(f"RSI Sağlıklı Bölge ({last_rsi:.1f})")
            elif last_rsi > 75:
                score -= 1

            # Kriter 2: MACD Analizi (Maks +2 puan)
            if last_macd_diff > 0 and prev_macd_diff <= 0:
                score += 2
                reasons.append("MACD Taze Kesişim ↑")
            elif last_macd_diff > 0:
                score += 1
                reasons.append("MACD Pozitif")

            # Kriter 3: Fiyat vs SMA50 (+1 puan)
            if last_price > last_sma50:
                score += 1
                reasons.append("Fiyat > SMA50")
            else:
                score -= 1

            # Kriter 4: Piyasa rejimi ve trend kalitesi
            if has_sma200 and last_sma200 is not None:
                if last_price > last_sma200:
                    score += 1
                    reasons.append("Fiyat > SMA200")
                else:
                    score -= 2

                if last_sma50 > last_sma200:
                    score += 2
                    reasons.append("Golden Cross Aktif")
                else:
                    score -= 2

                if sma50_slope > 0:
                    score += 1
                    reasons.append("SMA50 Yükseliyor")

            # Kriter 5: Bollinger Bantları
            if trend_ok and last_price <= bb_lower * 1.02:
                score += 1
                reasons.append("Trend İçinde Bollinger Alt Bandı")
            if bb_width < 0.05 and last_price > last_sma50:
                score += 1
                reasons.append("Bollinger Sıkışma")

            # Kriter 6: Stochastic Oscillator
            if last_stoch_k < 20:
                score += 1
                reasons.append(f"Stochastic Aşırı Satım ({last_stoch_k:.0f})")
            elif last_stoch_k > 80:
                score -= 1

            # Kriter 7: Hacim Doğrulaması
            if volume_confirmed and score >= 3:
                score += 1
                reasons.append("Hacim Doğrulaması ✓")

            # Kriter 8 (AŞAMA 2): ADX Trend Gücü
            if adx_val >= 25:
                score += 1
                reasons.append(f"Güçlü Trend (ADX={adx_val:.0f})")
            elif adx_val < 18 and score > 0:
                score -= 1
                reasons.append(f"Yatay Piyasa Riski (ADX={adx_val:.0f})")

            # Kriter 9 (AŞAMA 2): MFI Para Akışı Endeksi
            if last_mfi < 25:
                score += 1
                reasons.append(f"Para Akışı Aşırı Satım/Giriş (MFI={last_mfi:.0f})")
            elif 35 <= last_mfi <= 65:
                score += 1
            elif last_mfi > 80:
                score -= 1
                reasons.append(f"Para Çıkış Riski (MFI={last_mfi:.0f})")

            # Kriter 10 (AŞAMA 3): Pozitif RSI Uyumsuzluğu
            if bullish_divergence:
                score += 2
                reasons.append("Pozitif RSI Uyumsuzluğu ↑")

            # Kriter 11 (AŞAMA 3): Endeks Üstü Performans (Alpha)
            if rel_strength_ok:
                score += 1
                reasons.append("Endeks Üstü Performans (Alpha)")

            # Skoru sınırla
            score = max(score, 0)

            # Filtrele ve sonuçlara ekle
            if score >= MIN_BUY_SCORE and trend_ok:
                sinyal_gucu = "Güçlü" if score >= 9 else ("Orta" if score >= 6 else "Zayıf")
                recommendations.append({
                    'Hisse': ticker.replace('.IS', ''),
                    'Fiyat': last_price,
                    'RSI': last_rsi,
                    'Skor': score,
                    'Sinyal': sinyal_gucu,
                    'Nedenler': ", ".join(reasons),
                    'StopLoss': stop_loss,
                    'HedefFiyat': target_price,
                    'RiskOdul': risk_reward,
                    'AssetType': 'HISSE',
                    'Display': f"📊 {ticker.replace('.IS', '')}",
                    'Unit': 'lot'
                })

        except Exception:
            continue

    # En yüksek skora, ardından en düşük RSI'a göre sırala
    recommendations.sort(key=lambda x: (-x['Skor'], x['RSI']))
    return recommendations


def evaluate_portfolio(portfolio, data_dict):
    """
    Portföydeki hisseleri gelişmiş teknik analiz, trailing stop ve
    maliyet risk eşikleri ile değerlendirir. Sat/Tut/Güçlü Tut kararı verir.
    """
    evaluations = []

    for ticker, info in portfolio.items():
        yf_ticker = f"{ticker}.IS"
        if yf_ticker not in data_dict:
            continue

        df = data_dict[yf_ticker]
        if len(df) < 50:
            continue

        try:
            close_prices = df['Close'].squeeze()
            if isinstance(close_prices, pd.DataFrame):
                close_prices = close_prices.iloc[:, 0]

            high_prices = df['High'].squeeze()
            if isinstance(high_prices, pd.DataFrame):
                high_prices = high_prices.iloc[:, 0]

            low_prices = df['Low'].squeeze()
            if isinstance(low_prices, pd.DataFrame):
                low_prices = low_prices.iloc[:, 0]

            volume = df['Volume'].squeeze() if 'Volume' in df.columns else None
            if isinstance(volume, pd.DataFrame):
                volume = volume.iloc[:, 0]

            close_prices = close_prices.dropna()
            high_prices = high_prices.dropna()
            low_prices = low_prices.dropna()

            last_price = float(close_prices.iloc[-1])
            maliyet = info.get('maliyet', last_price)
            k_z = ((last_price - maliyet) / maliyet) * 100 if maliyet > 0 else 0.0

            # Gösterge hesaplamaları
            rsi = RSIIndicator(close=close_prices, window=14).rsi()
            last_rsi = float(rsi.iloc[-1])

            macd_indicator = MACD(close=close_prices)
            macd_diff = macd_indicator.macd_diff()
            last_macd_diff = float(macd_diff.iloc[-1])

            sma50 = SMAIndicator(close=close_prices, window=50).sma_indicator()
            last_sma50 = float(sma50.iloc[-1])

            bb = BollingerBands(close=close_prices, window=20, window_dev=2)
            bb_upper = float(bb.bollinger_hband().iloc[-1])

            stoch = StochasticOscillator(
                high=high_prices, low=low_prices, close=close_prices,
                window=14, smooth_window=3
            )
            last_stoch_k = float(stoch.stoch().iloc[-1])

            # MFI
            last_mfi = 50.0
            if volume is not None and len(volume) >= 14:
                try:
                    mfi_ind = MFIIndicator(high=high_prices, low=low_prices, close=close_prices, volume=volume, window=14)
                    mfi_series = mfi_ind.money_flow_index().dropna()
                    if len(mfi_series) > 0:
                        last_mfi = float(mfi_series.iloc[-1])
                except Exception:
                    last_mfi = 50.0

            # ATR ile Stop Düzeyi
            last_atr = 0.0
            try:
                atr_ind = AverageTrueRange(high=high_prices, low=low_prices, close=close_prices, window=14)
                atr_series = atr_ind.average_true_range().dropna()
                if len(atr_series) > 0:
                    last_atr = float(atr_series.iloc[-1])
            except Exception:
                last_atr = 0.0

            has_sma200 = len(close_prices) >= 200
            last_sma200 = None
            if has_sma200:
                sma200 = SMAIndicator(close=close_prices, window=200).sma_indicator()
                last_sma200 = float(sma200.iloc[-1])

            # Hacim analizi
            volume_spike_down = False
            if volume is not None and len(volume) >= 20:
                avg_volume = float(volume.iloc[-20:].mean())
                last_volume = float(volume.iloc[-1])
                if last_volume > avg_volume * 1.5:
                    price_change = (last_price - float(close_prices.iloc[-2])) / float(close_prices.iloc[-2])
                    if price_change < -0.02:
                        volume_spike_down = True

            # Negatif Uyumsuzluk (Bearish Divergence) Tespiti
            bearish_divergence = False
            if len(close_prices) >= 20 and len(rsi) >= 20:
                past_max_price = float(close_prices.iloc[-20:-5].max())
                recent_max_price = float(close_prices.iloc[-5:].max())
                past_max_rsi = float(rsi.iloc[-20:-5].max())
                recent_max_rsi = float(rsi.iloc[-5:].max())
                if recent_max_price > past_max_price and recent_max_rsi < past_max_rsi - 2.0:
                    bearish_divergence = True

            # ---- SATIŞ PUANLAMA SİSTEMİ ----
            sat_puani = 0
            reasons = []

            # 1. RSI Aşırı Alım
            if last_rsi > 80:
                sat_puani += 3
                reasons.append(f"RSI Aşırı Alım ({last_rsi:.1f}) ⚠")
            elif last_rsi > 70:
                sat_puani += 2
                reasons.append(f"RSI Yüksek ({last_rsi:.1f})")

            # 2. MACD Olumsuz
            if last_macd_diff < 0:
                sat_puani += 1
                reasons.append("MACD Negatif")

            # 3. SMA Kırılımları
            if last_price < last_sma50:
                sat_puani += 1
                reasons.append("Fiyat < SMA50")

            if has_sma200 and last_sma200 is not None and last_sma50 < last_sma200:
                sat_puani += 2
                reasons.append("Death Cross Aktif ✗")

            if has_sma200 and last_sma200 is not None and last_price < last_sma200:
                sat_puani += 2
                reasons.append("Fiyat < SMA200")

            # 4. Bollinger Üst Bandı
            if last_price >= bb_upper * 0.98:
                sat_puani += 1
                reasons.append("Bollinger Üst Bandı")

            # 5. Stochastic Yüksek
            if last_stoch_k > 80:
                sat_puani += 1
                reasons.append(f"Stochastic Yüksek ({last_stoch_k:.0f})")

            # 6. Yüksek Hacimli Düşüş
            if volume_spike_down:
                sat_puani += 2
                reasons.append("Yüksek Hacimli Düşüş ↓")

            # 7 (AŞAMA 2): MFI Para Çıkış Riski
            if last_mfi > 80:
                sat_puani += 1
                reasons.append(f"MFI Para Çıkış Riski ({last_mfi:.0f})")

            # 8 (AŞAMA 3): Negatif RSI Uyumsuzluğu
            if bearish_divergence:
                sat_puani += 2
                reasons.append("Negatif RSI Uyumsuzluğu ⚠️")

            # 9 (AŞAMA 1): Maliyet Risk & Trailing Stop Yönetimi
            if k_z <= -8.0:
                sat_puani += 2
                reasons.append(f"Disiplinli Stop-Loss Eşiği (%{k_z:.1f}) 🛑")
            elif k_z >= 15.0:
                sat_puani += 1
                reasons.append(f"Kâr Koruma / İz Süren Stop (%{k_z:.1f}) 🛡️")

            # ---- KARAR MATRİSİ ----
            if sat_puani >= 5:
                action = "Sat"
            elif sat_puani >= 3:
                action = "Dikkatli Tut"
            else:
                action = "Güçlü Tut"
                if not reasons:
                    reasons.append("Trend Olumlu ✓")

            # Önerilen Stop ve Kar Al Düzeyleri (Mevcut fiyata göre)
            trailing_stop = round(last_price - 1.5 * last_atr, 2) if last_atr > 0 else round(last_price * 0.95, 2)

            evaluations.append({
                'Hisse': ticker,
                'Durum': action,
                'Fiyat': last_price,
                'Maliyet': maliyet,
                'K/Z %': k_z,
                'Lot': info['lot'],
                'Sat Puanı': sat_puani,
                'TrailingStop': trailing_stop,
                'Nedenler': ", ".join(reasons)
            })

        except Exception:
            continue

    return evaluations


def analyze_all_assets(data_dict):
    """
    Tüm varlıklar (Hisseler) için analiz sonuçlarını döndürür.
    """
    return analyze_stocks(data_dict)


def enrich_with_sentiment(recommendations: list[dict],
                           sentiment_results: dict[str, dict]) -> list[dict]:
    """
    Teknik analiz tavsiyelerine AI haber duygu skoru ekler.

    Her tavsiye için:
      - 'Sentiment'    : ham sentiment dict
      - 'EfektiveSkor' : teknik skor + sentiment skoru
      - 'Nedenler'     : sentiment özeti eklenerek genişletilir

    Args:
        recommendations  : analyze_stocks() çıktısı
        sentiment_results: {'THYAO': {skor, guven, ozet, ...}, ...}

    Returns:
        Zenginleştirilmiş tavsiye listesi (skor'a göre yeniden sıralanmış)
    """
    from news_analyzer import ETIKET_SEMBOL

    enriched = []
    for r in recommendations:
        ticker = r['Hisse']
        sent = sentiment_results.get(ticker)
        r = dict(r)   # kopya al

        if sent and sent.get('kaynak') != 'yok':
            sent_skor = int(sent.get('skor', 0))
            efektif   = r['Skor'] + sent_skor
            sembol    = ETIKET_SEMBOL.get(sent.get('etiket', 'NOTR'), '⚪')

            r['Sentiment']    = sent
            r['EfektiveSkor'] = efektif
            r['Nedenler']    += f" | {sembol} Haber: {sent.get('ozet', '')}"
        else:
            r['Sentiment']    = None
            r['EfektiveSkor'] = r['Skor']

        enriched.append(r)

    # Efektif skora göre yeniden sırala
    enriched.sort(key=lambda x: (-x['EfektiveSkor'], x['RSI']))
    return enriched

