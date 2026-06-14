"""SVG → PNG rasterization with graceful backend fallback.

Used by the chart-wheel pipeline (issue #39) to turn the vector wheel into a
PNG — both for standalone ``.png`` output and for the bitmap embedded into the
``.docx``/``.pdf`` reports (docx-js / LibreOffice embed raster reliably; SVG
support there is patchy).

Backends, tried in order:
  1. **Headless Chrome/Chromium** — honours everything, crisp at any scale.
  2. **LibreOffice** (``soffice``) — always present in the Claude.ai sandbox.

The wheel SVG draws all symbols as ``<path>`` outlines (no font dependency), so
either backend produces identical glyphs. Raises :class:`RasterizeError` only
when *no* backend is available.
"""
from __future__ import annotations

import math
import re
import shutil
import subprocess
import time
import tempfile
from pathlib import Path
from typing import Optional

if __package__ in (None, ""):
    import env  # type: ignore[import-not-found]
else:
    from . import env


class RasterizeError(RuntimeError):
    pass


# Common Chrome/Chromium locations when not on PATH (mirrors env.SOFFICE_FALLBACKS).
CHROME_FALLBACKS = (
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/opt/google/chrome/chrome",
)


def find_chrome() -> Optional[str]:
    for name in ("google-chrome", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    for cand in CHROME_FALLBACKS:
        if Path(cand).exists():
            return cand
    return None


def available_backend() -> Optional[str]:
    if find_chrome():
        return "chrome"
    if env.find_soffice():
        return "soffice"
    return None


def _svg_dims(svg: str, default: int = 1000) -> tuple[int, int]:
    """Read the ``width``/``height`` (px) from an SVG header; fall back to a
    square *default*. Used to size the headless-Chrome window to the SVG, which
    is no longer always square (the standalone wheel adds a legend strip)."""
    m = re.search(r'<svg[^>]*\bwidth="([\d.]+)"[^>]*\bheight="([\d.]+)"', svg)
    if m:
        return int(math.ceil(float(m.group(1)))), int(math.ceil(float(m.group(2))))
    return default, default


def svg_to_png(svg: str, *, scale: int = 2,
               chrome_bin: Optional[str] = None,
               soffice_bin: Optional[str] = None) -> bytes:
    """Rasterize an SVG string to PNG bytes.

    The window is sized to the SVG's own width/height; *scale* multiplies it
    (``scale=2`` → a ~2× PNG, crisp at print size). Returns PNG bytes.
    """
    w, h = _svg_dims(svg)
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        svg_path = td_path / "wheel.svg"
        svg_path.write_text(svg)
        png_path = td_path / "wheel.png"

        chrome = chrome_bin or find_chrome()
        if chrome:
            try:
                _chrome_render(chrome, svg_path, png_path, w, h, scale, td_path)
            except subprocess.TimeoutExpired:
                pass  # fall through to the LibreOffice backend
            if png_path.exists() and png_path.stat().st_size > 0:
                return png_path.read_bytes()

        soffice = soffice_bin or env.find_soffice()
        if soffice:
            produced = _soffice_render(soffice, svg_path, td_path)
            if produced.exists():
                return produced.read_bytes()

        raise RasterizeError(
            "No SVG rasterizer available. Install Chrome/Chromium or LibreOffice "
            "(soffice). The .svg itself was produced successfully — only PNG/PDF "
            "rasterization needs one of these."
        )


def svg_to_pdf(svg: str, chrome_bin: Optional[str] = None,
               soffice_bin: Optional[str] = None) -> bytes:
    """Rasterize an SVG string to a single-page PDF (Chrome print-to-pdf, then
    LibreOffice). Returns PDF bytes; raises :class:`RasterizeError` if neither
    backend is present."""
    with tempfile.TemporaryDirectory() as td:
        td_path = Path(td)
        svg_path = td_path / "wheel.svg"
        svg_path.write_text(svg)

        chrome = chrome_bin or find_chrome()
        if chrome:
            pdf_path = td_path / "wheel.pdf"
            _run_chrome_until(
                [chrome, "--headless=new", "--disable-gpu", "--no-pdf-header-footer",
                 "--no-first-run", "--no-default-browser-check",
                 f"--user-data-dir={td_path / 'profile'}",
                 f"--print-to-pdf={pdf_path}", svg_path.as_uri()],
                pdf_path,
            )
            if pdf_path.exists() and pdf_path.stat().st_size > 0:
                return pdf_path.read_bytes()

        soffice = soffice_bin or env.find_soffice()
        if soffice:
            subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf", "--outdir",
                 str(td_path), str(svg_path)],
                capture_output=True, text=True, check=False,
            )
            produced = td_path / "wheel.pdf"
            if produced.exists():
                return produced.read_bytes()

        raise RasterizeError(
            "No SVG→PDF backend available (need Chrome/Chromium or LibreOffice). "
            "Write a .svg or .png instead, or render the wheel inside a .pdf "
            "report via render_pdf.py."
        )


def _run_chrome_until(cmd: list[str], out_path: Path, timeout: float = 45.0) -> None:
    """Run headless Chrome and stop as soon as *out_path* is written.

    Modern headless Chrome writes the screenshot/PDF but often does not exit
    promptly, so we poll for the output and terminate the process ourselves
    rather than blocking on ``wait()`` (which would stall for the full timeout).
    """
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if proc.poll() is not None:
                break
            if out_path.exists() and out_path.stat().st_size > 0:
                time.sleep(0.3)  # let the write settle
                break
            time.sleep(0.2)
    finally:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def _chrome_render(chrome: str, svg_path: Path, png_path: Path,
                   w: int, h: int, scale: int, td_path: Path) -> None:
    # --headless=new is required on modern Chrome (the legacy --headless launches
    # a full UI). A throwaway --user-data-dir avoids locking the user's profile.
    _run_chrome_until(
        [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
         "--no-first-run", "--no-default-browser-check",
         f"--force-device-scale-factor={scale}",
         f"--window-size={w},{h}",
         f"--user-data-dir={td_path / 'profile'}",
         f"--screenshot={png_path}",
         svg_path.as_uri()],
        png_path,
    )


def _soffice_render(soffice: str, svg_path: Path, td_path: Path) -> Path:
    subprocess.run(
        [soffice, "--headless", "--convert-to", "png", "--outdir",
         str(td_path), str(svg_path)],
        capture_output=True, text=True, check=False,
    )
    return td_path / (svg_path.stem + ".png")
