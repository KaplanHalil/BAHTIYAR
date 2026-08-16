import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, SMAIndicator, EMAIndicator, ADXIndicator
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
MIN_STOCK_HISTORY_DAYS = 50
MIN_AVG_TURNOVER_TL = 3_000_000
MIN_BUY_SCORE = 6
MARKET_INDEX = 'XU100.IS'
MARKET_REGIME_SMA_DAYS = 200


def calculate_market_health(data_dict: dict) -> dict:
    """
    BIST genel piyasa sağlığı ve rejimini hesaplar (0 - 100 Puan).
    
    Eksenler:
      1. BIST100 Trend Gücü (Maks 40 Puan):
         - Fiyat >= SMA20: +10 puan
         - Fiyat >= SMA50: +15 puan
         - Fiyat >= SMA200: +15 puan
         - SMA50 eğimi pozitif: +5 bonus (Maks 40 ile sınırlanır)
      2. BIST100 Momentum & Osilatör (Maks 30 Puan):
         - RSI(14) >= 55: +15 puan (45-55 arası: +8 puan)
         - MACD diff > 0 (Histogram pozitif): +15 puan
      3. Piyasa Genişliği / Market Breadth (Maks 30 Puan):
         - Takip listesindeki hisselerin % kaçı kendi SMA20 ve SMA50 üzerinde?
         - Hisselerin %60+'ı SMA20/50 üzerindeyse: +30 puan (%40-60 arası: +16 puan)

    Toplam Skor (0 - 100):
      - 70 - 100 : 'BULL' (Güçlü Boğa Piyasası)
                   -> %0 Nakit Savunması, %100 Yatırım
                   -> Min Alım Skoru: 6/15
                   -> Maks Hisse: 4
      - 40 - 69  : 'NEUTRAL' (Nötr / Dalgalı Piyasa)
                   -> %40 Nakit Kalkanı, %60 Yatırım
                   -> Min Alım Skoru: 9/15 (Yalnızca çok kaliteli fırsatlar)
                   -> Maks Hisse: 2
      - 0 - 39   : 'BEAR' (Düşüş / Ayı Piyasası)
                   -> %100 NAKİTTE BEKLEME (Cash Defense)
                   -> Min Alım Skoru: 999 (Yeni hisse alımı tamamen yasak)
                   -> Maks Hisse: 0
    """
    bist_df = data_dict.get(MARKET_INDEX)
    trend_score = 0
    momentum_score = 0
    breadth_score = 0
    details = []

    # 1. BIST 100 Endeks Analizi (Trend: 40 Puan, Momentum: 30 Puan)
    has_bist = False
    index_price = 0.0
    sma20_val = 0.0
    sma50_val = 0.0
    sma200_val = 0.0
    rsi_val = 50.0

    if bist_df is not None and not bist_df.empty:
        try:
            close_s = bist_df['Close'].squeeze()
            if isinstance(close_s, pd.DataFrame):
                close_s = close_s.iloc[:, 0]
            close_s = close_s.dropna()

            if len(close_s) >= 20:
                has_bist = True
                index_price = float(close_s.iloc[-1])

                # SMA20
                sma20 = SMAIndicator(close=close_s, window=20).sma_indicator()
                sma20_val = float(sma20.iloc[-1])
                if index_price >= sma20_val:
                    trend_score += 10
                    details.append("Endeks > SMA20 (Kısa Vade Pozitif)")

                # SMA50 & SMA50 eğimi
                if len(close_s) >= 50:
                    sma50 = SMAIndicator(close=close_s, window=50).sma_indicator()
                    sma50_val = float(sma50.iloc[-1])
                    if index_price >= sma50_val:
                        trend_score += 15
                        details.append("Endeks > SMA50 (Orta Vade Pozitif)")
                    if len(sma50) >= 5 and sma50.iloc[-1] > sma50.iloc[-5]:
                        trend_score = min(40, trend_score + 5)
                        details.append("SMA50 Eğimi Yükseliyor ↑")

                # SMA200
                if len(close_s) >= 200:
                    sma200 = SMAIndicator(close=close_s, window=200).sma_indicator()
                    sma200_val = float(sma200.iloc[-1])
                    if index_price >= sma200_val:
                        trend_score += 15
                        details.append("Endeks > SMA200 (Uzun Vade Boğa Hattı)")
                else:
                    if trend_score >= 20:
                        trend_score += 15

                trend_score = min(40, trend_score)

                # Momentum (RSI & MACD)
                if len(close_s) >= 14:
                    rsi_ind = RSIIndicator(close=close_s, window=14).rsi()
                    rsi_val = float(rsi_ind.iloc[-1])
                    if rsi_val >= 55:
                        momentum_score += 15
                        details.append(f"Endeks RSI Güçlü ({rsi_val:.1f})")
                    elif rsi_val >= 45:
                        momentum_score += 8
                        details.append(f"Endeks RSI Nötr ({rsi_val:.1f})")
                    else:
                        details.append(f"Endeks RSI Zayıf ({rsi_val:.1f}) ⚠️")

                if len(close_s) >= 26:
                    macd_ind = MACD(close=close_s)
                    macd_diff = float(macd_ind.macd_diff().iloc[-1])
                    if macd_diff > 0:
                        momentum_score += 15
                        details.append("Endeks MACD Pozitif (Yükseliş İvmesi)")
                    else:
                        details.append("Endeks MACD Negatif (Satış Baskısı)")
        except Exception:
            has_bist = False

    # 2. Piyasa Genişliği / Market Breadth (Maks 30 Puan)
    stocks_total = 0
    stocks_above_sma20 = 0
    stocks_above_sma50 = 0

    for ticker, df in data_dict.items():
        if ticker == MARKET_INDEX or not ticker.endswith('.IS'):
            continue
        try:
            c_s = df['Close'].squeeze()
            if isinstance(c_s, pd.DataFrame):
                c_s = c_s.iloc[:, 0]
            c_s = c_s.dropna()
            if len(c_s) < 20:
                continue
            stocks_total += 1
            last_p = float(c_s.iloc[-1])

            s20 = float(c_s.rolling(window=20).mean().iloc[-1])
            if last_p >= s20:
                stocks_above_sma20 += 1

            if len(c_s) >= 50:
                s50 = float(c_s.rolling(window=50).mean().iloc[-1])
                if last_p >= s50:
                    stocks_above_sma50 += 1
            else:
                if last_p >= s20:
                    stocks_above_sma50 += 1
        except Exception:
            continue

    if stocks_total > 0:
        pct_above_20 = (stocks_above_sma20 / stocks_total) * 100
        pct_above_50 = (stocks_above_sma50 / stocks_total) * 100

        if pct_above_20 >= 60:
            breadth_score += 15
            details.append(f"Hisselerin %{pct_above_20:.0f}'i SMA20 Üzerinde (Geniş Tabanlı Yükseliş)")
        elif pct_above_20 >= 40:
            breadth_score += 8
            details.append(f"Hisselerin %{pct_above_20:.0f}'i SMA20 Üzerinde (Kararsız Piyasa)")
        else:
            details.append(f"Hisselerin yalnızca %{pct_above_20:.0f}'i SMA20 Üzerinde (Zayıf Genişlik)")

        if pct_above_50 >= 60:
            breadth_score += 15
            details.append(f"Hisselerin %{pct_above_50:.0f}'i SMA50 Üzerinde")
        elif pct_above_50 >= 40:
            breadth_score += 8
    else:
        pct_above_20 = 50.0
        pct_above_50 = 50.0
        breadth_score = 15

    if not has_bist:
        total_score = min(100, int((breadth_score / 30.0) * 100))
    else:
        total_score = min(100, trend_score + momentum_score + breadth_score)

    if total_score >= 60:
        regime = 'BULL'
        regime_title = "GÜÇLÜ BOĞA PİYASASI"
        regime_emoji = "🟢"
        cash_target_pct = 0.00         # %0 Nakit, %100 Yatırım
        min_buy_score = 6              # Standart alım eşiği
        max_recommended_stocks = 5     # 5 hisseye kadar sepet
        allow_new_buys = True
        summary_msg = "Piyasa güçlü yükseliş trendinde. Tam güç hisse alımı ve büyüme tavsiye ediliyor."
    elif total_score >= 25:
        regime = 'NEUTRAL'
        regime_title = "NÖTR / DENGELİ PİYASA"
        regime_emoji = "🟡"
        cash_target_pct = 0.00         # Fırsat odaklı tam yatırım
        min_buy_score = 6              # Kaliteli hisseler alınır
        max_recommended_stocks = 5     # 5 hisseye kadar sepet
        allow_new_buys = True
        summary_msg = "Piyasa dengeli ve dalgalı. Trendi güçlü ve endeks üstü getiri vadeden hisseler seçiliyor."
    else:
        regime = 'BEAR'
        regime_title = "AYI / SERT DÜŞÜŞ PİYASASI"
        regime_emoji = "🔴"
        cash_target_pct = 1.00         # %100 NAKİTTE BEKLE
        min_buy_score = 999            # Alım YASAK
        max_recommended_stocks = 0     # 0 hisse
        allow_new_buys = False
        summary_msg = "Piyasa genel çöküş / sert düşüş trendinde. Sermayeyi korumak amacıyla %100 NAKİTTE KALINMASI öneriliyor."

    return {
        'available': True,
        'health_score': total_score,
        'regime': regime,
        'regime_title': regime_title,
        'regime_emoji': regime_emoji,
        'cash_target_pct': cash_target_pct,
        'min_buy_score': min_buy_score,
        'max_recommended_stocks': max_recommended_stocks,
        'allow_new_buys': allow_new_buys,
        'allow_stocks': allow_new_buys,  # Geriye dönük uyumluluk
        'trend_score': trend_score,
        'momentum_score': momentum_score,
        'breadth_score': breadth_score,
        'stocks_total': stocks_total,
        'pct_above_sma20': round(pct_above_20, 1),
        'pct_above_sma50': round(pct_above_50, 1),
        'index_price': index_price,
        'index_rsi': round(rsi_val, 1),
        'summary_msg': summary_msg,
        'details': details,
        'reason': summary_msg
    }


