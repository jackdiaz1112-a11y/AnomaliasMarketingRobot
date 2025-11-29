#!/usr/bin/env python3
import os
from datetime import datetime, timezone
from atproto import Client, models

print("▶ Iniciando publish_bluesky.py")

# Credenciales
handle = os.environ.get("BLUESKY_USERNAME")
app_password = os.environ.get("BLUESKY_PASSWORD")

if not handle or not app_password:
    print("❌ No hay credenciales de Bluesky. Abortando.")
    exit(0)

# Archivos generados por robot.py
text_path = "last_post_for_bluesky.txt"
imgref_path = "last_post_image.txt"

if not os.path.exists(text_path):
    print("❌ No existe last_post_for_bluesky.txt. Abortando.")
    exit(0)

text = open(text_path, "r", encoding="utf-8").read().strip()
print("✔ Texto cargado (inicio):", text[:80].replace("\n"," ") + " ...")

# Imagen opcional (ruta)
img_path = None
if os.path.exists(imgref_path):
    v = open(imgref_path, "r", encoding="utf-8").read().strip()
    if v:
        img_path = v

# Login
client = Client()
try:
    client.login(handle, app_password)
    # print client info safely
    me = getattr(client, "me", None)
    print("✔ Autenticado como:", getattr(me, "handle", getattr(me, "did", "<unknown>")))
except Exception as e:
    print("❌ Error autenticando en Bluesky:", e)
    exit(0)

# Subir imagen si existe y es accesible
image_blob_ref = None
if img_path:
    print("✔ Se solicitó subir imagen:", img_path)
    if os.path.exists(img_path):
        try:
            with open(img_path, "rb") as f:
                img_bytes = f.read()
            print("   Tamaño imagen (bytes):", len(img_bytes))

            # Algunas versiones aceptan (bytes), otras requieren dict; probamos ambas formas
            try:
                uploaded = client.com.atproto.repo.upload_blob(img_bytes)
            except TypeError:
                # intento alternativo (por si la firma es distinta)
                uploaded = client.com.atproto.repo.upload_blob({"blob": img_bytes})

            print("   Resultado upload_blob:", uploaded)

            # Intenta leer uploaded.blob si existe, si no mira uploaded directamente
            if hasattr(uploaded, "blob"):
                image_blob_ref = uploaded.blob
            elif isinstance(uploaded, dict) and "blob" in uploaded:
                image_blob_ref = uploaded["blob"]
            else:
                # si el objeto tiene 'ref' anidado
                try:
                    image_blob_ref = getattr(uploaded, "ref", None) or uploaded
                except Exception:
                    image_blob_ref = uploaded

            print("   Referencia de blob obtenida:", image_blob_ref)
        except Exception as e:
            print("❌ Error subiendo la imagen:", e)
    else:
        print("⚠ La ruta de imagen indicada no existe:", img_path)

# Crear embed si hay imagen valida
images_embed = None
if image_blob_ref:
    try:
        images_embed = models.AppBskyEmbedImages.Main(
            images=[
                models.AppBskyEmbedImages.Image(
                    image=image_blob_ref,
                    alt="Imagen generada por robot"
                )
            ]
        )
        print("✔ Embed de imagen creado correctamente.")
    except Exception as e:
        print("⚠ No se pudo crear embed de imagen:", e)
        images_embed = None

# Campo createdAt (compatible)
created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

# Preparar record
try:
    record = models.AppBskyFeedPost.Record(
        text=text,
        created_at=created_at,
        embed=images_embed
    )
except Exception as e:
    print("❌ Error creando record:", e)
    record = models.AppBskyFeedPost.Record(text=text, created_at=created_at)

# Publicar
try:
    resp = client.app.bsky.feed.post.create(repo=client.me.did, record=record)
    print("✔ Post creado exitosamente:", resp)
    # Guardar la URL legible
    try:
        uri = resp.get("uri") if isinstance(resp, dict) else getattr(resp, "uri", None)
        if uri:
            print("→ URI:", uri)
            # crear un archivo para referencia
            with open("last_bluesky_uri.txt", "w", encoding="utf-8") as f:
                f.write(str(uri))
    except Exception:
        pass
except Exception as e:
    print("❌ Error publicando en Bluesky:", e)
    exit(1)
