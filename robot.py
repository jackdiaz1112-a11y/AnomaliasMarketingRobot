#!/usr/bin/env python3
# robot.py - Generador de copys e imágenes para autopublicación
import os
import json
import datetime
import random
import base64
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ----- Config -----
ROOT = Path(".")
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

books = list(config.get("books", {}).items())
copies_per_run = config.get("generation", {}).get("copies_per_run", 3)
images_per_run = config.get("generation", {}).get("images_per_run", 1)
paths = config.get("output_paths", {})
COPYS_DIR = Path(paths.get("copys_dir", "generated_copys"))
IMAGES_DIR = Path(paths.get("images_dir", "generated_images"))
LOGS_DIR = Path(paths.get("logs_dir", "logs"))
STATE_DIR = Path(paths.get("state_dir", "state"))
BEACONS_URL = config.get("beacons_url", "").strip()

HF_TOKEN = os.environ.get("HF_TOKEN", None)

# Ensure dirs
for p in [COPYS_DIR, IMAGES_DIR, LOGS_DIR, STATE_DIR]:
    p.mkdir(parents=True, exist_ok=True)

ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")

# Utility: beacons link with UTM per book
def beacons_link_for(book_key):
    base = BEACONS_URL
    meta = dict(config.get("books", {})).get(book_key, {})
    campaign = meta.get("utm_campaign", book_key.replace(" ", "_"))
    if "?" in base:
        return f"{base}&utm_source=robot&utm_medium=post&utm_campaign={campaign}"
    return f"{base}?utm_source=robot&utm_medium=post&utm_campaign={campaign}"

# Pick book (alternate mode)
def load_last_index():
    p = STATE_DIR / "last_book_index.txt"
    if p.exists():
        try:
            return int(p.read_text().strip())
        except:
            return -1
    return -1

def save_last_index(i):
    (STATE_DIR / "last_book_index.txt").write_text(str(i))

def pick_book_index():
    n = len(books)
    if n == 0:
        return None
    mode = config.get("publication", {}).get("mode", "alternate")
    if mode == "random":
        return random.randint(0, n-1)
    if mode == "single":
        default = config.get("publication", {}).get("default_book_for_bluesky")
        if default:
            keys = [k for k,_ in books]
            try:
                return keys.index(default)
            except:
                return 0
        return 0
    # alternate
    last = load_last_index()
    nexti = (last + 1) % n
    save_last_index(nexti)
    return nexti

# HF Inference API helpers (text and image)
HF_INFERENCE_URL = "https://api-inference.huggingface.co/models/"

def hf_text_generate(prompt, models_to_try=None, max_tokens=200):
    if not HF_TOKEN:
        return None
    headers = {"Authorization": f"Bearer {HF_TOKEN}", "Accept": "application/json"}
    if models_to_try is None:
        models_to_try = ["mistralai/Mistral-7B-Instruct", "google/flan-ul2", "bigscience/bloomz"]
    for model in models_to_try:
        try:
            import requests, json as _js
            url = HF_INFERENCE_URL + model
            payload = {"inputs": prompt, "parameters": {"max_new_tokens": max_tokens}}
            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            if resp.status_code == 200:
                j = resp.json()
                # Inference API may return text in different shapes
                if isinstance(j, dict) and "generated_text" in j:
                    return j["generated_text"]
                if isinstance(j, list) and len(j) > 0 and "generated_text" in j[0]:
                    return j[0]["generated_text"]
                # Try raw string
                if isinstance(j, str):
                    return j
                # else try to extract string
                return str(j)
            else:
                # try next model
                continue
        except Exception as e:
            continue
    return None

def hf_image_generate(prompt, model="stabilityai/stable-diffusion-2"):
    if not HF_TOKEN:
        return None
    import requests
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    url = HF_INFERENCE_URL + model
    try:
        payload = {"inputs": prompt}
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        if resp.status_code == 200:
            # response may be bytes -> save
            content_type = resp.headers.get("content-type","")
            if "image" in content_type:
                return resp.content
            # sometimes returns json with base64
            j = resp.json()
            # if 'image' field base64
            for key in ("image","images","generated_image"):
                if key in j:
                    b64 = j[key]
                    return base64.b64decode(b64)
            # fallback: try first item's 'blob' field
            if isinstance(j, list) and j and "blob" in j[0]:
                return base64.b64decode(j[0]["blob"])
        return None
    except Exception:
        return None

