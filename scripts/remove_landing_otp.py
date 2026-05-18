from pathlib import Path

VALIDATE_FN = """
\t  function validate() {
\t\tvar name = $.trim($('#name').val());
\t\tvar phone = $.trim($('#telephone').val());
\t\tvar email = $.trim($('#email').val());
\t\tvar location = $.trim($('#Location').val());

\t\tif (!name || name.length < 2) {
\t\t  alert('Please enter a valid name.');
\t\t  $('#name').focus();
\t\t  return false;
\t\t}

\t\tif (!/^[0-9]{10}$/.test(phone)) {
\t\t  alert('Please enter a valid 10-digit mobile number.');
\t\t  $('#telephone').focus();
\t\t  return false;
\t\t}

\t\tif (!/^[^\\s@]+@[^\\s@]+\\.[^\\s@]+$/.test(email)) {
\t\t  alert('Please enter a valid email address.');
\t\t  $('#email').focus();
\t\t  return false;
\t\t}

\t\tif (!location || location === 'Select Location') {
\t\t  alert('Please select a location.');
\t\t  $('#Location').focus();
\t\t  return false;
\t\t}

\t\treturn true;
\t  }

"""

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

for path in PATHS:
    if not path.exists():
        print("skip", path)
        continue
    text = path.read_text(encoding="utf-8")
    text = text.replace(
        'onsubmit="return handleLandingFormSubmit(event);"',
        'onsubmit="return validate();"',
    )
    text = text.replace('\n      <script src="js/landing-form-otp.js"></script>', "")
    text = text.replace('\n      <script src="../js/landing-form-otp.js"></script>', "")
    if "function validate()" not in text:
        text = text.replace(
            "\n\t  <script>\n\n\t  $(document).ready",
            "\n\t  <script>\n" + VALIDATE_FN + "\n\t  $(document).ready",
            1,
        )
        text = text.replace(
            "\n\t  <script>\n\t  $(document).ready",
            "\n\t  <script>\n" + VALIDATE_FN + "\n\t  $(document).ready",
            1,
        )
    path.write_text(text, encoding="utf-8")
    print("patched", path)

for js in [
    Path(r"c:\Time_kinds\time4kids\public\timekids-2g\js\landing-form-otp.js"),
    Path(r"c:\Time_kinds\time4kids\timekids-2g\js\landing-form-otp.js"),
    Path(r"c:\Time_kinds\timekids-2g\js\landing-form-otp.js"),
]:
    if js.exists():
        js.unlink()
        print("deleted", js)
