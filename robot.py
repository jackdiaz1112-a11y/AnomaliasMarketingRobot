#!/usr/bin/env python3
# robot.py - Generador y preparador de posts (genera copys, imágenes, last_post_for_bluesky.txt)
import os
import json
import datetime
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# --- util ---
def now_ts():
    return datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")

def safe_mkdir(p):
    Path(p).mkdir(parents=True, exist_ok=True)

# --- cargar config ---
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

books = list(config.get("books", {}).items())  # list of (title, meta)
copies_per_run = config.get("generation", {}).get("copies_per_run", 3)
images_per_run = config.get("generation", {}).get("images_per_run", 2)
paths = config.get("output_paths", {})
COPYS_DIR = Path(paths.get("copys_dir", "generated_copys"))
IMAGES_DIR = Path(paths.get("images_dir", "generated_images"))
LOGS_DIR = Path(paths.get("logs_dir", "logs"))
STATE_DIR = Path(paths.get("state_dir", "state"))

BEACONS_URL = config.get("beacons_url", "").strip()

PUBLICATION_MODE = config.get("publication", {}).get("mode", "alternate")  # alternate/random/single
DEFAULT_BOOK = config.get("publication", {}).get("default_book_for_bluesky", None)

safe_mkdir(COPYS_DIR)
safe_mkdir(IMAGES_DIR)
safe_mkdir(LOGS_DIR)
safe_mkdir(STATE_DIR)

HF_TOKEN = os.environ.get("HF_TOKEN", None)

# --- helper para UTM por libro ---
def beacons_link_for(book_key):
    base = BEACONS_URL
    meta = config["books"].get(book_key, {})
    campaign = meta.get("utm_campaign", book_key.replace(" ", "_"))
    if "?" in base:
        return f"{base}&utm_source=robot&utm_medium=post&utm_campaign={campaign}"
    else:
        return f"{base}?utm_source=robot&utm_medium=post&utm_campaign={campaign}"

# --- elegir libro a publicar (alternar) ---
def load_last_index():
    lf = STATE_DIR / "last_book_index.txt"
    if lf.exists():
        try:
            return int(lf.read_text().strip())
        except:
            return -1
    return -1

def save_last_index(i):
    lf = STATE_DIR / "last_book_index.txt"
    lf.write_text(str(i))

def pick_book_index():
    n = len(books)
    if n == 0:
        return None
    if PUBLICATION_MODE == "random":
        return random.randint(0, n-1)
    if PUBLICATION_MODE == "single":
        # use default book if set, else index 0
        if DEFAULT_BOOK:
            keys = [k for k,_ in books]
            try:
                return keys.index(DEFAULT_BOOK)
            except:
                return 0
        return 0
    # alternate
    last = load_last_index()
    nexti = (last + 1) % n
    save_last_index(nexti)
    return nexti

# --- generar copies ---
def append_beacons_link(text, book_key, short=False):
    link = beacons_link_for(book_key)
    if short:
        return text + f"\n\n→ {link}"
    else:
        return text + f"\n\nLee más y descubre la serie 'Anomalías de la Realidad': {link}"

def generar_copy_simple(libro, descripcion):
    hooks = [
        "No eres el error. Quizá es el sistema.",
        "¿Qué falla: tú o la estructura que te rodea?",
        "Ideas inquietantes para mentes inquietas.",
        "Una invitación a pensar de forma diferente."
    ]
    hook = random.choice(hooks)
    short = f"{hook}\n\n{descripcion}\n\nLink en bio."
    long = f"{hook}\n\n{descripcion}\n\nSi te interesa profundizar, revisa el libro completo en Amazon."
    short = append_beacons_link(short, libro, short=True)
    long = append_beacons_link(long, libro, short=False)
    return {"short": short, "long": long}

# --- imágenes: SD si hay token, fallback con PIL. Conservo la imagen base y genero 3 tamaños ---
def generar_imagen_placeholder(libro, prompt, out_path):
    try:
        W, H = 2048, 1152
        img = Image.new("RGB", (W, H), color=(18, 20, 26))
        draw = ImageDraw.Draw(img)
        text = f"{libro}\n\n{prompt[:240]}"
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except:
            font = ImageFont.load_default()
        draw.multiline_text((40,40), text, fill=(230,230,230), font=font)
        img.save(out_path, format="PNG")
        return out_path
    except Exception as e:
        print("Placeholder failed:", e)
        return None

