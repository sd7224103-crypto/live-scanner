from flask import Flask
import threading
import time

app = Flask(__name__)

def scanner():
    while True:
        print("Scanner Running...")
        time.sleep(10)

@app.route("/")
def home():
    return "Live Scanner Running 🚀"

# Start background scanner thread
threading.Thread(target=scanner, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
