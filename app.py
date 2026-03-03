import os
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, jsonify

app = Flask(__name__)
app.secret_key = "Anoop@12"

# ================= CONFIG =================

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

USERNAME = "Anoop"
PASSWORD = "Anoop@12"

STOCK_MAP = {
    "NSE_EQ|INE002A01018": "RELIANCE",
    "NSE_EQ|INE040A01034": "HDFCBANK",
    "NSE_EQ|INE467B01029": "TCS",
    "NSE_EQ|INE009A01021": "INFY",
}

NIFTY_KEY = "NSE_INDEX|Nifty 50"

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Accept": "application/json"
}

# ================= UTIL =================

def get_previous_day(date):
    day = date - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day

def market_open():
    now = datetime.now()
    if now.weekday() >= 5:
        return False
    if now.hour < 9 or (now.hour == 9 and now.minute < 16):
        return False
    if now.hour > 15 or (now.hour == 15 and now.minute > 30):
        return False
    return True

def fetch_915(stock, date):
    date_str = date.strftime("%Y-%m-%d")
    url = f"https://api.upstox.com/v2/historical-candle/{stock}/1minute/{date_str}/{date_str}"
    r = requests.get(url, headers=HEADERS, timeout=5)
    data = r.json()
    candles = data.get("data", {}).get("candles", [])

    for candle in candles:
        dt = datetime.fromisoformat(candle[0].replace("Z","+00:00"))
        if dt.hour == 9 and dt.minute == 15:
            return candle[1], candle[2], candle[3]
    return None, None, None

# ================= LOGIN =================

@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        if request.form["username"] == USERNAME and request.form["password"] == PASSWORD:
            session["user"] = USERNAME
            return redirect("/dashboard")
    return render_template("login.html")

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect("/")
    return render_template("dashboard.html", user=session["user"])

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

# ================= NIFTY STRIP =================

@app.route("/nifty")
def nifty():
    try:
        url = "https://api.upstox.com/v2/market-quote/ohlc"
        params = {"instrument_key": NIFTY_KEY, "interval": "1d"}
        r = requests.get(url, headers=HEADERS, params=params)
        data = r.json()

        key = list(data["data"].keys())[0]
        ltp = data["data"][key]["last_price"]
        prev_close = data["data"][key]["ohlc"]["close"]

        change = round(((ltp-prev_close)/prev_close)*100,2)

        return jsonify({"ltp": ltp, "change": change})
    except:
        return jsonify({"ltp": "-", "change": 0})

# ================= SCANNER =================

@app.route("/live-scanner")
def live_scanner():

    if "user" not in session:
        return jsonify({})

    now = datetime.now()
    prev = get_previous_day(now)
    is_open = market_open()

    date_used = now if is_open else prev

    results = []

    for stock, name in STOCK_MAP.items():

        try:
            o,h,l = fetch_915(stock, date_used)

            if o:
                if o == l:
                    results.append({"stock": name, "condition": "Open = Low"})
                elif o == h:
                    results.append({"stock": name, "condition": "Open = High"})

            if is_open:
                prev_date = prev.strftime("%Y-%m-%d")
                url = f"https://api.upstox.com/v2/historical-candle/{stock}/1day/{prev_date}/{prev_date}"
                r = requests.get(url, headers=HEADERS)
                data = r.json()
                candle = data.get("data", {}).get("candles", [])

                if candle:
                    pdh = candle[0][2]
                    pdl = candle[0][3]

                    url = "https://api.upstox.com/v2/market-quote/ohlc"
                    params = {"instrument_key": stock, "interval": "1d"}
                    r = requests.get(url, headers=HEADERS, params=params)
                    data = r.json()

                    key = list(data["data"].keys())[0]
                    ltp = data["data"][key]["last_price"]

                    if ltp > pdh:
                        results.append({"stock": name, "condition": "PDH Break"})
                    elif ltp < pdl:
                        results.append({"stock": name, "condition": "PDL Break"})

        except:
            continue

    return jsonify({
        "market_open": is_open,
        "date": date_used.strftime("%Y-%m-%d"),
        "data": results
    })

# ================= RUN =================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