def generate_resized_versions(src_path, dest_base):
    # produce 1:1, 16:9, 9:16
    try:
        img = Image.open(src_path).convert("RGB")
        sizes = {
            "square": (1080,1080),
            "wide": (1920,1080),
            "tall": (1080,1920)
        }
        out_paths = {}
        for k,s in sizes.items():
            im2 = img.copy()
            im2.thumbnail(s, Image.LANCZOS)
            # create canvas to exact size (center)
            canvas = Image.new("RGB", s, (10,10,12))
            x = (s[0]-im2.size[0])//2
            y = (s[1]-im2.size[1])//2
            canvas.paste(im2, (x,y))
            p = f"{dest_base}_{k}.png"
            canvas.save(p, format="PNG")
            out_paths[k] = p
        return out_paths
    except Exception as e:
        print("generate_resized_versions error:", e)
        return {}

def generar_imagen_sd(libro, prompt, out_path):
    try:
        from diffusers import StableDiffusionPipeline
        import torch
        model_id = "runwayml/stable-diffusion-v1-5"
        device = "cuda" if torch.cuda.is_available() else "cpu"
        pipe = StableDiffusionPipeline.from_pretrained(model_id, use_auth_token=HF_TOKEN)
        pipe = pipe.to(device)
        image = pipe(prompt, num_inference_steps=25, guidance_scale=7.5).images[0]
        image.save(out_path)
        return out_path
    except Exception as exc:
        print("SD generation failed:", exc)
        return None

# --- main ---
timestamp = now_ts()
log_lines = []
selected_idx = pick_book_index()
if selected_idx is None:
    print("No books configured.")
    exit(0)

book_key, meta = books[selected_idx]
descripcion = meta.get("descripcion", "")
print(f"[{timestamp}] Procesando libro seleccionado para publicación: {book_key}")

# ensure copys file
copys_file = COPYS_DIR / f"{book_key.replace(' ','_')}.txt"
with open(copys_file, "a", encoding="utf-8") as cf:
    for i in range(copies_per_run):
        c = generar_copy_simple(book_key, descripcion)
        cf.write(f"[{timestamp}] SHORT:\n{c['short']}\n\nLONG:\n{c['long']}\n\n---\n")
        print("Copy generado para", book_key)

# generar imagen(es)
book_img_dir = IMAGES_DIR / book_key.replace(' ','_')
safe_mkdir(book_img_dir)
generated_images = []
for i in range(images_per_run):
    prompt = f"Conceptual elegant book cover, dark elegant, philosophical, {book_key}, {descripcion}"
    filename_base = f"{book_img_dir}/{book_key.replace(' ','_')}_{timestamp}_{i+1}"
    out_path = f"{filename_base}_base.png"
    saved = None
    if HF_TOKEN:
        saved = generar_imagen_sd(book_key, prompt, out_path)
    if not saved:
        saved = generar_imagen_placeholder(book_key, prompt, out_path)
    if saved:
        generated_images.append(saved)
        resized = generate_resized_versions(saved, filename_base)
        # add also resized to list (prioritize square for posts)
        if "square" in resized:
            generated_images.append(resized["square"])
    print("Imagen guardada en:", saved)

# preparar last_post_for_bluesky.txt (primer short + primera imagen si existe)
last_text = None
with open(copys_file, "r", encoding="utf-8") as cf:
    content = cf.read().strip().split("\n\n---\n")
    # pick last block
    if content:
        last_block = content[-1]
        # extract SHORT part
        if "SHORT:" in last_block:
            parts = last_block.split("SHORT:")
            if len(parts) > 1:
                txt = parts[1].strip()
                # take first paragraph lines until LONG:
                if "LONG:" in txt:
                    txt = txt.split("LONG:")[0].strip()
                last_text = txt

if last_text is None:
    last_text = generar_copy_simple(book_key, descripcion)['short']

with open("last_post_for_bluesky.txt", "w", encoding="utf-8") as lf:
    lf.write(last_text + "\n")

# attach image path for Bluesky (choose first square or base)
image_for_bluesky = None
for p in generated_images:
    if p and p.endswith("_square.png"):
        image_for_bluesky = p
        break
if not image_for_bluesky and generated_images:
    image_for_bluesky = generated_images[0]

with open("last_post_image.txt", "w", encoding="utf-8") as lf:
    lf.write(image_for_bluesky or "")

log_lines.append(f"{timestamp} - {book_key} - copies:{copies_per_run} images:{len(generated_images)}")
logfile = LOGS_DIR / f"log_{timestamp}.txt"
with open(logfile, "w", encoding="utf-8") as lf:
    lf.write("\n".join(log_lines))

print("Robot finalizado. Logs en:", logfile)
print("Last text file:", "last_post_for_bluesky.txt")
print("Last image reference:", image_for_bluesky or "NONE")
