# Development

Use Python 3 with Tkinter. Install Pillow to display camera frames. On Debian or Raspberry Pi OS, install `python3-tk`, `python3-pil`, and `python3-pil.imagetk`.

From the repository root:

```sh
python -m unittest discover -s tests -v
PYTHONPATH=src python -m claptrap_controller --smoke-test
```

The smoke test opens the window for three seconds without connecting or saving settings. The offline tests cover protocol encoding, input resolution, and stream framing. They do not establish compatibility with a physical robot. Record hardware model, firmware, OS, architecture, and observed behavior for device validation.

## Packaged builds

Install build dependencies with `python -m pip install -r requirements-build.txt`, then run `python tools/build_package.py` on the target platform. The archive appears in `dist/packages/` and includes the app, icon, README, and license notices. PyInstaller builds are native to the host OS and CPU; the GitHub Actions workflow produces Windows x64, macOS Intel and Apple Silicon, and Linux x64 and ARM64 archives. The Linux ARM64 archive targets the CM4 uConsole running Debian Trixie, but still needs device testing. macOS builds are unsigned and unnotarized.
