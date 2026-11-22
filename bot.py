import os
import time
import random
import base64
import threading
import urllib.parse
import requests
import telebot
from flask import Flask

TELEGRAM_TOKEN = os.environ.get("BOT_TOKEN")
if not TELEGRAM_TOKEN:
    raise ValueError("Render ke Environment Variables me BOT_TOKEN add karein!")

bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=True)
app = Flask(__name__)


@app.route("/")
def home():
    return "Smart Image Bot is running 24/7!", 200


def run_web():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def make_smart_prompt(user_text):
    try:
        sys_msg = (
            "Convert the user Hindi/Hinglish/English request into one short, "
            "highly detailed, accurate English image generation prompt. "
            "Output ONLY the English prompt, nothing else."
        )
        url = "https://text.pollinations.ai/" + urllib.parse.quote(
            sys_msg + " User request: " + user_text, safe=""
        )
        r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        if r.status_code == 200 and 3 < len(r.text.strip()) < 400:
            return r.text.strip().replace('"', "")
    except Exception:
        pass
    return user_text


def try_pollinations(p, model, w, h):
    enc = urllib.parse.quote(p, safe="")
    seed = int(time.time()) % 999999
    urls = [
        f"https://image.pollinations.ai/prompt/{enc}?model={model}&width={w}&height={h}&seed={seed}&nologo=true",
        f"https://image.pollinations.ai/prompt/{enc}?width={w}&height={h}&seed={seed}",
    ]
    last_err = "unknown"
    for url in urls:
        try:
            r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30)
            if r.status_code == 200 and "image" in r.headers.get("Content-Type", ""):
                return r.content, None
            last_err = f"Pollinations {r.status_code}"
        except Exception as e:
            last_err = str(e)
    return None, last_err


def try_horde(p):
    hdr = {"apikey": "0000000000", "Client-Agent": "ImajeBot:1.0:render"}
    payload = {
        "prompt": p,
        "params": {"width": 512, "height": 512, "steps": 20, "n": 1},
        "nsfw": False,
        "censor_nsfw": True,
        "r2": True,
    }
    try:
        r = requests.post(
            "https://aihorde.net/api/v2/generate/async",
            json=payload,
            headers=hdr,
            timeout=20,
        )
        if r.status_code != 202:
            return None, f"Horde {r.status_code}"
        gid = r.json().get("id")
        for _ in range(25):
            time.sleep(3)
            chk = requests.get(
                f"https://aihorde.net/api/v2/generate/check/{gid}",
                headers=hdr,
                timeout=15,
            ).json()
            if chk.get("faulted"):
                return None, "Horde faulted"
            if chk.get("done"):
                st = requests.get(
                    f"https://aihorde.net/api/v2/generate/status/{gid}",
                    headers=hdr,
                    timeout=15,
                ).json()
                gens = st.get("generations", [])
                if gens and gens[0].get("img"):
                    img_str = gens[0]["img"]
                    if img_str.startswith("http"):
                        img_r = requests.get(img_str, timeout=25)
                        if img_r.status_code == 200:
                            return img_r.content, None
                    else:
                        return base64.b64decode(img_str), None
                return None, "Horde empty"
        return None, "Horde timeout"
    except Exception as e:
        return None, str(e)


