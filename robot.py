#!/usr/bin/env python3
# robot.py - versión para GitHub Actions (automatización)
import os
import json
import datetime
import random
from pathlib import Path

# Opcional: imprimir para logs
print("Iniciando robot:", datetime.datetime.utcnow().isoformat())

# Cargar configuración
with open("config.json", "r", encoding="utf-8") as f:
    config = json.load(f)

books = config.get("books", {})
copies_per_run = config.get("generation", {}).get("copies_per_run", 3)
images_per_run = config.get("generation", {}).get("images_per_run", 2)
paths = config.get("output_paths", {})
COPYS_DIR = Path(paths.get("copys_dir", "generated_copys"))
IMAGES_DIR = Path(paths.get("images_dir", "generated_images"))
LOGS_DIR = Path(paths.get("logs_dir", "logs"))

# Asegurar existencia de carpetas
COPYS_DIR.mkdir(parents=True, exist_ok=True)
IMAGES_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Token seguro pasado por GitHub Secrets -> variable de entorno HF_TOKEN
HF_TOKEN = os.environ.get("HF_TOKEN", None)

# Función simple para generar copy (puedes sofisticarla luego)
def generar_copy_simple(libro, descripcion):
    hooks = [
        "No eres el error. Quizá es el sistema.",
        "¿Qué falla: tú o la estructura que te rodea?",
        "Ideas inquietantes para mentes inquietas.",
        "Una invitación a pensar de forma diferente."
    ]
    hook = random.choice(hooks)
    short = f"{hook}\n\n{descripcion}\n\nLink en bio."
    long = f"{hook}\n\n{descripcion}\n\nSi te interesa profundizar, revisa el libro completo en Amazon.\n"
    return {"short": short, "long": long}

# Función para generar imágenes: intenta usar Diffusers si HF token existe
def generar_imagen_placeholder(libro, prompt, filename_out):
    # Fallback simple: crea un png con texto (muy básico) para no fallar si no hay SD
    try:
        from PIL import Image, ImageDraw, ImageFont
        img = Image.new("RGB", (1024, 576), color=(10, 10, 15))
        draw = ImageDraw.Draw(img)
        text = f"{libro}\n{prompt[:120]}"
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
        except:
            font = None
        draw.text((40, 40), text, fill=(230,230,230), font=font)
        img.save(filename_out)
        return filename_out
    except Exception as e:
        print("Error generador placeholder:", e)
        return None

def generar_imagen_stablediffusion(libro, prompt, filename_out):
    try:
        # import aqui para evitar fallos si no está instalado
        from diffusers import StableDiffusionPipeline
        import torch

        device = "cuda" if torch.cuda.is_available() else "cpu"
        model_id = "runwayml/stable-diffusion-v1-5"
        pipe = StableDiffusionPipeline.from_pretrained(model_id, use_auth_token=HF_TOKEN)
        pipe = pipe.to(device)
        image = pipe(prompt, num_inference_steps=25, guidance_scale=7.5).images[0]
        image.save(filename_out)
        return filename_out
    except Exception as e:
        print("SD generation failed:", e)
        return None

# Ejecutar generación
timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
log_lines = []
for libro, meta in books.items():
    descripcion = meta.get("descripcion", "")
    print(f"Procesando libro: {libro}")

    # Generar copies
    copys_file = COPYS_DIR / f"{libro.replace(' ', '_')}.txt"
    with open(copys_file, "a", encoding="utf-8") as cf:
        for i in range(copies_per_run):
            c = generar_copy_simple(libro, descripcion)
            cf.write(f"[{timestamp}] SHORT:\n{c['short']}\n\nLONG:\n{c['long']}\n\n---\n")
            print("Copy generado para", libro)

    # Generar imágenes
    for i in range(images_per_run):
        prompt = f"Conceptual, elegant, dark aesthetic, book {libro}, idea: {descripcion}"
        filename = IMAGES_DIR / f"{libro.replace(' ','_')}_{timestamp}_{i+1}.png"

        saved = None
        if HF_TOKEN:
            saved = generar_imagen_stablediffusion(libro, prompt, str(filename))
        if not saved:
            saved = generar_imagen_placeholder(libro, prompt, str(filename))
        print("Imagen guardada en:", saved)

    log_lines.append(f"{timestamp} - {libro} - copies: {copies_per_run} images: {images_per_run}")

# Guardar log
logfile = LOGS_DIR / f"log_{timestamp}.txt"
with open(logfile, "w", encoding="utf-8") as lf:
    lf.write("\n".join(log_lines))

print("Robot finalizado. Logs en:", logfile)
