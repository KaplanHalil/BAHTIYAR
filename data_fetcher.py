import yfinance as yf
import pandas as pd
import sys
import os
import logging
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

logging.disable(logging.CRITICAL)

def fetch_data(stock_list=None, period="1y"):
    if stock_list is None:
        stock_list = BIST_STOCKS

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

        result = {}

        # Her hisseyi ayrı dataframe olarak ayır
        for ticker in stock_list:
            try:
                if ticker in data.columns.levels[0]:
                    df = data[ticker].dropna(how="all")

                    if not df.empty:
                        result[ticker] = df

            except Exception:
                pass

        return result

    except Exception as e:
        print(f"Hata: {e}")
        return {}
