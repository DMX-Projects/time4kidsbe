import re
from pathlib import Path

PATHS = [
    Path(r"c:\Time_kinds\time4kids\public\timekids-2g\landing-page-fb.html"),
    Path(r"c:\Time_kinds\time4kids\public\timekids-2g\landing-page.html"),
    Path(r"c:\Time_kinds\time4kids\public\timekids-2g\landing-page-yt.html"),
    Path(r"c:\Time_kinds\time4kids\timekids-2g\pages\landing-page-fb.html"),
    Path(r"c:\Time_kinds\time4kids\timekids-2g\pages\landing-page.html"),
    Path(r"c:\Time_kinds\time4kids\timekids-2g\pages\landing-page-yt.html"),
    Path(r"c:\Time_kinds\timekids-2g\pages\landing-page-fb.html"),
    Path(r"c:\Time_kinds\timekids-2g\pages\landing-page.html"),
    Path(r"c:\Time_kinds\timekids-2g\pages\landing-page-yt.html"),
]

JS_SRC = Path(r"c:\Time_kinds\time4kids\public\timekids-2g\js\landing-form-otp.js")
for dest in (
    Path(r"c:\Time_kinds\time4kids\timekids-2g\js\landing-form-otp.js"),
    Path(r"c:\Time_kinds\timekids-2g\js\landing-form-otp.js"),
):
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(JS_SRC.read_text(encoding="utf-8"), encoding="utf-8")

OTP_BLOCK_RE = re.compile(
    r"\s*<div class=\"lf-outer mb-3\">\s*"
    r"<div style=\"display:flex;[^\"]*\">.*?"
    r"Verify mobile with OTP before submit\.</small>\s*"
    r"</div>\s*",
    re.DOTALL,
)

for path in PATHS:
    if not path.exists():
        print("skip", path)
        continue
    text = path.read_text(encoding="utf-8")
    text = OTP_BLOCK_RE.sub("\n", text)
    text = text.replace(
        'onsubmit="return validate();"',
        'onsubmit="return handleLandingFormSubmit(event);"',
    )
    text = re.sub(
        r"\n\t\tif \(typeof validateLandingOtpField === 'function' && !validateLandingOtpField\(\)\) \{\n\t\t  return false;\n\t\t\}\n",
        "\n",
        text,
    )
    if "function validate()" in text and "handleLandingFormSubmit" in text:
        text = re.sub(
            r"\n\t  <script>\n\t  function validate\(\) \{.*?\n\t\treturn true;\n\t  \}\n",
            "\n\t  <script>\n",
            text,
            count=1,
            flags=re.DOTALL,
        )
    path.write_text(text, encoding="utf-8")
    print("patched", path)