def get_market_regime(data_dict):
    """Geriye dönük uyumluluk wrapper'ı."""
    return calculate_market_health(data_dict)


def analyze_stocks(data_dict, market_health=None):
    """
    BIST hisselerini piyasa sağlık endeksi, gelişmiş teknik analiz,
    risk yönetimi (ATR) ve adaptif puanlama motoru ile değerlendirir (Maks: 15 puan).
    """
    if market_health is None:
        market_health = calculate_market_health(data_dict)

    if not market_health['allow_new_buys']:
        return []

    min_required_score = market_health.get('min_buy_score', MIN_BUY_SCORE)

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

            # 3. SMA 50 & 200 & EMA 9/21
            sma50 = SMAIndicator(close=close_prices, window=50).sma_indicator()
            last_sma50 = float(sma50.iloc[-1])

            sma20 = SMAIndicator(close=close_prices, window=20).sma_indicator()
            last_sma20 = float(sma20.iloc[-1])

            ema9 = EMAIndicator(close=close_prices, window=9).ema_indicator()
            last_ema9 = float(ema9.iloc[-1])

            ema21 = EMAIndicator(close=close_prices, window=21).ema_indicator()
            last_ema21 = float(ema21.iloc[-1])

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
                stop_loss = round(max(last_price - 1.8 * last_atr, last_price * 0.88), 2)
                target_price = round(last_price + 3.5 * last_atr, 2)
                risk = last_price - stop_loss
                reward = target_price - last_price
                risk_reward = round(reward / risk, 2) if risk > 0 else 2.0
            else:
                stop_loss = round(last_price * 0.90, 2)
                target_price = round(last_price + (last_price * 0.20), 2)
                risk_reward = 2.0

            # 9. Hacim ve Likidite Analizi
            volume_confirmed = False
            avg_turnover = 0.0
            if volume is not None and len(volume) >= 20:
                avg_volume = float(volume.iloc[-20:].mean())
                last_volume = float(volume.iloc[-1])
                volume_confirmed = last_volume > avg_volume * 1.15
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

            # Ana Trend Şartı: Orta vadeli yükseliş trendi (Fiyat >= SMA50)
            trend_ok = (last_price >= last_sma50)

            falling_knife = price_change_20d < -15 and last_macd_diff <= 0
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
            rel_strength_ok = (stock_ret_20d > bist_ret_20d)

            # ---- AĞIRLIKLI PUANLAMA MOTORU (Maks: 15 Puan) ----
            score = 0
            reasons = []

            # Kriter 1: RSI Puanı (İdeal Momentum Bölgesi 45 - 72)
            if 45 <= last_rsi <= 72:
                score += 2
                reasons.append(f"RSI İdeal Bölgede ({last_rsi:.0f})")
            elif 35 <= last_rsi < 45 or 72 < last_rsi <= 78:
                score += 1
                reasons.append(f"RSI Kabul Edilebilir ({last_rsi:.0f})")

            # Kriter 2: MACD İvmesi
            if last_macd_diff > 0:
                score += 2
                reasons.append("MACD Pozitif / Al Sinyali")
                if last_macd_diff > prev_macd_diff:
                    score += 1
                    reasons.append("MACD İvmesi Artıyor ↑")

            # Kriter 3: Hareketli Ortalama Trendi (SMA20, SMA50, SMA200)
            if last_price >= last_sma20:
                score += 1
                reasons.append("Fiyat > SMA20")
            if last_price >= last_sma50:
                score += 2
                reasons.append("Fiyat > SMA50 (Ana Yükseliş Trendi)")
            if last_sma20 >= last_sma50:
                score += 1
                reasons.append("SMA20 >= SMA50")

            # Kriter 4: Kısa Vadeli EMA9 >= EMA21 İvmesi
            if last_ema9 >= last_ema21:
                score += 1
                reasons.append("EMA9 >= EMA21 (Kısa Vade İvme)")

            if has_sma200 and last_sma200 is not None:
                if last_sma50 > last_sma200:
                    score += 1
                    reasons.append("Golden Cross Aktif")
                if sma50_slope > 0:
                    score += 1
                    reasons.append("SMA50 Yükseliyor ↑")

            # Kriter 5: ADX Güçlü Trend
            if adx_val >= 25:
                score += 1
                reasons.append(f"Güçlü Trend (ADX={adx_val:.0f})")

            # Kriter 6: Hacim Doğrulaması
            if volume_confirmed:
                score += 1
                reasons.append("Hacim Doğrulaması ✓")

            # Kriter 7: Para Akışı (MFI)
            if 30 <= last_mfi <= 75:
                score += 1
                reasons.append("Para Girişi Dengeli (MFI)")

            # Kriter 8: Göreceli Güç (Alpha vs BIST)
            if rel_strength_ok:
                score += 2
                reasons.append("Endeks Üstü Getiri Potansiyeli (Alpha)")

            # Kriter 9: Pozitif RSI Uyumsuzluğu
            if bullish_divergence:
                score += 2
                reasons.append("Pozitif RSI Uyumsuzluğu ↑")

            # Skoru sınırla
            score = max(score, 0)

            # Filtrele ve sonuçlara ekle (Piyasa rejimine göre dinamik eşik: min_required_score)
            if score >= min_required_score and trend_ok:
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


