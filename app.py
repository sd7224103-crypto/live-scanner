import os
import requests
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from functools import wraps
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change_this_secret")

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")

STOCK_MAP = {
    "NSE_EQ|INE002A01018": "RELIANCE",
    "NSE_EQ|INE040A01034": "HDFCBANK",
    "NSE_EQ|INE467B01029": "TCS",
    "NSE_EQ|INE009A01021": "INFY",
}

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Accept": "application/json"
}

USERS = {
    "Anoop": {"password": "Anoop@12", "role": "admin"},
    "Trader1": {"password": "trade123", "role": "user"}
}

# ================= AUTH =================

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapper

# ================= LOGIN =================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form.get("username")
        p = request.form.get("password")

        if u in USERS and USERS[u]["password"] == p:
            session["user"] = u
            session["role"] = USERS[u]["role"]
            return redirect(url_for("dashboard"))

        return render_template("login.html", error="Invalid Credentials")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ================= DASHBOARD =================

@app.route("/")
@login_required
def dashboard():
    first_stock = list(STOCK_MAP.keys())[0]
    return render_template(
        "dashboard.html",
        user=session["user"],
        role=session["role"],
        stocks=STOCK_MAP,
        first_stock=first_stock
    )
# ================= ORB SCANNER LOGIC =================

def get_previous_day(date):
    day = date - timedelta(days=1)
    while day.weekday() >= 5:
        day -= timedelta(days=1)
    return day

def fetch_915(stock, date):
    date_str = date.strftime("%Y-%m-%d")
    url = f"https://api.upstox.com/v2/historical-candle/{stock}/1minute/{date_str}/{date_str}"

    r = requests.get(url, headers=HEADERS)
    data = r.json()
    candles = data.get("data", {}).get("candles", [])

    for candle in candles:
        ts = candle[0]
        dt = datetime.fromisoformat(ts.replace("Z","+00:00"))
        if dt.hour == 9 and dt.minute == 15:
            return candle[1], candle[2], candle[3], candle[4]

    return None, None, None, None

@app.route("/orb-scanner")
@login_required
def orb_scanner():

    alerts = []
    today = datetime.now()
    prev = get_previous_day(today)

    for stock in STOCK_MAP:
        name = STOCK_MAP[stock]
        o, h, l, c = fetch_915(stock, today)

        if o is None:
            continue

        if o == l:
            alerts.append(f"🔥 {name} Open = Low")

        if o == h:
            alerts.append(f"🚀 {name} Open = High")

    return jsonify(alerts)

# ================= PDH/PDL SCANNER =================

@app.route("/pdh-scanner")
@login_required
def pdh_scanner():

    alerts = []
    prev = get_previous_day(datetime.now())
    prev_day = prev.strftime("%Y-%m-%d")

    for stock in STOCK_MAP:
        name = STOCK_MAP[stock]

        try:
            url = f"https://api.upstox.com/v2/historical-candle/{stock}/1day/{prev_day}/{prev_day}"
            r = requests.get(url, headers=HEADERS)
            data = r.json()
            candles = data.get("data", {}).get("candles", [])

            if candles:
                ph = candles[0][2]
                pl = candles[0][3]

                ltp_url = "https://api.upstox.com/v2/market-quote/ohlc"
                params = {"instrument_key": stock, "interval": "1d"}
                ltp = requests.get(ltp_url, headers=HEADERS, params=params).json()

                last_price = ltp["data"][stock]["last_price"]

                if last_price > ph:
                    alerts.append(f"🚀 {name} Broke PDH")

                if last_price < pl:
                    alerts.append(f"🔻 {name} Broke PDL")

        except:
            pass

    return jsonify(alerts)

# ================= CHART DATA =================

@app.route("/chart-data")
@login_required
def chart_data():

    stock = request.args.get("stock")
    today = datetime.now().strftime("%Y-%m-%d")
    prev = get_previous_day(datetime.now()).strftime("%Y-%m-%d")

    try:
        url = f"https://api.upstox.com/v2/historical-candle/{stock}/1minute/{today}/{today}"
        r = requests.get(url, headers=HEADERS)
        data = r.json()
        candles = data.get("data", {}).get("candles", [])

        result = []
        for c in candles:
            dt = datetime.fromisoformat(c[0].replace("Z","+00:00"))
            result.append({
                "time": int(dt.timestamp()),
                "open": c[1],
                "high": c[2],
                "low": c[3],
                "close": c[4]
            })

        url_prev = f"https://api.upstox.com/v2/historical-candle/{stock}/1day/{prev}/{prev}"
        r2 = requests.get(url_prev, headers=HEADERS)
        data2 = r2.json()
        prev_candle = data2.get("data", {}).get("candles", [])

        pdh = prev_candle[0][2] if prev_candle else None
        pdl = prev_candle[0][3] if prev_candle else None

        return jsonify({
            "candles": result,
            "pdh": pdh,
            "pdl": pdl
        })

    except:
        return jsonify({"candles": [], "pdh": None, "pdl": None})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
