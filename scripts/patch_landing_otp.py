import re
from pathlib import Path

_CLOSE_DIV = "</" + "motion>"
_CLOSE_DIV = "</" + "div>"

OTP_BLOCK = (
    '                     <div class="lf-outer mb-3">\n'
    '                        <motion style="display:flex; gap:8px; flex-wrap:wrap;">\n'
    '                           <input class="form-control" type="text" name="otp" id="otp" placeholder="Enter OTP" maxlength="6" inputmode="numeric" style="flex:1; min-width:140px;" />\n'
    '                           <button type="button" class="btn btn-outline-secondary" id="sendOtpBtn" style="white-space:nowrap;">Send OTP</button>\n'
    f"                        {_CLOSE_DIV}\n"
    '                        <small class="text-muted" style="display:block; margin-top:6px;">Verify mobile with OTP before submit.</small>\n'
    f"                     {_CLOSE_DIV}\n"
)
OTP_BLOCK = OTP_BLOCK.replace("<motion style", "<div style")

VALIDATE_SNIPPET = """
		if (typeof validateLandingOtpField === 'function' && !validateLandingOtpField()) {
		  return false;
		}

		return true;"""

PATHS = [
    Path(r"c:\Time_kinds\time4kids\public\timekids-2g\landing-page.html"),
    Path(r"c:\Time_kinds\time4kids\public\timekids-2g\landing-page-yt.html"),
    Path(r"c:\Time_kinds\time4kids\timekids-2g\pages\landing-page.html"),
    Path(r"c:\Time_kinds\time4kids\timekids-2g\pages\landing-page-fb.html"),
    Path(r"c:\Time_kinds\time4kids\timekids-2g\pages\landing-page-yt.html"),
    Path(r"c:\Time_kinds\timekids\timekids-2g\pages\landing-page-fb.html"),
]

JS_SRC = Path(r"c:\Time_kinds\time4kids\public\timekids-2g\js\landing-form-otp.js")
for dest in (
    Path(r"c:\Time_kinds\time4kids\timekids-2g\js\landing-form-otp.js"),
    Path(r"c:\Time_kinds\timekids-2g\js\landing-form-otp.js"),
):
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(JS_SRC.read_text(encoding="utf-8"), encoding="utf-8")

for path in PATHS:
    if not path.exists():
        print("skip missing", path)
        continue
    text = path.read_text(encoding="utf-8")
    text = text.replace("</motion>", _CLOSE_DIV).replace("<motion ", "<" + "div ")
    if 'name="otp"' not in text:
        text = re.sub(
            r'(<input class="form-control" type="text" name="telephone" id="telephone"[^>]*>\s*</div>\s*)'
            r'<div class="lf-outer mb-3">\s*<input class="form-control" type="text" name="email"',
            r"\1" + OTP_BLOCK + '                     <div class="lf-outer mb-3">\n                        <input class="form-control" type="text" name="email"',
            text,
            count=1,
        )
    if "validateLandingOtpField" not in text:
        old = (
            "\t\tif (!location || location === 'Select Location') {\n"
            "\t\t  alert('Please select a location.');\n"
            "\t\t  $('#Location').focus();\n"
            "\t\t  return false;\n"
            "\t\t}\n\n\t\treturn true;"
        )
        new = (
            "\t\tif (!location || location === 'Select Location') {\n"
            "\t\t  alert('Please select a location.');\n"
            "\t\t  $('#Location').focus();\n"
            "\t\t  return false;\n"
            "\t\t}" + VALIDATE_SNIPPET
        )
        text = text.replace(old, new)
    in_pages = path.parts[-2] == "pages"
    script_tag = "../js/landing-form-otp.js" if in_pages else "js/landing-form-otp.js"
    jquery_tag = "../js/jquery-3.5.1.min.js" if in_pages else "js/jquery-3.5.1.min.js"
    if "landing-form-otp.js" not in text:
        text = text.replace(
            f'<script src="{jquery_tag}"></script>',
            f'<script src="{jquery_tag}"></script>\n      <script src="{script_tag}"></script>',
        )
    path.write_text(text, encoding="utf-8")
    print("patched", path)
