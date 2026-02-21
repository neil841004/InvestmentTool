import yfinance as yf

def test_data():
    print("Testing yfinance...")
    tickers = ["2330.TW", "AAPL", "BTC-USD"]
    try:
        data = yf.download(tickers, period="1d", progress=False)
        if not data.empty:
            print("Data retrieval SUCCESS")
            print(data.head())
        else:
            print("Data retrieval FAILED: Empty dataframe")
    except Exception as e:
        print(f"Data retrieval ERROR: {e}")

if __name__ == "__main__":
    test_data()
