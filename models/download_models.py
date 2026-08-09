import os, urllib.request, hashlib

URL="https://huggingface.co/gridshiftstudio/drumsep-onnx/resolve/main/drumsep.onnx"
OUT=os.path.join(os.path.dirname(__file__),"drumsep.onnx")
print("Downloading DrumSep ONNX (~335 MB)...")
urllib.request.urlretrieve(URL, OUT)
print("Saved:", OUT)
print("Verify the model checksum against the Hugging Face model card before distributing it.")
