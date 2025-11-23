#!/usr/bin/env python3
# robot.py - Generador de copys e imágenes
import os, json, datetime, random, base64
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# --- Cargar config ---
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

# Asegurar dirs
for d in (COPYS_DIR, IMAGES_DIR, LOGS_DIR, STATE_DIR):
    d.mkdir(parents=True, exist_ok=True)

def beacons_link_for(book_key):
    base = BEACONS_URL
    meta = dict(config.get("books", {})).get(book_key, {})
    campaign = meta.get("utm_campaign", book_key.replace(" ", "_"))
    if "?" in base:
        return f"{base}&utm_source=robot&utm_medium=post&utm_campaign={campaign}"
    return f"{base}?utm_source=robot&utm_medium=post&utm_campaign={campaign}"

# Selección alternada de libro
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
    last = load_last_index()
    nexti = (last + 1) % n
    save_last_index(nexti)
    return nexti

# HF Inference helpers (texto e imagen)
HF_API_BASE = "https://api-inference.huggingface.co/models/"

def hf_text_generate(prompt, models=None, max_tokens=200):
    if not HF_TOKEN:
        return None
    import requests
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    if models is None:
        models = ["mistralai/Mistral-7B-Instruct", "google/flan-ul2", "bigscience/bloomz"]
    for m in models:
        try:
            url = HF_API_BASE + m
            payload = {"inputs": prompt, "parameters": {"max_new_tokens": max_tokens}}
            r = requests.post(url, headers=headers, json=payload, timeout=30)
            if r.status_code == 200:
                j = r.json()
                # extraer texto
                if isinstance(j, dict) and "generated_text" in j:
                    return j["generated_text"]
                if isinstance(j, list) and j and isinstance(j[0], dict) and "generated_text" in j[0]:
                    return j[0]["generated_text"]
                if isinstance(j, str):
                    return j
                return str(j)
        except Exception:
            continue
    return None

def hf_image_generate(prompt, model="stabilityai/stable-diffusion-2"):
    if not HF_TOKEN:
        return None
    import requests
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}
    url = HF_API_BASE + model
    try:
        r = requests.post(url, headers=headers, json={"inputs": prompt}, timeout=60)
        if r.status_code == 200:
            # si viene imagen raw
            content_type = r.headers.get("content-type", "")
            if "image" in content_type:
                return r.content
            j = r.json()
            # posible base64 en distintos campos
            for key in ("image","images","generated_image","data"):
                if key in j:
                    b64 = j[key]
                    return base64.b64decode(b64)
            # fallback
            return None
    except Exception:
        return None

# Placeholder image generator
def placeholder_image(book_key, prompt, out_path):
    W,H = 2048,1152
    try:
        img = Image.new("RGB",(W,H),color=(22,22,25))
        draw = ImageDraw.Draw(img)
        text = f"{book_key}\n\n{prompt[:300]}"
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
        except:
            font = ImageFont.load_default()
        draw.multiline_text((40,40), text, fill=(230,230,230), font=font)
        img.save(out_path, format="PNG")
        return out_path
    except Exception:
        return None

# Compose copies
def compose_copies(book_key, description):
    hooks = [
        "No eres el error. Quizá es el sistema.",
        "¿Qué falla, tú o la estructura que te rodea?",
        "Ideas inquietantes para mentes inquietas.",
        "Una invitación a pensar distinto."
    ]
    hook = random.choice(hooks)
    prompt_short = f"Escribe un copy corto (20-40 palabras) para redes sobre '{book_key}': {description}. Termina invitando al link en bio."
    text_short = hf_text_generate(prompt_short, max_tokens=80)
    if not text_short:
        text_short = f"{hook} {description[:140]} — Lee más en el link en bio."
    prompt_long = f"Escribe un texto largo (50-140 palabras) con tono filosófico-inquietante sobre '{book_key}' y una CTA al link en bio."
    text_long = hf_text_generate(prompt_long, max_tokens=180)
    if not text_long:
        text_long = f"{hook}\n\n{description}\n\nSi quieres profundizar, visita el link en bio."
    link = beacons_link_for(book_key)
    short = f"{text_short}\n\n→ {link}"
    long = f"{text_long}\n\nLee más: {link}"
    return {"short": short, "long": long}

# Main
def main():
    idx = pick_book_index()
    if idx is None:
        print("No books configured.")
        return
    book_key, meta = books[idx]
    description = meta.get("descripcion","")
    ts = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    print("Selected:", book_key)

    # copys
    copys_file = COPYS_DIR / f"{book_key.replace(' ','_')}.txt"
    with open(copys_file, "a", encoding="utf-8") as cf:
        for _ in range(copies_per_run):
            c = compose_copies(book_key, description)
            cf.write(f"[{ts}] SHORT:\n{c['short']}\n\nLONG:\n{c['long']}\n\n---\n")
            print("Wrote copy")

    # images
    book_img_dir = IMAGES_DIR / book_key.replace(" ", "_")
    book_img_dir.mkdir(parents=True, exist_ok=True)
    generated_image = None
    for i in range(images_per_run):
        prompt = f"Book cover concept, dark elegant, minimal, philosophical: '{book_key}' — {description}"
        img_bytes = hf_image_generate(prompt)
        out_file = book_img_dir / f"{book_key.replace(' ','_')}_{ts}_{i+1}.png"
        if img_bytes:
            try:
                with open(out_file, "wb") as f:
                    f.write(img_bytes)
                generated_image = str(out_file)
            except Exception:
                generated_image = None
        if not generated_image:
            ph = placeholder_image(book_key, prompt, str(out_file))
            if ph:
                generated_image = ph
        print("Saved image:", generated_image)

    # last_post files
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
        lf.write(generated_image or "")

    # log
    logf = LOGS_DIR / f"log_{ts}.txt"
    with open(logf, "w", encoding="utf-8") as lg:
        lg.write(f"{ts} - {book_key} - copies:{copies_per_run} images:{images_per_run}\n")
    print("Done. Files created: last_post_for_bluesky.txt, last_post_image.txt")

if __name__ == "__main__":
    main()
