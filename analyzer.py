import pandas as pd
import numpy as np
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import MACD, SMAIndicator
from ta.volatility import BollingerBands

# ============================================================================
#  GELİŞMİŞ TEKNİK ANALİZ MOTORU
#  Kullanılan Göstergeler:
#    1. RSI (14) - Momentum / Aşırı alım-satım
#    2. MACD (12,26,9) - Trend yönü ve ivme
#    3. SMA 50 & SMA 200 - Trend takibi, Golden/Death Cross
#    4. Bollinger Bantları (20,2) - Volatilite ve fiyat kanalı
#    5. Stochastic Oscillator (14,3) - Momentum doğrulama
#    6. Hacim Analizi - İşlem hacmi ile sinyal doğrulama
# ============================================================================

MAX_SKOR = 10  # Ağırlıklı puanlama sistemindeki maksimum puan
MIN_STOCK_HISTORY_DAYS = 200
MIN_AVG_TURNOVER_TL = 3_000_000
MIN_BUY_SCORE = 5
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
    BIST hisselerini gelişmiş teknik analiz ile değerlendirir.
    Ağırlıklı puanlama sistemi kullanır (Maks: 10 puan).
    """
    recommendations = []
    
    for ticker, df in data_dict.items():
        # analyze_all_assets() aynı sözlüğe metalleri de koyuyor.
        # Hisse motoru sadece BIST sembollerini değerlendirmeli.
        if ticker == MARKET_INDEX or not ticker.endswith('.IS'):
            continue

        if len(df) < MIN_STOCK_HISTORY_DAYS:
            continue

        try:
            close_prices = df['Close'].squeeze()
            if isinstance(close_prices, pd.DataFrame):
                close_prices = close_prices.iloc[:, 0]
            
            # Hacim verisini al
            volume = df['Volume'].squeeze() if 'Volume' in df.columns else None
            if isinstance(volume, pd.DataFrame):
                volume = volume.iloc[:, 0]

            close_prices = close_prices.dropna()
            if len(close_prices) < MIN_STOCK_HISTORY_DAYS:
                continue

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
                high=df['High'].squeeze() if isinstance(df['High'].squeeze(), pd.Series) else df['High'].squeeze(),
                low=df['Low'].squeeze() if isinstance(df['Low'].squeeze(), pd.Series) else df['Low'].squeeze(),
                close=close_prices,
                window=14, smooth_window=3
            )
            last_stoch_k = float(stoch.stoch().iloc[-1])
            
            # 6. Hacim ve likidite analizi
            volume_confirmed = False
            avg_turnover = 0.0
            if volume is not None and len(volume) >= 20:
                avg_volume = float(volume.iloc[-20:].mean())
                last_volume = float(volume.iloc[-1])
                volume_confirmed = last_volume > avg_volume * 1.2
                avg_turnover = avg_volume * float(close_prices.iloc[-1])

            last_price = float(close_prices.iloc[-1])
            price_change_20d = 0.0
            if len(close_prices) >= 20:
                price_20d_ago = float(close_prices.iloc[-20])
                price_change_20d = ((last_price - price_20d_ago) / price_20d_ago) * 100 if price_20d_ago > 0 else 0

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

            # ---- AĞIRLIKLI PUANLAMA SİSTEMİ ----
            score = 0
            reasons = []
            
            # Kriter 1: RSI Analizi. Düşük RSI tek başına alım sebebi değil; trend şartı aranır.
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
                score += 2  # Taze pozitif kesişim (Crossover) - çok güçlü sinyal
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
                    
            # Kriter 5: Bollinger Bantları. Alt bant sadece trend bozulmamışsa olumlu sayılır.
            if trend_ok and last_price <= bb_lower * 1.02:
                score += 1
                reasons.append("Trend İçinde Bollinger Alt Bandı")
            if bb_width < 0.05 and last_price > last_sma50:
                score += 1
                reasons.append("Bollinger Sıkışma")
                
            # Kriter 6: Stochastic Oscillator (+1 puan)
            if last_stoch_k < 20:
                score += 1
                reasons.append(f"Stochastic Aşırı Satım ({last_stoch_k:.0f})")
            elif last_stoch_k > 80:
                score -= 1
                
            # Kriter 7: Hacim Doğrulaması (+1 puan bonus)
            if volume_confirmed and score >= 3:
                score += 1
                reasons.append("Hacim Doğrulaması ✓")
                
            # Skoru 0'ın altına düşürme
            score = max(score, 0)
            
            # Skor yüksek olsa bile ana trend filtresi sağlanmadan alım yapılmaz.
            if score >= MIN_BUY_SCORE and trend_ok:
                sinyal_gucu = "Güçlü" if score >= 7 else ("Orta" if score >= 5 else "Zayıf")
                recommendations.append({
                    'Hisse': ticker.replace('.IS', ''),
                    'Fiyat': last_price,
                    'RSI': last_rsi,
                    'Skor': score,
                    'Sinyal': sinyal_gucu,
                    'Nedenler': ", ".join(reasons)
                })
                
        except Exception:
            continue
            
    # En yüksek skora, ardından en düşük RSI'a göre sırala
    recommendations.sort(key=lambda x: (-x['Skor'], x['RSI']))
    return recommendations


def evaluate_portfolio(portfolio, data_dict):
    """
    Portföydeki hisseleri gelişmiş teknik analiz ile değerlendirir.
    Sat/Tut/Güçlü Tut kararı verir.
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
                
            volume = df['Volume'].squeeze() if 'Volume' in df.columns else None
            if isinstance(volume, pd.DataFrame):
                volume = volume.iloc[:, 0]
                
            # Gösterge hesaplamaları
            rsi = RSIIndicator(close=close_prices, window=14).rsi()
            macd_indicator = MACD(close=close_prices)
            macd_diff = macd_indicator.macd_diff()
            sma50 = SMAIndicator(close=close_prices, window=50).sma_indicator()
            
            bb = BollingerBands(close=close_prices, window=20, window_dev=2)
            bb_upper = float(bb.bollinger_hband().iloc[-1])
            
            stoch = StochasticOscillator(
                high=df['High'].squeeze() if isinstance(df['High'].squeeze(), pd.Series) else df['High'].squeeze(),
                low=df['Low'].squeeze() if isinstance(df['Low'].squeeze(), pd.Series) else df['Low'].squeeze(),
                close=close_prices,
                window=14, smooth_window=3
            )
            last_stoch_k = float(stoch.stoch().iloc[-1])
            
            last_price = float(close_prices.iloc[-1])
            last_rsi = float(rsi.iloc[-1])
            last_macd_diff = float(macd_diff.iloc[-1])
            last_sma50 = float(sma50.iloc[-1])
            
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
                # Hacim yüksek + fiyat düşüyorsa tehlike
                if last_volume > avg_volume * 1.5:
                    price_change = (last_price - float(close_prices.iloc[-2])) / float(close_prices.iloc[-2])
                    if price_change < -0.02:
                        volume_spike_down = True
            
            # ---- SATIŞ PUANLAMA SİSTEMİ ----
            sat_puani = 0
            action = "Tut"
            reasons = []
            
            # RSI Aşırı Alım
            if last_rsi > 80:
                sat_puani += 3
                reasons.append(f"RSI Aşırı Alım ({last_rsi:.1f}) ⚠")
            elif last_rsi > 70:
                sat_puani += 2
                reasons.append(f"RSI Yüksek ({last_rsi:.1f})")
                
            # MACD Negatif
            if last_macd_diff < 0:
                sat_puani += 1
                reasons.append("MACD Negatif")
                
            # Fiyat SMA50 altında
            if last_price < last_sma50:
                sat_puani += 1
                reasons.append("Fiyat < SMA50")
                
            # Death Cross
            if has_sma200 and last_sma200 is not None and last_sma50 < last_sma200:
                sat_puani += 2
                reasons.append("Death Cross Aktif ✗")
                
            # Fiyat SMA200 altında (güçlü düşüş trendi)
            if has_sma200 and last_sma200 is not None and last_price < last_sma200:
                sat_puani += 2
                reasons.append("Fiyat < SMA200")
                
            # Bollinger üst bandına temas
            if last_price >= bb_upper * 0.98:
                sat_puani += 1
                reasons.append("Bollinger Üst Bandı")
                
            # Stochastic aşırı alım
            if last_stoch_k > 80:
                sat_puani += 1
                reasons.append(f"Stochastic Yüksek ({last_stoch_k:.0f})")
                
            # Hacim patlamasıyla birlikte düşüş
            if volume_spike_down:
                sat_puani += 2
                reasons.append("Yüksek Hacimli Düşüş ↓")
            
            # ---- KARAR MATRİSİ ----
            if sat_puani >= 5:
                action = "Sat"
            elif sat_puani >= 3:
                action = "Dikkatli Tut"
            else:
                action = "Güçlü Tut"
                if not reasons:
                    reasons.append("Trend Olumlu ✓")
                    
            # Kar/Zarar hesaplaması
            maliyet = info.get('maliyet', last_price)
            k_z = 0
            if maliyet > 0:
                k_z = ((last_price - maliyet) / maliyet) * 100
                
            evaluations.append({
                'Hisse': ticker,
                'Durum': action,
                'Fiyat': last_price,
                'Maliyet': maliyet,
                'K/Z %': k_z,
                'Lot': info['lot'],
                'Sat Puanı': sat_puani,
                'Nedenler': ", ".join(reasons)
            })
            
        except Exception:
            continue
        
    return evaluations


