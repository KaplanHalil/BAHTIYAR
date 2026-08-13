import yfinance as yf
import pandas as pd
import logging

from stock_list_manager import get_stock_list

# Genel piyasa rejimi için BIST 100 endeksi
MARKET_INDEX = 'XU100.IS'

logging.disable(logging.CRITICAL)

# Hisse listesi — hisse_listesi.json dosyasından yüklenir (internetten değil)
BIST_STOCKS = get_stock_list()


def fetch_data(stock_list=None, period="1y"):
    """
    Arındırmasız helal hisseleri ve BIST endeks verilerini çeker.

    Args:
        stock_list: Çekilecek hisse listesi (None ise BIST_STOCKS/helal listesi kullanılır)
        period: Veri dönemi (\"1y\", \"1mo\", etc)

    Returns:
        dict: {ticker: dataframe} formatında veri
    """
    if stock_list is None:
        stock_list = BIST_STOCKS

    result = {}

    # ========== HISSE VERİLERİ ==========
    if stock_list:
        try:
            data = yf.download(
                tickers=stock_list,
                period=period,
                group_by="ticker",
                auto_adjust=False,
                threads=True,
                progress=False
            )

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

    # ========== BIST ENDEKS VERİSİ ==========
    try:
        index_data = yf.download(
            tickers=MARKET_INDEX,
            period=period,
            auto_adjust=False,
            progress=False
        )
        if not index_data.empty:
            result[MARKET_INDEX] = index_data.dropna(how="all")
    except Exception as e:
        print(f"BIST endeks veri çekme hatası: {e}")

    return result


