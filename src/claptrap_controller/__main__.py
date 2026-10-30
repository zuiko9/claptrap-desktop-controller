"""Desktop app for connecting to and controlling a Claptrap robot."""

import argparse
import json
import os
from pathlib import Path
import sys
import time
import tkinter as tk
from tkinter import ttk

from .camera import Camera
from .control import Movement
from .transport import ControlClient

CONFIG_DIR = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
CONFIG_PATH = CONFIG_DIR / 'claptrap-controller' / 'settings.json'
DEFAULT_HOST = '192.168.10.123'
DEFAULT_STRENGTH = 6
UI_TICK_MS = 40
KEYS = {'w': 'up', 's': 'down', 'a': 'left', 'd': 'right',
        'Up': 'up', 'Down': 'down', 'Left': 'left', 'Right': 'right'}


def icon_path():
    base = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
    return base / 'assets' / 'app-icon.png'


def load_settings():
    try:
        settings = json.loads(CONFIG_PATH.read_text())
    except (OSError, ValueError):
        return {}
    return settings if isinstance(settings, dict) else {}


class App:
    def __init__(self, root, smoke=False):
        self.root = root
        self.smoke = smoke
        self.client = None
        self.camera = None
        self.movement = Movement()
        self.keys_down = set()
        self.pointer_down = set()
        self.release_jobs = {}
        self.frame_stamp = 0
        self.photo = None
        self.video_image_item = None
        self.video_message_item = None
        self.video_pause_item = None
        self.camera_paused = False
        self.camera_message = None
        self.last_tick = time.monotonic()
        self.fullscreen = False
        settings = load_settings()
        self.host = tk.StringVar(value=str(settings.get('host', DEFAULT_HOST)))
        strength = settings.get('strength', DEFAULT_STRENGTH)
        if type(strength) is not int or not 1 <= strength <= 31:
            strength = DEFAULT_STRENGTH
        self.strength = tk.IntVar(value=strength)
        self.status = tk.StringVar(value='Disconnected · join the robot Wi-Fi to connect')
        self.telemetry = tk.StringVar(value='Battery —    Wi-Fi —')
        self.configure_window()
        self.build_layout()
        self.bind_events()
        root.after(UI_TICK_MS, self.tick)

    def configure_window(self):
        root = self.root
        root.title('Claptrap Desktop Controller')
        root.geometry('1120x680')
        root.minsize(780, 500)
        root.configure(bg='#171d23')
        try:
            self.icon = tk.PhotoImage(file=str(icon_path()))
            root.iconphoto(True, self.icon)
        except tk.TclError:
            self.icon = None
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('.', font=('TkDefaultFont', 11), background='#242d35', foreground='#f1f5f7')
        style.configure('TButton', padding=8)
        style.configure('TEntry', fieldbackground='#fff', foreground='#171d23')

    def build_layout(self):
        root = self.root
        shell = ttk.Frame(root, padding=16)
        shell.pack(fill='both', expand=True)
        header = ttk.Frame(shell)
        header.pack(fill='x', pady=(0, 12))
        ttk.Label(header, text='CLAPTRAP DESKTOP CONTROLLER', font=('TkDefaultFont', 19, 'bold')).pack(side='left', padx=(0, 22))
        ttk.Label(header, text='Robot address').pack(side='left')
        self.address = ttk.Entry(header, textvariable=self.host, width=19)
        self.address.pack(side='left', padx=8)
        self.connect_button = ttk.Button(header, text='Connect', command=self.toggle_connection)
        self.connect_button.pack(side='left')
        ttk.Button(header, text='Fullscreen', command=self.toggle_fullscreen).pack(side='right')
        ttk.Label(shell, textvariable=self.status).pack(anchor='w', pady=(0, 10))
        body = ttk.Frame(shell)
        body.pack(fill='both', expand=True)
        self.video = tk.Canvas(body, bg='#10171d', highlightthickness=1,
                               highlightbackground='#51616d')
        self.video.pack(side='left', fill='both', expand=True, padx=(0, 16))
        self.video.bind('<Configure>', lambda event: self.render_video())
        panel = ttk.Frame(body, width=215)
        panel.pack(side='right', fill='y')
        ttk.Label(panel, text='MOVE', font=('TkDefaultFont', 15, 'bold')).pack(anchor='w')
        ttk.Label(panel, text='Hold a direction or use WASD / arrows.', wraplength=205).pack(anchor='w', pady=(4, 14))
        pad = ttk.Frame(panel)
        pad.pack(anchor='w')
        for text, direction, row, column in (('↑', 'up', 0, 1), ('←', 'left', 1, 0),
                                             ('↓', 'down', 1, 1), ('→', 'right', 1, 2)):
            button = ttk.Button(pad, text=text, width=4, takefocus=False)
            button.grid(row=row, column=column, padx=3, pady=3)
            button.bind('<ButtonPress-1>', lambda event, d=direction: self.pointer_press(d))
        ttk.Button(panel, text='Stop · Space', command=self.stop).pack(fill='x', pady=(18, 14))
        ttk.Label(panel, text='Movement strength (1–31)').pack(anchor='w')
        ttk.Spinbox(panel, from_=1, to=31, textvariable=self.strength, width=6).pack(anchor='w', pady=6)
        ttk.Separator(panel).pack(fill='x', pady=16)
        ttk.Label(panel, textvariable=self.telemetry, wraplength=205).pack(anchor='w')
        ttk.Label(shell, text='Release to stop · focus loss clears input · F11 fullscreen · Esc exits fullscreen',
                  font=('TkDefaultFont', 10)).pack(anchor='w', pady=(12, 0))

    def bind_events(self):
        root = self.root
        root.bind('<KeyPress>', self.key_press)
        root.bind('<KeyRelease>', self.key_release)
        root.bind_all('<ButtonRelease-1>', self.pointer_release)
        root.bind('<FocusOut>', lambda event: root.after_idle(self.check_focus))
        root.bind('<Unmap>', lambda event: self.stop() if event.widget == root else None)
        root.protocol('WM_DELETE_WINDOW', self.close)

    def save(self):
        if self.smoke:
            return
        try:
            CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = CONFIG_PATH.with_suffix('.tmp')
            settings = {
                'host': self.host.get().strip(),
                'strength': self.movement_strength(),
            }
            temporary_path.write_text(json.dumps(settings, indent=2) + '\n')
            temporary_path.replace(CONFIG_PATH)
        except OSError as exc:
            self.status.set(f'Could not save settings: {exc}')

    def movement_strength(self):
        try:
            return max(1, min(31, self.strength.get()))
        except (ValueError, tk.TclError):
            return DEFAULT_STRENGTH

    def editing(self):
        return isinstance(self.root.focus_get(), (ttk.Entry, ttk.Spinbox, tk.Entry))

    def clear_input(self):
        self.movement.clear()
        self.keys_down.clear()
        self.pointer_down.clear()
        for job in self.release_jobs.values():
            self.root.after_cancel(job)
        self.release_jobs.clear()

    def stop(self):
        self.clear_input()
        if self.client:
            self.client.neutral()

    def check_focus(self):
        if self.root.focus_displayof() is None or self.editing():
            self.stop()

    def update_input(self):
        keyboard_directions = {KEYS[key] for key in self.keys_down if key in KEYS}
        self.movement.held = keyboard_directions | self.pointer_down
        if self.client:
            self.client.update(*self.movement.axes(self.movement_strength()))

    def key_press(self, event):
        key = self.key_name(event)
        if key == 'F11':
            self.toggle_fullscreen()
            return 'break'
        if key == 'Escape' and self.fullscreen:
            self.toggle_fullscreen()
            return 'break'
        if key == 'space' and not self.editing():
            self.stop()
            return 'break'
        can_move = (self.client and self.client.has_fresh_status() and
                    not self.client.locked)
        if self.editing() or not can_move:
            return
        if key in self.release_jobs:
            self.root.after_cancel(self.release_jobs.pop(key))
        if key in KEYS:
            self.keys_down.add(key)
            self.update_input()
            return 'break'

    def key_release(self, event):
        key = self.key_name(event)
        if key in self.keys_down:
            if key in self.release_jobs:
                self.root.after_cancel(self.release_jobs.pop(key))
            self.release_jobs[key] = self.root.after(15, lambda: self.release_key(key))

    def release_key(self, key):
        self.release_jobs.pop(key, None)
        self.keys_down.discard(key)
        self.update_input()

    @staticmethod
    def key_name(event):
        """Normalize single-character keys while preserving names like F11."""
        return event.keysym.lower() if len(event.keysym) == 1 else event.keysym

    def pointer_press(self, direction):
        if self.client and self.client.has_fresh_status() and not self.client.locked:
            self.root.focus_set()
            self.pointer_down.add(direction)
            self.update_input()

    def pointer_release(self, event):
        if self.pointer_down:
            self.pointer_down.clear()
            self.update_input()

    def toggle_fullscreen(self):
        self.stop()
        self.fullscreen = not self.fullscreen
        self.root.attributes('-fullscreen', self.fullscreen)

    def toggle_connection(self):
        if self.client:
            self.disconnect()
            return
        host = self.host.get().strip()
        if not host or any(char in host for char in '/: \t\r\n'):
            self.status.set('Enter a robot IP address or hostname, without a port')
            return
        self.stop()
        self.client = ControlClient(host)
        self.client.start()
        self.camera = Camera(host)
        self.camera.start()
        self.render_video()
        self.address.configure(state='disabled')
        self.connect_button.configure(text='Disconnect')
        self.root.focus_set()
        self.save()

    def disconnect(self):
        self.stop()
        if self.client:
            self.client.close()
        if self.camera:
            self.camera.close()
        self.client = self.camera = None
        self.address.configure(state='normal')
        self.connect_button.configure(text='Connect')
        self.telemetry.set('Battery —    Wi-Fi —')
        self.status.set('Disconnected')
        self.frame_stamp = 0
        self.camera_paused = False
        self.render_video()

    def render_video(self):
        width, height = self.video.winfo_width(), self.video.winfo_height()
        if width < 10 or height < 10:
            return
        self.camera_message = self.camera.message if self.camera else None
        if self.camera and self.camera.frame is not None and self.draw_camera_frame(width, height):
            if self.video_message_item is not None:
                self.video.itemconfigure(self.video_message_item, state='hidden')
            return

        if self.video_image_item is not None:
            self.video.itemconfigure(self.video_image_item, state='hidden')
        if self.video_pause_item is not None:
            self.video.itemconfigure(self.video_pause_item, state='hidden')
        self.photo = None
        message = self.camera.message if self.camera else 'Camera appears here when connected'
        if self.video_message_item is None:
            self.video_message_item = self.video.create_text(
                width // 2, height // 2, text=message, fill='#e3edf2',
                width=max(100, width - 40), font=('TkDefaultFont', 14))
        else:
            self.video.coords(self.video_message_item, width // 2, height // 2)
            self.video.itemconfigure(self.video_message_item, text=message,
                                     width=max(100, width - 40), state='normal')

    def draw_camera_frame(self, width, height):
        try:
            from PIL import Image, ImageOps, ImageTk
        except ImportError:
            return False

        frame = self.camera.frame.copy()
        frame = ImageOps.contain(
            frame, (width, height), method=Image.Resampling.BILINEAR)
        photo = ImageTk.PhotoImage(frame)
        if self.video_image_item is None:
            self.video_image_item = self.video.create_image(
                width // 2, height // 2, image=photo)
        else:
            self.video.coords(self.video_image_item, width // 2, height // 2)
            self.video.itemconfigure(self.video_image_item, image=photo, state='normal')
        self.photo = photo
        if self.camera_paused:
            if self.video_pause_item is None:
                self.video_pause_item = self.video.create_text(
                    width // 2, 28, text='Camera paused', fill='#ffd36a')
            else:
                self.video.coords(self.video_pause_item, width // 2, 28)
                self.video.itemconfigure(self.video_pause_item, state='normal')
        elif self.video_pause_item is not None:
            self.video.itemconfigure(self.video_pause_item, state='hidden')
        return True

    def tick(self):
        now = time.monotonic()
        if now - self.last_tick > 0.75:
            self.stop()
        self.last_tick = now
        if self.client:
            client = self.client
            if client.locked or not client.has_fresh_status():
                self.clear_input()
                client.neutral()
                if client.has_fresh_status():
                    client.arm()
            client.update(*self.movement.axes(self.movement_strength()))
            status = client.message
            if client.connected and not client.has_fresh_status():
                status = 'Connected · waiting for fresh status · movement paused'
            self.status.set(status)
            if client.status:
                battery, wifi = client.status[2:4]
                battery_text = f'{battery}%' if battery <= 100 else 'unknown'
                self.telemetry.set(f'Battery {battery_text}    Wi-Fi {wifi}/6')
            camera_paused = bool(self.camera and self.camera.frame_time and
                                 now - self.camera.frame_time > 2)
            frame_stamp = self.camera.frame_time if self.camera else 0
            camera_message = self.camera.message if self.camera else None
            if (frame_stamp != self.frame_stamp or camera_paused != self.camera_paused or
                    camera_message != self.camera_message):
                self.frame_stamp = frame_stamp
                self.camera_paused = camera_paused
                self.render_video()
            if client.thread and not client.thread.is_alive():
                reason = client.message
                self.disconnect()
                self.status.set(reason)
        self.root.after(UI_TICK_MS, self.tick)

    def close(self):
        self.save()
        client = self.client
        self.disconnect()
        if client and client.thread:
            client.thread.join(timeout=0.6)
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description='Claptrap Desktop Controller')
    parser.add_argument('--smoke-test', action='store_true',
                        help='Open briefly without connecting or saving settings')
    args = parser.parse_args()
    root = tk.Tk()
    App(root, smoke=args.smoke_test)
    if args.smoke_test:
        root.after(3000, root.destroy)
    root.mainloop()


if __name__ == '__main__':
    main()
