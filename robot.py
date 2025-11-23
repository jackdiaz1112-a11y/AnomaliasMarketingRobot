#!/usr/bin/env python3
# robot.py - Generador de textos e imágenes para publicaciones automatizadas

import os
import json
import datetime
import random
import base64
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# -------------------------------
# Cargar configuración
# -------------------------------
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

BOOKS = config["books"]
HF_TOKEN = os.environ.get("HF_TOKEN")

OUTPUT_DIR = Path("generated_images")
OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

# -------------------------------
# Función mejorada: Hugging Face Image Generation
# -------------------------------
def hf_image_generate(prompt, model="stabilityai/stable-diffusion-xl-base-1.0"):
    """
    Intenta generar una imagen mediante Hugging Face.
    Devuelve bytes de imagen PNG o None en caso de error.
    """

    if not HF_TOKEN:
        print("⚠ No hay HF_TOKEN disponible, usando placeholder.")
        return None

    import requests

    url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}

    payload = {"inputs": prompt}

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=90)

        if r.status_code == 200:
            ctype = r.headers.get("content-type", "")

            # Imagen directa
            if "image" in ctype:
                return r.content

            # Posibles formatos JSON
            data = r.json()

            # 1. Chequear claves estándar
            for key in ("image", "images", "generated_image", "data"):
                if key in data:
                    value = data[key]

                    # Caso lista
                    if isinstance(value, list):
                        v = value[0]
                        return base64.b64decode(v)

                    # Caso string base64
                    if isinstance(value, str):
                        return base64.b64decode(value)

            print("⚠ Hugging Face devolvió JSON sin imagen válida.")
            return None

        else:
            print("⚠ Error en Hugging Face:", r.status_code, r.text[:200])
            return None

    except Exception as e:
        print("⚠ Excepción al contactar Hugging Face:", e)
        return None


# -------------------------------
# Función placeholder mejorada
# -------------------------------
def placeholder_image(book_key, prompt, out_path):
    W, H = 2048, 1152

    try:
        img = Image.new("RGB", (W, H), color=(245, 245, 250))
        draw = ImageDraw.Draw(img)

        # Degradado vertical suave
        for y in range(H):
            shade = 245 - int((y / H) * 40)
            draw.line([(0, y), (W, y)], fill=(shade, shade, shade))

        text = f"{book_key}\n\n{prompt[:300]}"

        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 42)
        except:
            font = ImageFont.load_default()

        draw.multiline_text(
            (80, 80),
            text,
            fill=(20, 20, 20),
            font=font,
            spacing=10,
        )

        img.save(out_path, format="PNG", optimize=True)
        return out_path

    except Exception as e:
        print("⚠ Error creando placeholder:", e)
        return None


# -------------------------------
# Selección aleatoria del libro
# -------------------------------
def pick_book():
    keys = list(BOOKS.keys())
    key = random.choice(keys)
    data = BOOKS[key]
    return key, data


# -------------------------------
# Generar texto para Bluesky
# -------------------------------
def build_copy(book_key, book_data):
    frases = book_data["frases"]
    frase = random.choice(frases)

    hoy = datetime.datetime.now().strftime("%Y-%m-%d")
    copy = f"Ideas inquietantes para mentes inquietas. {frase}\n\n#{book_key} — {hoy}"

    return copy


# -------------------------------
# Flujo principal
# -------------------------------
def main():
    print("▶ Ejecutando robot.py")

    book_key, book_data = pick_book()
    prompt = book_data["prompt"]

    # Ruta de imagen
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    img_dir = OUTPUT_DIR / book_key
    img_dir.mkdir(parents=True, exist_ok=True)
    img_path = img_dir / f"{book_key}_{ts}.png"

    print(f"▶ Libro elegido: {book_key}")
    print("▶ Generando texto...")

    # Generar texto
    copy = build_copy(book_key, book_data)

    # Guardar texto para Bluesky
    with open("last_post_for_bluesky.txt", "w", encoding="utf-8") as f:
        f.write(copy)

    # Intentar generar imagen con Hugging Face
    print("▶ Generando imagen con Hugging Face...")
    img_bytes = hf_image_generate(prompt)

    if img_bytes:
        print("✔ Imagen obtenida desde Hugging Face")
        with open(img_path, "wb") as f:
            f.write(img_bytes)
    else:
        print("⚠ HF falló, usando placeholder")
        placeholder_image(book_key, prompt, img_path)

    # Registrar ruta para Bluesky
    with open("last_post_image.txt", "w", encoding="utf-8") as f:
        f.write(str(img_path))

    print("✔ Robot completado")


# -------------------------------
# Ejecutar
# -------------------------------
if __name__ == "__main__":
    main()