def evaluate_portfolio(portfolio, data_dict, market_health=None):
    """
    Portföydeki hisseleri piyasa rejimi, teknik analiz, trailing stop ve
    maliyet risk eşikleri ile değerlendirir. Sat/Tut/Güçlü Tut kararı verir.
    """
    if market_health is None:
        market_health = calculate_market_health(data_dict)

    is_bear_market = (market_health.get('regime') == 'BEAR')
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

            # ---- KÂRI SÜREN VE TRENDİ KORUYAN SATIŞ PUANLAMA MOTORU ----
            # Kural: Yükselen trenddeki hisseler (kâr eden veya aşırı alıma girenler) erken satılmaz!
            # Satış yalnızca hissenin trendi gerçekten kırıldığında veya stop seviyesine indiğinde tetiklenir.
            sat_puani = 0
            reasons = []

            # 1. Trend Kırılımı (Fiyat < SMA50)
            if last_price < last_sma50:
                sat_puani += 2
                reasons.append("Fiyat < SMA50 (Trend Bozuldu)")

            # 2. Death Cross veya SMA200 Altına Kırılım
            if has_sma200 and last_sma200 is not None:
                if last_sma50 < last_sma200:
                    sat_puani += 2
                    reasons.append("Death Cross Aktif ✗")
                if last_price < last_sma200:
                    sat_puani += 2
                    reasons.append("Fiyat < SMA200")

            # 3. RSI Çöküşü / Momentum Kaybı (RSI < 35)
            if last_rsi < 35:
                sat_puani += 1
                reasons.append(f"RSI Çöküşü ({last_rsi:.1f})")

            # 4. MACD Negatif ve Fiyat SMA50 Altında
            if last_macd_diff < 0 and last_price < last_sma50:
                sat_puani += 1
                reasons.append("MACD Negatif & SMA50 Altı")

            # 5. Yüksek Hacimli Sert Düşüş
            if volume_spike_down:
                sat_puani += 2
                reasons.append("Yüksek Hacimli Düşüş ↓")

            # 6. Negatif RSI Uyumsuzluğu
            if bearish_divergence:
                sat_puani += 2
                reasons.append("Negatif RSI Uyumsuzluğu ⚠️")

            # 7. Stop-Loss Disiplini (Maliyet Risk Kalkanı)
            if k_z <= -10.0:
                sat_puani += 3
                reasons.append(f"Stop-Loss Eşiği (%{k_z:.1f}) 🛑")

            # ---- KARAR MATRİSİ ----
            if sat_puani >= 3:
                action = "Sat"
            elif sat_puani >= 2:
                action = "Dikkatli Tut"
            else:
                action = "Güçlü Tut"
                if not reasons:
                    reasons.append("Trend Güçlü / Kâr Sürdürülüyor ✓")

            # ATR İz Süren Stop Seviyesi (Kârı koruma eşiği)
            trailing_stop = round(last_price - 1.8 * last_atr, 2) if last_atr > 0 else round(last_price * 0.90, 2)

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