# ============================================================================
#  DEĞERLI METALLER (ALTIN / GÜMÜŞ) ANALİZ MOTORU
#  Kuveyt Türk fiyatları üzerinden tavsiye
# ============================================================================

def analyze_precious_metals(data_dict):
    """
    Altın (GC=F) ve Gümüş (SI=F) futures'ı analiz eder.
    Hisse analizi ile benzer ağırlıklı puanlama sistemi kullanır.
    
    NOT: GC=F ve SI=F USD bazında değerli metal futures'larıdır.
    Kuveyt Türk'ün TL bazındaki fiyatları almak için dönüşüm yapılabilir.
    """
    recommendations = []
    
    metal_map = {
        'GC=F': {'name': 'ALTIN', 'unit': 'gram', 'display': '🥇 Altın'},
        'SI=F': {'name': 'GUMUS', 'unit': 'gram', 'display': '🥈 Gümüş'}
    }
    
    for ticker, df in data_dict.items():
        if ticker not in metal_map:
            continue
            
        if len(df) < 30:  # Değerli metaller için 30 günlük veri yeterli
            continue
            
        try:
            close_prices = df['Close'].squeeze()
            if isinstance(close_prices, pd.DataFrame):
                close_prices = close_prices.iloc[:, 0]
            
            volume = df['Volume'].squeeze() if 'Volume' in df.columns else None
            if isinstance(volume, pd.DataFrame):
                volume = volume.iloc[:, 0]
                
            last_price = float(close_prices.iloc[-1])
            
            # ---- GÖSTERGE HESAPLAMALARI ----
            
            # 1. RSI (14 Günlük)
            rsi = RSIIndicator(close=close_prices, window=14).rsi()
            last_rsi = float(rsi.iloc[-1])
            
            # 2. SMA 20 & 50 (Kısa vadeli trend)
            sma20 = SMAIndicator(close=close_prices, window=20).sma_indicator()
            last_sma20 = float(sma20.iloc[-1])
            last_sma50 = None
            
            if len(close_prices) >= 50:
                sma50 = SMAIndicator(close=close_prices, window=50).sma_indicator()
                last_sma50 = float(sma50.iloc[-1])
            
            # 3. Volatilite (Günlük getiri standart sapması)
            # Günlük log-getiri std kullan: trendü olan metaller için coefficient of variation
            # çok yüksek çıkar ve yanlış ceza keser.
            daily_returns = close_prices.pct_change().dropna()
            volatility = float(daily_returns.std() * 100) if len(daily_returns) > 5 else 0
            
            # 4. Fiyat Hareketleri
            price_change_5d = ((last_price - float(close_prices.iloc[-5])) / float(close_prices.iloc[-5]) * 100) if len(close_prices) >= 5 else 0
            price_change_20d = ((last_price - float(close_prices.iloc[-20])) / float(close_prices.iloc[-20]) * 100) if len(close_prices) >= 20 else 0
            
            # 5. MACD (Trend yönü)
            macd_indicator = MACD(close=close_prices, window_slow=26, window_fast=12, window_sign=9)
            macd_diff = macd_indicator.macd_diff()
            last_macd_diff = float(macd_diff.iloc[-1]) if len(macd_diff) > 0 and not pd.isna(macd_diff.iloc[-1]) else 0
            
            # ---- AĞIRLIKLI PUANLAMA SİSTEMİ (Değerli Metaller) ----
            # İki strateji desteklenir:
            #   A) Dip alma: Düşük RSI + fiyat geri çekildi
            #   B) Trend takip: Yükselen trend, güçlü momentum
            score = 0
            reasons = []
            
            # Kriter 1: RSI Analizi (Maks +2 puan)
            if last_rsi < 30:
                score += 2
                reasons.append(f"RSI Aşırı Satım ({last_rsi:.1f})")
            elif last_rsi < 40:
                score += 1
                reasons.append(f"RSI Düşük ({last_rsi:.1f})")
            elif 40 <= last_rsi <= 60:
                # Orta bölge — nötr ama henyz aşırı alım değil
                score += 1
                reasons.append(f"RSI Ntr Bölge ({last_rsi:.1f})")
            elif 60 < last_rsi <= 75:
                # Sağlıklı güçlü trend bölgesi
                score += 1
                reasons.append(f"RSI Trend Güçlü ({last_rsi:.1f})")
            # RSI > 75: nötr (aşırı alım riskte)

            # Kriter 2: 5 Günlük Fiyat Hareketi
            if price_change_5d < -5:
                score += 2  # Sert düşüş = dip alma fırsatı
                reasons.append(f"Kısa Vadeli Düşüş ({price_change_5d:.1f}%)")
            elif price_change_5d < 0:
                score += 1  # Hafif geri çekilme
                reasons.append(f"Hafif Düşüş ({price_change_5d:.1f}%)")
            elif 0 < price_change_5d < 3:
                score += 1  # Istikrarlı yükseliş
                reasons.append(f"Istikrarlı Artış ({price_change_5d:.1f}%)")
                
            # Kriter 3: 20 Günlük Orta Vadeli Trend
            if price_change_20d > 3:
                score += 2
                reasons.append(f"Güçlü 20g Trend ({price_change_20d:.1f}%)")
            elif price_change_20d > 0:
                score += 1
                reasons.append(f"Pozitif 20g Trend ({price_change_20d:.1f}%)")
                
            # Kriter 4: Fiyat SMA20 Üzerinde (+1 puan)
            if last_price > last_sma20:
                score += 1
                reasons.append("Fiyat > SMA20")
                
            # Kriter 5: Fiyat SMA50 Üzerinde (+1 puan)
            if last_sma50 is not None and last_price > last_sma50:
                score += 1
                reasons.append("Fiyat > SMA50")
                
            # Kriter 6: MACD Pozitif (+1 puan)
            if last_macd_diff > 0:
                score += 1
                reasons.append("MACD Pozitif")
                
            # Kriter 7: Volatilite — günlük getiri std bazlı ceza (>2.5% = yüksek)
            if volatility > 2.5:
                score -= 1
                reasons.append(f"Yüksek Volatilite ({volatility:.1f}%)")
            
            score = max(score, 0)
            
            # Metal için eşik daha düşük: 2 puan yeterli
            # (Metaller az sayıda gösterge kriterini keser, hisse kadar değil)
            if score >= 2:
                sinyal_gucu = "Güçlü" if score >= 6 else ("Orta" if score >= 4 else "Zayıf")
                
                metal_info = metal_map[ticker]
                recommendations.append({
                    'Hisse': metal_info['name'],
                    'Fiyat': last_price,
                    'RSI': last_rsi,
                    'Skor': score,
                    'Sinyal': sinyal_gucu,
                    'Nedenler': ", ".join(reasons),
                    'AssetType': 'METAL',
                    'Display': metal_info['display'],
                    'Unit': metal_info['unit'],
                    'Volatility': volatility
                })
                
        except Exception as e:
            continue
            
    # En yüksek skora göre sırala
    recommendations.sort(key=lambda x: (-x['Skor'], x['RSI']))
    return recommendations


def analyze_all_assets(data_dict):
    """
    Hem hisseler hem de değerli metaller (altın/gümüş) için
    birleştirilmiş analiz yapır ve kombinli tavsiyeler döndürür.
    """
    market_regime = get_market_regime(data_dict)

    # Hisse analizi
    stock_recs = analyze_stocks(data_dict) if market_regime['allow_stocks'] else []

    # Değerli metal analizi
    metal_recs = analyze_precious_metals(data_dict)
    
    # Hisselere AssetType ekle
    for rec in stock_recs:
        rec['AssetType'] = 'HISSE'
        rec['Display'] = f"📊 {rec['Hisse']}"
        rec['Unit'] = 'adet'
    
    # Birleştir ve sırala
    all_recommendations = stock_recs + metal_recs
    all_recommendations.sort(key=lambda x: (-x['Skor'], x['RSI']))
    
    return all_recommendations
