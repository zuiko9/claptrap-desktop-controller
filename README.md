# Claptrap Desktop Controller

Claptrap Desktop Controller is an unofficial desktop app for the CL4P-TP robot included with *Borderlands: The Handsome Collection – Claptrap-in-a-Box Edition*. It was created after the original Claptrap phone apps were delisted, so owners can continue using their robots. Connect over the robot's Wi-Fi to drive it and view its camera.

## Run

The app needs Python 3 and Tkinter. Camera display also needs Pillow. On Debian or Raspberry Pi OS, install `python3-tk`, `python3-pil`, and `python3-pil.imagetk`.

Packaged archives for Windows, macOS, and Linux are produced by the build workflow. Extract the archive for your system, then open the app inside. Linux also needs a graphical desktop and Tk libraries.

From the repository root:

```sh
PYTHONPATH=src python -m claptrap_controller
```

The window opens disconnected. Set the robot's switch to **2 / On** for camera access, or **1 / Run** to enable movement. Join its Wi-Fi (the `CL4P-TP...` network name varies between units), check the robot address, then select **Connect**. The default address is `192.168.10.123`; change it if your robot uses another address. Run mode may shut off if the robot is not upright on a solid surface.

## Controls

- Hold **WASD** or the arrow keys to drive and turn. The on-screen arrows work with a pointer.
- Release a key or button to return that direction to neutral. Opposing directions cancel each other.
- Press **Space** to clear movement. Movement also clears when the window loses focus, status becomes stale, or you disconnect.
- Set movement strength from 1 to 31. Start low when checking physical direction on a robot.
- Press **F11** for fullscreen; **Esc** returns to windowed mode.

The camera appears after connection when its stream is available. If Pillow is missing or the stream fails, the video area shows a message. Audio is not available in this build.

Contributor setup and packaged build instructions are in [docs/development.md](docs/development.md).

## Support

<a href="https://ko-fi.com/zuiko9"><img src="https://storage.ko-fi.com/cdn/brandasset/v2/support_me_on_kofi_blue.png" alt="Support me on Ko-fi" width="220"></a>

## License

This project is licensed under the [MIT License](LICENSE). The robot icon is from [Tabler Icons](https://github.com/tabler/tabler-icons/blob/main/icons/outline/robot.svg), also under MIT; see its [license notice](assets/TABLER-LICENSE).
