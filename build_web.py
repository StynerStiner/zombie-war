#!/usr/bin/env python3
"""
build_web.py
============
Builds the browser (WebAssembly) version of Zombie War with pygbag, ready to
upload to a static host such as Vercel.

    python3 -m pip install pygbag
    python3 build_web.py

What it does
------------
1. Copies the game's Python files into a clean staging folder (`web_build/`),
   so the huge `.venv/`, `__pycache__/` and the docs never end up inside the
   downloadable web bundle.
2. Runs pygbag, which compiles the game to WebAssembly (Pyodide).
3. Leaves a ready-to-deploy static site in `web_build/build/web/`.

The desktop game is not modified in any way by this script.
"""

import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
# The staging folder's name becomes the bundle name (zombiewar.apk), so it is
# named deliberately rather than something like "web_build".
STAGE = os.path.join(HERE, "web_build", "zombiewar")
OUTPUT = os.path.join(STAGE, "build", "web")
DEPLOY = os.path.join(HERE, "zombie-war-web")   # ready-to-upload static site

# Files that live next to main.py but must NOT go into the web bundle.
EXCLUDE = {"build_web.py"}
EXTRA_FILES = ["scores.json"]


def game_files():
    """
    Every .py file in the project except this build script, plus scores.json.

    This is discovered rather than hard-coded on purpose: a forgotten module
    does not just go missing, it makes pygbag think the import is a package on
    PyPI, and the game dies at boot with a 404 on every device.
    """
    py = sorted(f for f in os.listdir(HERE)
                if f.endswith(".py") and f not in EXCLUDE
                and os.path.isfile(os.path.join(HERE, f)))
    if "main.py" not in py:
        raise SystemExit("Cannot build: main.py not found in {}".format(HERE))
    return py + [f for f in EXTRA_FILES if os.path.isfile(os.path.join(HERE, f))]

APP_NAME = "zombiewar"
TITLE = "Zombie War - built by William"


