
#!/usr/bin/env python3
# publish_bluesky.py - Publica lo generado en Bluesky usando atproto
import os
from pathlib import Path
from atproto import Client
from atproto.models import AppBskyFeedPost, AppBskyEmbedImages

handle = os.environ.get("BLUESKY_USERNAME")
app_password = os.environ.get("BLUESKY_PASSWORD")

if not handle or not app_password:
    print("No Bluesky credentials in env. Exiting.")
    exit(0)

text_path = Path("last_post_for_bluesky.txt")
img_ref_path = Path("last_post_image.txt")

if not text_path.exists():
    print("No last_post_for_bluesky.txt found. Exiting.")
    exit(0)

text = text_path.read_text(encoding="utf-8").strip()

image_blob_ref = None
if img_ref_path.exists():
    img = img_ref_path.read_text(encoding="utf-8").strip()
    if img and Path(img).exists():
        with open(img, "rb") as f:
            b = f.read()
        client = Client()
        client.login(handle, app_password)
        uploaded = client.com.atproto.repo.upload_blob(b, "image/png")
        image_blob_ref = uploaded.blob
    else:
        client = Client()
        client.login(handle, app_password)
else:
    client = Client()
    client.login(handle, app_password)

images_embed = None
if image_blob_ref:
    images_embed = AppBskyEmbedImages.Main(
        images=[AppBskyEmbedImages.Image(image=image_blob_ref, alt="Imagen generada por robot")]
    )

record = AppBskyFeedPost.Record(text=text, embed=images_embed)
resp = client.app.bsky.feed.post.create(repo=client.me.did, record=record)
print("Posted to Bluesky:", resp)
