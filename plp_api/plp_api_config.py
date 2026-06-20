# PLP / TiKES enrollment API key — set PLP_API_KEY in .env (see .env.example).
# TiKES calls POST /api/plp/create-enrollment/ with header: X-API-Key: <this value>

import os

PLP_API_KEY = os.getenv(
    "PLP_API_KEY",
    "5a65a53ccedda13b510dca83f117d538711f8f53c7a2f26b9471960a14089938",
).strip()