# Placeholder image generator
def placeholder_image(book_key, prompt, out_path):
    try:
        W, H = 2048, 1152
        img = Image.new("RGB", (W, H), color=(18, 20, 26))
        draw = ImageDraw.Draw(img)
        text = f"{book_key}\n\n{prompt[:300]}"
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except:
            font = ImageFont.load_default()
        draw.multiline_text((40,40), text, fill=(230,230,230), font=font)
        img.save(out_path, format="PNG")
        return out_path
    except Exception:
        return None

# Compose copy
def compose_copies(book_key, description):
    hooks = [
        "No eres el error. Quizá es el sistema.",
        "¿Qué falla, tú o la estructura que te rodea?",
        "Ideas inquietantes para mentes inquietas.",
        "Una invitación a pensar distinto."
    ]
    hook = random.choice(hooks)
    prompt = f"Escribe un copy corto y efectivo para redes sociales (20-40 palabras) sobre el libro '{book_key}' describiéndolo así: {description}. Termina con una llamada a la acción que invite a visitar el link en bio."
    # try hf
    text_try = hf_text_generate(prompt, max_tokens=80)
    if text_try:
        short = text_try.strip()
    else:
        short = f"{hook} {description[:140]} — Lee más en el link en bio."
    # long form
    prompt2 = f"Escribe un texto más largo (50-140 palabras) sobre el libro '{book_key}' con tono inquietante y filosófico, incluye una CTA para visitar el link en bio."
    text_try2 = hf_text_generate(prompt2, max_tokens=180)
    if text_try2:
        long = text_try2.strip()
    else:
        long = f"{hook}\n\n{description}\n\nSi quieres profundizar, visita el link en bio."
    # append beacons link
    link = beacons_link_for(book_key)
    short = f"{short}\n\n→ {link}"
    long = f"{long}\n\nLee más: {link}"
    return {"short": short, "long": long}

# Main: pick book, generate copies and image, save last_post files
def main():
    idx = pick_book_index()
    if idx is None:
        print("No books configured.")
        return
    book_key, meta = books[idx]
    description = meta.get("descripcion", "")
    print("Selected book:", book_key)

    # generate copies
    copys_file = COPYS_DIR / f"{book_key.replace(' ', '_')}.txt"
    with open(copys_file, "a", encoding="utf-8") as cf:
        for _ in range(copies_per_run):
            c = compose_copies(book_key, description)
            cf.write(f"[{ts}] SHORT:\n{c['short']}\n\nLONG:\n{c['long']}\n\n---\n")
            print("Wrote copy for", book_key)

    # generate image
    book_img_dir = IMAGES_DIR / book_key.replace(" ", "_")
    book_img_dir.mkdir(parents=True, exist_ok=True)
    generated_image_path = None
    for i in range(images_per_run):
        prompt = f"Book cover concept, dark elegant, philosophical, minimal, for the book titled '{book_key}': {description}"
        img_bytes = hf_image_generate(prompt)
        filename = book_img_dir / f"{book_key.replace(' ','_')}_{ts}_{i+1}.png"
        if img_bytes:
            try:
                with open(filename, "wb") as f:
                    f.write(img_bytes)
                generated_image_path = str(filename)
            except Exception:
                generated_image_path = None
        if not generated_image_path:
            # fallback placeholder
            ph = placeholder_image(book_key, prompt, str(filename))
            if ph:
                generated_image_path = ph
        print("Image saved:", generated_image_path)

    # prepare last_post_for_bluesky.txt and last_post_image.txt
    # pick last short from file
    last_short = None
    try:
        with open(copys_file, "r", encoding="utf-8") as cf:
            content = cf.read().strip().split("\n\n---\n")
            if content:
                last_block = content[-1]
                if "SHORT:" in last_block:
                    part = last_block.split("SHORT:")[1]
                    if "LONG:" in part:
                        part = part.split("LONG:")[0]
                    last_short = part.strip()
    except Exception:
        last_short = None

    if not last_short:
        last_short = compose_copies(book_key, description)["short"]

    with open("last_post_for_bluesky.txt", "w", encoding="utf-8") as lf:
        lf.write(last_short + "\n")

    with open("last_post_image.txt", "w", encoding="utf-8") as lf:
        lf.write(generated_image_path or "")

    # log
    logf = LOGS_DIR / f"log_{ts}.txt"
    with open(logf, "w", encoding="utf-8") as lg:
        lg.write(f"{ts} - {book_key} - copies:{copies_per_run} images:{images_per_run}\n")
    print("Finished. last_post_for_bluesky.txt and last_post_image.txt created.")

if __name__ == "__main__":
    main()