def stage():
    """Copy a clean copy of the game into web_build/."""
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(STAGE)

    names = game_files()
    for name in names:
        shutil.copy2(os.path.join(HERE, name), os.path.join(STAGE, name))

    # assets/ is optional; copy it if the player added their own art or audio.
    assets_src = os.path.join(HERE, "assets")
    if os.path.isdir(assets_src):
        shutil.copytree(assets_src, os.path.join(STAGE, "assets"),
                        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    print("staged {} files into {}: {}".format(len(names), STAGE, ", ".join(names)))


# Without this, dragging your thumb across the canvas scrolls or zooms the page
# instead of moving the player, and a double-tap zooms in. Phones and tablets
# are unplayable without it.
MOBILE_CSS = """
<style id="zombiewar-mobile">
  /* pygbag sets body background to grey with an inline style, which beats a
     normal rule - !important is what actually wins, otherwise the page shows
     big light-grey bars around the game. */
  html, body {
      margin:0 !important; padding:0 !important; height:100% !important;
      overflow:hidden !important; overscroll-behavior:none;
      background:#0b1310 !important;
      background-image:radial-gradient(circle at 50% 40%, #16261d 0%, #070d0a 75%) !important;
  }
  html, body, canvas, #canvas, #canvas3d, #screen {
      touch-action: none;                 /* we handle all touch ourselves */
      -ms-touch-action: none;
      user-select: none; -webkit-user-select: none;
      -webkit-touch-callout: none;
      -webkit-tap-highlight-color: transparent;
  }
  canvas, #canvas { background:#0b1310 !important; }

  /* pygbag's loading box is bright blue text on a green block by default.
     Restyle it into the game's own loading screen. */
  #infobox {
      background:rgba(9,18,13,.95) !important;
      color:#8fe6a4 !important;
      border:2px solid #2f6b45 !important;
      border-radius:14px !important;
      padding:20px 30px 18px !important;
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif !important;
      font-weight:600 !important; font-size:13px !important;
      letter-spacing:.5px; text-align:center !important;
      box-shadow:0 14px 50px rgba(0,0,0,.65) !important;
      min-width:260px;
  }
  #infobox::before {
      content:"ZOMBIE WAR";
      display:block; color:#e8503f; font-size:28px; font-weight:800;
      letter-spacing:4px; margin-bottom:4px;
      text-shadow:0 3px 0 #3a0f0b;
  }
  #infobox::after {
      content:"built by William";
      display:block; color:#7d9c88; font-size:11px; font-weight:400;
      margin-top:8px; letter-spacing:1px;
  }
  #status { color:#7d9c88 !important; font-family:inherit !important; }

  /* Landscape-only: the arena is 16:9, so portrait squeezes it into an
     unreadable strip. Ask for a rotate instead of showing that. */
  #zw-rotate {
      display:none; position:fixed; inset:0; z-index:99999;
      background:#0b1310; color:#cfe6d6; text-align:center;
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
      flex-direction:column; align-items:center; justify-content:center; gap:18px;
      padding:24px;
  }
  #zw-rotate .zw-phone {
      width:74px; height:120px; border:4px solid #78e68c; border-radius:12px;
      animation: zw-tilt 1.8s ease-in-out infinite;
  }
  #zw-rotate h2 { margin:0; font-size:22px; color:#78e68c; letter-spacing:1px; }
  #zw-rotate p  { margin:0; font-size:15px; opacity:.85; max-width:420px; }
  @keyframes zw-tilt {
      0%,40%   { transform: rotate(0deg); }
      60%,100% { transform: rotate(-90deg); }
  }
  @media (orientation: portrait) and (max-width: 900px) {
      #zw-rotate { display:flex; }
  }
</style>
"""

ROTATE_OVERLAY = """
<div id="zw-rotate">
  <div class="zw-phone"></div>
  <h2>ROTATE YOUR DEVICE</h2>
  <p>Zombie War is played in landscape. Turn your phone or tablet sideways to
     get the full rainforest and the touch controls.</p>
</div>
"""

MOBILE_VIEWPORT = ('<meta name="viewport" content="width=device-width, '
                   'initial-scale=1.0, maximum-scale=1.0, user-scalable=no, '
                   'viewport-fit=cover">')

# A couple of runtime URLs (the package index and the pygame wheel) are built
# inside pygbag's own packed filesystem, so rewriting index.html cannot reach
# them.  This shim redirects them to our mirror at the network layer instead.
# It is inlined in <head>, and pygbag's loader is async/defer, so it is always
# installed before the first runtime fetch happens.
CDN_REWRITE_JS = """
<script id="zw-cdn-rewrite">
(function () {
  var FROM = "https://pygame-web.github.io/cdn/";
  var TO = "/cdn/";
  function fix(url) {
    return (typeof url === "string" && url.indexOf(FROM) === 0)
      ? TO + url.slice(FROM.length) : url;
  }
  var origFetch = window.fetch;
  if (origFetch) {
    window.fetch = function (input, init) {
      try {
        if (typeof input === "string") {
          input = fix(input);
        } else if (input && typeof input.url === "string") {
          var fixed = fix(input.url);
          if (fixed !== input.url) { input = new Request(fixed, input); }
        }
      } catch (e) { /* fall through with the original request */ }
      return origFetch.call(this, input, init);
    };
  }
  var origOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function (method, url) {
    try { arguments[1] = fix(url); } catch (e) { /* ignore */ }
    return origOpen.apply(this, arguments);
  };
})();
</script>
"""


# ---------------------------------------------------------------------------
# Self-hosting the Python runtime
# ---------------------------------------------------------------------------
# pygbag loads ~21 MB of CPython + pygame WebAssembly from pygame-web.github.io,
# and that CDN sends "cache-control: max-age=600" - so a browser re-downloads
# all of it ten minutes later. On a phone that is the entire loading time.
#
# We mirror those files into the deployment instead and serve them with a
# one-year immutable cache (see vercel.json), so the runtime downloads once and
# every later visit starts almost instantly.
#
# The list is not guesswork: it is every pygame-web URL the game actually
# requests during a full boot, captured from a real browser session.
CDN_ORIGIN = "https://pygame-web.github.io/cdn/"
CDN_LOCAL_PREFIX = "/cdn/"
CDN_FILES = [
    "0.9.3/pythons.js",
    "0.9.3/cpythonrc.py",
    "0.9.3/empty.html",
    "0.9.3/empty.ogg",
    "0.9.3/cpython312/main.js",
    "0.9.3/cpython312/main.data",
    "0.9.3/cpython312/main.wasm",
    "cp312/pygame_ce-2.5.7-cp312-cp312-wasm32_bi_emscripten.whl",
    "index-0.9.3-cp312.json",
    "vtx.js",
    "vt/xterm.js",
    "vt/xterm.css",
    "vt/xterm-addon-image.js",
]
# Registered as a service worker; harmless if the CDN ever drops it.
# browserfs 404s on the public CDN as well (that is the harmless
# "BrowserFS not found" console message), so it is optional here too.
CDN_OPTIONAL = ["0.9.3/pygbag0.9.3.js", "0.9.3/favicon.png",
                "0.9.3/browserfs.min.js"]

CDN_CACHE = os.path.join(HERE, "web_build", "cdn-cache")


def mirror_cdn(output_dir):
    """Copy the pygbag runtime into <output>/cdn/ so we can cache it ourselves."""
    import urllib.request

    os.makedirs(CDN_CACHE, exist_ok=True)
    total = 0
    for rel in CDN_FILES + CDN_OPTIONAL:
        optional = rel in CDN_OPTIONAL
        cached = os.path.join(CDN_CACHE, rel.replace("/", "__"))
        target = os.path.join(output_dir, "cdn", *rel.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)

        if not os.path.isfile(cached) or os.path.getsize(cached) == 0:
            url = CDN_ORIGIN + rel
            try:
                with urllib.request.urlopen(url, timeout=120) as response:
                    data = response.read()
                if not data:
                    raise ValueError("empty response")
                with open(cached, "wb") as fh:
                    fh.write(data)
            except Exception as exc:
                if optional:
                    print("   (skipped optional {}: {})".format(rel, exc))
                    continue
                raise SystemExit(
                    "Could not mirror {} ({}). The game would still work from the\n"
                    "public CDN, but loading would stay slow. Re-run the build, or\n"
                    "remove it from CDN_FILES to fall back.".format(url, exc))

        shutil.copy2(cached, target)
        total += os.path.getsize(target)

    # The package manifest points at the CDN for wheels; repoint it at us.
    manifest = os.path.join(output_dir, "cdn", "index-0.9.3-cp312.json")
    if os.path.isfile(manifest):
        try:
            with open(manifest, "r", encoding="utf-8") as fh:
                text = fh.read()
            text = text.replace(CDN_ORIGIN, CDN_LOCAL_PREFIX)
            with open(manifest, "w", encoding="utf-8") as fh:
                fh.write(text)
        except OSError as exc:
            print("   (could not repoint the package manifest: {})".format(exc))

    print("mirrored the Python runtime: {} files, {:.1f} MB (cached in {})".format(
        len(CDN_FILES) + len(CDN_OPTIONAL), total / 1024.0 / 1024.0, CDN_CACHE))


def patch_index_for_mobile(index_path):
    """Add a mobile viewport + touch-action CSS to pygbag's generated page."""
    try:
        with open(index_path, "r", encoding="utf-8") as fh:
            html = fh.read()
    except OSError as exc:
        print("warning: could not read index.html ({}), skipping mobile patch".format(exc))
        return

    if "zombiewar-mobile" in html:
        return                                    # already patched

    # Load the Python runtime from our own /cdn/ mirror instead of
    # pygame-web.github.io (see mirror_cdn).
    html = html.replace(CDN_ORIGIN, CDN_LOCAL_PREFIX)

    injection = CDN_REWRITE_JS + MOBILE_CSS
    if "name=\"viewport\"" not in html and "name='viewport'" not in html:
        injection = MOBILE_VIEWPORT + injection

    if "</head>" in html:
        html = html.replace("</head>", injection + "</head>", 1)
    else:                                         # very unusual, but be safe
        html = injection + html

    # The rotate prompt lives at the end of <body> so it paints over everything.
    if "zw-rotate" not in html.split("</head>", 1)[-1]:
        if "</body>" in html:
            html = html.replace("</body>", ROTATE_OVERLAY + "</body>", 1)
        else:
            html = html + ROTATE_OVERLAY

    try:
        with open(index_path, "w", encoding="utf-8") as fh:
            fh.write(html)
        print("patched index.html for phones and tablets (touch-action, viewport)")
    except OSError as exc:
        print("warning: could not write index.html ({})".format(exc))


def build():
    """Run pygbag over the staging folder."""
    cmd = [
        sys.executable, "-m", "pygbag",
        "--build",                 # build only, do not start pygbag's test server
        "--width", "1280",
        "--height", "720",
        "--app_name", APP_NAME,
        "--title", TITLE,
        STAGE,
    ]
    print("running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=HERE)
    if result.returncode != 0:
        raise SystemExit("pygbag failed with exit code {}".format(result.returncode))

    if not os.path.isfile(os.path.join(OUTPUT, "index.html")):
        raise SystemExit("pygbag finished but {}/index.html is missing".format(OUTPUT))

    mirror_cdn(OUTPUT)
    patch_index_for_mobile(os.path.join(OUTPUT, "index.html"))

    total = 0
    print("\nbuild output ({}):".format(OUTPUT))
    for name in sorted(os.listdir(OUTPUT)):
        path = os.path.join(OUTPUT, name)
        size = os.path.getsize(path) if os.path.isfile(path) else 0
        total += size
        print("   {:<28} {:>10,} bytes".format(name, size))
    print("   {:<28} {:>10,} bytes total".format("", total))
    # Copy the finished site to a clearly named folder for uploading.
    if os.path.isdir(DEPLOY):
        shutil.rmtree(DEPLOY)
    shutil.copytree(OUTPUT, DEPLOY)
    print("\nReady to deploy:  {}".format(DEPLOY))
    print("   cd {} && vercel deploy --prod".format(os.path.basename(DEPLOY)))


if __name__ == "__main__":
    stage()
    build()
