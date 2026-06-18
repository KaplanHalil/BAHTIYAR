import yfinance as yf
import pandas as pd
import sys
import os
import logging

# Precious metals fetcher - optional import
try:
    from precious_metals_fetcher import fetch_precious_metals
    METALS_AVAILABLE = True
except ImportError:
    METALS_AVAILABLE = False

# BIST 100 Hisseleri (Güncel Yaklaşım)
BIST_STOCKS = [
    "AEFES.IS", "AGHOL.IS", "AHGAZ.IS", "AKBNK.IS", "AKCNS.IS", "AKFGY.IS", "AKSA.IS", "AKSEN.IS", "ALARK.IS", "ALBRK.IS", 
    "ALFAS.IS", "ARCLK.IS", "ASELS.IS", "ASTOR.IS", "BERA.IS", "BIMAS.IS", "BIOEN.IS", "BOBET.IS", "BRSAN.IS", "BTCIM.IS", 
    "BUCIM.IS", "CANTE.IS", "CCOLA.IS", "CIMSA.IS", "CWENE.IS", "DOAS.IS", "DOHOL.IS", "ECILC.IS", "EGEEN.IS", "EKGYO.IS", 
    "ENJSA.IS", "ENKAI.IS", "EREGL.IS", "EUPWR.IS", "EUREN.IS", "FROTO.IS", "GARAN.IS", "GESAN.IS", "GLYHO.IS", "GUBRF.IS", 
    "GWIND.IS", "HALKB.IS", "HEKTS.IS", "IMASM.IS", "IPEKE.IS", "ISCTR.IS", "ISDMR.IS", "ISGYO.IS", "ISMEN.IS", "IZENM.IS", 
    "KALES.IS", "KARSN.IS", "KAYSE.IS", "KCAER.IS", "KCHOL.IS", "KLSER.IS", "KONTR.IS", "KONYA.IS", "KORDS.IS", "KOZAA.IS", 
    "KOZAL.IS", "KRDMD.IS", "MAVI.IS", "MGROS.IS", "MIATK.IS", "ODAS.IS", "OTKAR.IS", "OYAKC.IS", "PENTA.IS", "PETKM.IS", 
    "PGSUS.IS", "PNLSN.IS", "QUAGR.IS", "SAHOL.IS", "SASA.IS", "SDTTR.IS", "SISE.IS", "SKBNK.IS", "SMRTG.IS", "SOKM.IS", 
    "TABGD.IS", "TAVHL.IS", "TCELL.IS", "THYAO.IS", "TKFEN.IS", "TOASO.IS", "TSKB.IS", "TTKOM.IS", "TTRAK.IS", "TUKAS.IS", 
    "TUPRS.IS", "ULKER.IS", "VAKBN.IS", "VESBE.IS", "VESTL.IS", "YEOTK.IS", "YKBNK.IS", "YYLGD.IS", "ZOREN.IS", "KZBGY.IS"
]

# Değerli Metaller
PRECIOUS_METALS = ['GC=F', 'SI=F']  # Altın ve Gümüş Futures

logging.disable(logging.CRITICAL)

def fetch_data(stock_list=None, include_metals=True, period="1y"):
    """
    BIST hisseleri ve değerli metaller (altın/gümüş) verilerini çeker.
    
    Args:
        stock_list: Çekilecek hisse listesi (None ise BIST_STOCKS kullanılır)
        include_metals: Altın/gümüş verileri de çekil (True/False)
        period: Veri dönemi ("1y", "1mo", etc)
    
    Returns:
        dict: {ticker: dataframe} formatında veri
    """
    if stock_list is None:
        stock_list = BIST_STOCKS

    result = {}

    # ========== HISSE VERİLERİ ==========
    if stock_list:
        try:
            # Tüm hisseleri tek request ile çek
            data = yf.download(
                tickers=stock_list,
                period=period,
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False
            )

            # Her hisseyi ayrı dataframe olarak ayır
            for ticker in stock_list:
                try:
                    if ticker in data.columns.levels[0]:
                        df = data[ticker].dropna(how="all")

                        if not df.empty:
                            result[ticker] = df

                except Exception:
                    pass

        except Exception as e:
            print(f"Hisse veri çekme hatası: {e}")

    # ========== DEĞERLI METAL VERİLERİ ==========
    if include_metals:
        try:
            # Altın (GC=F) ve Gümüş (SI=F) futures verilerini çek
            metals_data = yf.download(
                tickers=PRECIOUS_METALS,
                period=period,
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False
            )

            # Altın
            try:
                if 'GC=F' in metals_data.columns.levels[0]:
                    df_gold = metals_data['GC=F'].dropna(how="all")
                    if not df_gold.empty:
                        result['GC=F'] = df_gold
            except Exception:
                pass

            # Gümüş
            try:
                if 'SI=F' in metals_data.columns.levels[0]:
                    df_silver = metals_data['SI=F'].dropna(how="all")
                    if not df_silver.empty:
                        result['SI=F'] = df_silver
            except Exception:
                pass

        except Exception as e:
            print(f"Değerli metal veri çekme hatası: {e}")

    return result
