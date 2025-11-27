import os
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
    print("❌ No hay texto para publicar en Bluesky.")
    exit(0)

text = open(text_path, "r", encoding="utf-8").read().strip()
print("✔ Texto cargado para Bluesky:", text[:80], "...")

# Imagen opcional
img_path = None
if os.path.exists(imgref_path):
    v = open(imgref_path, "r", encoding="utf-8").read().strip()
    if v:
        img_path = v

# Conectar con Bluesky
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
    uploaded = client.com.atproto.repo.upload_blob(img_bytes)
    image_blob_ref = uploaded.blob
    print("✔ Imagen subida correctamente")

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

# Crear post
record = models.AppBskyFeedPost.Record(
    text=text,
    embed=images_embed
)

print("✔ Enviando post…")

resp = client.app.bsky.feed.post.create(
    repo=client.me.did,
    record=record
)

print("✅ Post creado exitosamente:", resp)
