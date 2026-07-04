"""
test_mobile_pwa.py
Milestone 4 verification suite: confirms the license wall injection, PWA assets,
Capacitor mobile configuration, and the generated icon/splash matrix all reach a
0-error state. Pure file/JSON/image checks — no servers or native SDKs needed.

Run:
    pytest test_mobile_pwa.py
    # or directly:
    python3 test_mobile_pwa.py
"""

import glob
import json
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def _read(path):
    with open(os.path.join(ROOT, path)) as f:
        return f.read()


# ---------------------------------------------------------------------------
# 1. License wall injection
# ---------------------------------------------------------------------------
def test_app_py_injects_license_gate():
    app = _read("app.py")
    assert "from license_gate import enforce_license" in app
    assert "enforce_license()" in app


def test_license_gate_contract():
    gate = _read("license_gate.py")
    assert "st.session_state" in gate           # token stored in session_state
    assert "st.text_input" in gate              # paste-key input
    assert "st.link_button" in gate             # checkout redirects
    assert "/validate/" in gate                 # GET /validate/{token}
    assert "checkout/individual" in gate or "individual" in gate
    assert "enforce_license" in gate


# ---------------------------------------------------------------------------
# 2. PWA manifest
# ---------------------------------------------------------------------------
def test_manifest_is_valid_and_standalone():
    manifest = json.loads(_read("web/public/manifest.json"))
    assert manifest["display"] == "standalone", "manifest must hide the URL bar"
    for key in ("name", "short_name", "start_url", "scope", "theme_color", "background_color", "icons"):
        assert key in manifest, f"manifest missing {key}"
    assert manifest["background_color"] and manifest["theme_color"]
    sizes = {i["sizes"] for i in manifest["icons"]}
    assert "192x192" in sizes and "512x512" in sizes
    assert any(i.get("purpose") == "maskable" for i in manifest["icons"])


def test_index_html_wires_pwa():
    html = _read("web/public/index.html")
    assert 'rel="manifest"' in html and "manifest.json" in html
    assert 'name="theme-color"' in html
    assert "apple-touch-icon" in html
    assert os.path.exists(os.path.join(ROOT, "web/public/service-worker.js"))
    assert os.path.exists(os.path.join(ROOT, "web/public/app.js"))


# ---------------------------------------------------------------------------
# 3. Capacitor config
# ---------------------------------------------------------------------------
def test_capacitor_config_valid():
    cfg = json.loads(_read("mobile/capacitor.config.json"))
    assert cfg["appId"] and cfg["appName"]
    assert cfg["webDir"] == "www"
    assert os.path.exists(os.path.join(ROOT, "mobile", cfg["webDir"], "index.html"))


def test_capacitor_package_declared():
    pkg = json.loads(_read("mobile/package.json"))
    deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    assert "@capacitor/core" in deps
    assert "@capacitor/cli" in deps


def test_native_billing_hidden_in_wrapper():
    js = _read("mobile/www/app.js")
    assert "isNative" in js
    assert "native-hidden" in js  # billing block hidden on native
    assert "/checkout/" in js     # routes to web checkout


# ---------------------------------------------------------------------------
# 4. Icon / splash matrix
# ---------------------------------------------------------------------------
def test_base_icon_is_1024():
    from PIL import Image

    p = os.path.join(ROOT, "mobile", "resources", "icon.png")
    assert os.path.exists(p), "base 1024 icon.png missing"
    with Image.open(p) as im:
        assert im.size == (1024, 1024)


def test_asset_matrix_over_40():
    pngs = glob.glob(os.path.join(ROOT, "mobile", "**", "*.png"), recursive=True)
    pngs = [p for p in pngs if "node_modules" not in p]
    pngs += glob.glob(os.path.join(ROOT, "web", "public", "icons", "*.png"))
    assert len(pngs) >= 40, f"expected >=40 generated assets, found {len(pngs)}"


def test_ios_appicon_contents_references_exist():
    base = os.path.join(ROOT, "mobile/ios/App/App/Assets.xcassets/AppIcon.appiconset")
    contents = json.loads(_read(os.path.join(base, "Contents.json")))
    assert len(contents["images"]) >= 15
    for img in contents["images"]:
        fname = img.get("filename")
        assert fname, "every AppIcon entry needs a filename"
        assert os.path.exists(os.path.join(base, fname)), f"missing referenced icon {fname}"


def test_android_mipmaps_present():
    for density in ("mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"):
        p = os.path.join(ROOT, f"mobile/android/app/src/main/res/mipmap-{density}/ic_launcher.png")
        assert os.path.exists(p), f"missing android launcher for {density}"


# ---------------------------------------------------------------------------
# 5. Generator is importable/repeatable
# ---------------------------------------------------------------------------
def test_generator_importable():
    sys.path.insert(0, os.path.join(ROOT, "mobile"))
    import generate_assets

    assert hasattr(generate_assets, "main")
    assert callable(generate_assets.make_base_icon)


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failures = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except Exception as e:  # noqa: BLE001
            failures += 1
            import traceback

            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
    print(f"\n{len(tests) - failures}/{len(tests)} passed.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(_run_all())
