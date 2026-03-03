import os
import requests
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, session, jsonify, url_for
from functools import wraps

# ===============================
# CONFIG
# ===============================

ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev_key")

app = Flask(__name__)
app.secret_key = SECRET_KEY

HEADERS = {
    "Authorization": f"Bearer {ACCESS_TOKEN}",
    "Accept": "application/json"
}

# ===============================
# DEMO USERS (Multi User)
# ===============================

USERS = {
    "Anoop": {"password": "Anoop@12", "role": "admin"},
    "User1": {"password": "1234", "role": "user"}
}

# ===============================
# STOCK LIST
# ===============================

STOCK_MAP = {
    "NSE_EQ|INE002A01018": "RELIANCE",
    "NSE_EQ|INE040A01034": "HDFCBANK",
    "NSE_EQ|INE467B01029": "TCS",
    "NSE_EQ|INE009A01021": "INFY",
}

# ===============================
# LOGIN REQUIRED DECORATOR
# ===============================

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper

# ===============================
# ROUTES
# ===============================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        user = USERS.get(username)

        if user and user["password"] == password:
            session["user"] = username
            session["role"] = user["role"]
            return redirect("/")
        else:
            return "Invalid Credentials"

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


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


@app.route("/admin")
@login_required
def admin():
    if session.get("role") != "admin":
        return "Unauthorized"
    return render_template("admin.html")


# ===============================
# CHART DATA API
# ===============================

@app.route("/chart-data")
@login_required
def chart_data():

    stock = request.args.get("stock")

    if not stock:
        return jsonify({"error": "Stock missing"})

    today = datetime.now().strftime("%Y-%m-%d")
    prev = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

    try:
        # Try Today Intraday
        url = f"https://api.upstox.com/v2/historical-candle/{stock}/1minute/{today}/{today}"
        r = requests.get(url, headers=HEADERS, timeout=5)
        data = r.json()

        candles = data.get("data", {}).get("candles", [])

        # If today empty → use previous day
        if not candles:
            url = f"https://api.upstox.com/v2/historical-candle/{stock}/1minute/{prev}/{prev}"
            r = requests.get(url, headers=HEADERS, timeout=5)
            data = r.json()
            candles = data.get("data", {}).get("candles", [])

        formatted = []

        for c in candles:
            dt = datetime.fromisoformat(c[0].replace("Z", "+00:00"))
            formatted.append({
                "time": int(dt.timestamp()),
                "open": c[1],
                "high": c[2],
                "low": c[3],
                "close": c[4]
            })

        # Fetch Previous Day High/Low
        pdh = None
        pdl = None

        try:
            url = f"https://api.upstox.com/v2/historical-candle/{stock}/1day/{prev}/{prev}"
            r = requests.get(url, headers=HEADERS, timeout=5)
            data = r.json()
            day_candle = data.get("data", {}).get("candles", [])

            if day_candle:
                pdh = day_candle[0][2]
                pdl = day_candle[0][3]

        except:
            pass

        return jsonify({
            "candles": formatted,
            "pdh": pdh,
            "pdl": pdl
        })

    except Exception as e:
        return jsonify({
            "candles": [],
            "pdh": None,
            "pdl": None
        })


# ===============================
# HEALTH CHECK (UptimeRobot)
# ===============================

@app.route("/health")
def health():
    return "OK"


# ===============================
# RUN
# ===============================

if __name__ == "__main__":
    app.run(debug=True)
