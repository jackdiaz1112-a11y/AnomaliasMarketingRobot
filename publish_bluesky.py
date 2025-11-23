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
print("✔ Texto cargado para Bluesky:", text[:80], "...")

# Imagen opcional
img_path = None
if os.path.exists(imgref_path):
    v = open(imgref_path, "r", encoding="utf-8").read().strip()
    if v:
        img_path = v

# Login
client = Client()
client.login(handle, app_password)
print("✔ Autenticado como:", client.me.handle)

# Subir imagen si existe
image_blob_ref = None
if img_path and os.path.exists(img_path):
    print("✔ Subiendo imagen:", img_path)
    with open(img_path, "rb") as f:
        img_bytes = f.read()

    print("   Tamaño imagen:", len(img_bytes), "bytes")

    # upload_blob SOLO recibe los bytes
    uploaded = client.com.atproto.repo.upload_blob(img_bytes)
    print("✔ Resultado upload_blob:", uploaded)

    # La referencia está en uploaded.blob
    image_blob_ref = uploaded.blob

# Crear embed si hay imagen
images_embed = None
if image_blob_ref:
    images_embed = models.AppBskyEmbedImages.Main(
        images=[
            models.AppBskyEmbedImages.Image(
                image=image_blob_ref,
                alt="Imagen generada automáticamente"
            )
        ]
    )
    print("✔ Embed de imagen creado")

# Campo obligatorio createdAt
created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

record = models.AppBskyFeedPost.Record(
    text=text,
    created_at=created_at,
    embed=images_embed
)

print("✔ Record preparado, enviando post...")

resp = client.app.bsky.feed.post.create(
    repo=client.me.did,
    record=record
)

print("✔ Post creado exitosamente:", resp)
