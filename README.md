# Claptrap Desktop Controller

Claptrap Desktop Controller is an unofficial desktop app for the CL4P-TP robot included with *Borderlands: The Handsome Collection – Claptrap-in-a-Box Edition*. It was created after the original Claptrap phone apps were delisted, so owners can continue using their robots. Connect over the robot's Wi-Fi to drive it and view its camera.

## Run

Install Python 3 with Tkinter. To use the camera and microphone, install Pillow and `sounddevice` with `python -m pip install Pillow sounddevice`. On Debian or Raspberry Pi OS, also install `python3-tk`, `python3-pil`, `python3-pil.imagetk`, and `libportaudio2`.

Packaged archives for Windows, macOS, and Linux are produced by the build workflow. Extract the archive for your system, then open the app inside. Linux also needs a graphical desktop and Tk libraries.

From the repository root:

```sh
PYTHONPATH=src python -m claptrap_controller
```

Set the robot's switch to **2 / On** for the camera or **1 / Run** to drive it. Join the robot's Wi-Fi; its network name usually starts with `CL4P-TP`. Open the app, check the address (usually `192.168.10.123`), and select **Connect**. If Run mode shuts off, place the robot upright on a solid surface.

## Controls

- Hold **WASD** or the arrow keys to drive and turn. The on-screen arrows work with a pointer.
- Release a key or button to return that direction to neutral. Opposing directions cancel each other.
- Press **Space** to clear movement. Movement also clears when the window loses focus, status becomes stale, or you disconnect.
- Set movement strength from 1 to 31. Start low when checking physical direction on a robot.
- Press **F11** for fullscreen; **Esc** returns to windowed mode.
- Hold **T** or the **Hold to talk** button to speak through the robot. Release to stop. Start with the talk level at 40%; lower it if you hear feedback. Your computer may ask for microphone access.

The camera appears when you connect. The app follows the robot's camera stream and shows the newest frame it can display. If Pillow is missing or the stream fails, the video area shows a message. The battery reading is approximate and updates in 5% steps to keep it from jumping with every status message.

Contributor setup and packaged build instructions are in [docs/development.md](docs/development.md).

## Support

<a href="https://ko-fi.com/zuiko9"><img src="https://storage.ko-fi.com/cdn/brandasset/v2/support_me_on_kofi_blue.png" alt="Support me on Ko-fi" width="220"></a>

## License

This project is licensed under the [MIT License](LICENSE). The robot icon is from [Tabler Icons](https://github.com/tabler/tabler-icons/blob/main/icons/outline/robot.svg), also under MIT; see its [license notice](assets/TABLER-LICENSE).
