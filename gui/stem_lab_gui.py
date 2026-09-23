#!/usr/bin/env python3

import os
import queue
import signal
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk


PRESETS = {
    "Fast 4 stems": "4stems",
    "Balanced 4 stems": "balanced",
    "Fine-tuned 4 stems": "maximum",
    "Vocals + instrumental": "vocals",
    "Six stems": "6stems",
    "Drum parts": "drum-parts",
    "Vocal de-reverb": "deverb",
}


class StemLab(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("808SGN Stem Lab")
        self.geometry("820x580")
        self.minsize(680, 480)

        self.repo_dir = Path(__file__).resolve().parent.parent
        self.wrapper = self.repo_dir / "scripts" / "stem-separate"

        self.process = None
        self.messages = queue.Queue()

        self.input_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.preset_var = tk.StringVar(value="Fast 4 stems")
        self.status_var = tk.StringVar(value="Ready")

        self.build_interface()
        self.after(100, self.read_messages)
        self.protocol("WM_DELETE_WINDOW", self.close_app)

    def build_interface(self):
        root = ttk.Frame(self, padding=18)
        root.pack(fill="both", expand=True)

        root.columnconfigure(1, weight=1)
        root.rowconfigure(6, weight=1)

        ttk.Label(
            root,
            text="808SGN Stem Lab",
            font=("", 20, "bold"),
        ).grid(
            row=0,
            column=0,
            columnspan=3,
            sticky="w",
            pady=(0, 18),
        )

        ttk.Label(root, text="Input audio").grid(
            row=1,
            column=0,
            sticky="w",
        )

        ttk.Entry(
            root,
            textvariable=self.input_var,
        ).grid(
            row=1,
            column=1,
            sticky="ew",
            padx=10,
        )

        ttk.Button(
            root,
            text="Browse…",
            command=self.choose_input,
        ).grid(
            row=1,
            column=2,
        )

        ttk.Label(
            root,
            text="Preset",
        ).grid(
            row=2,
            column=0,
            sticky="w",
            pady=12,
        )

        self.preset_box = ttk.Combobox(
            root,
            textvariable=self.preset_var,
            values=list(PRESETS),
            state="readonly",
        )
        self.preset_box.grid(
            row=2,
            column=1,
            sticky="ew",
            padx=10,
            pady=12,
        )
        self.preset_box.bind(
            "<<ComboboxSelected>>",
            self.update_output_for_preset,
        )

        ttk.Label(
            root,
            text="Output folder",
        ).grid(
            row=3,
            column=0,
            sticky="w",
        )

        ttk.Entry(
            root,
            textvariable=self.output_var,
        ).grid(
            row=3,
            column=1,
            sticky="ew",
            padx=10,
        )

        ttk.Button(
            root,
            text="Browse…",
            command=self.choose_output,
        ).grid(
            row=3,
            column=2,
        )

        controls = ttk.Frame(root)
        controls.grid(
            row=4,
            column=0,
            columnspan=3,
            sticky="ew",
            pady=18,
        )

        self.start_button = ttk.Button(
            controls,
            text="Start separation",
            command=self.start,
        )
        self.start_button.pack(side="left")

        self.cancel_button = ttk.Button(
            controls,
            text="Cancel",
            command=self.cancel,
            state="disabled",
        )
        self.cancel_button.pack(side="left", padx=8)

        ttk.Button(
            controls,
            text="Open output folder",
            command=self.open_output,
        ).pack(side="left")

        self.progress = ttk.Progressbar(
            root,
            mode="indeterminate",
        )
        self.progress.grid(
            row=5,
            column=0,
            columnspan=3,
            sticky="ew",
        )

        self.log = tk.Text(
            root,
            wrap="word",
            height=18,
            state="disabled",
        )
        self.log.grid(
            row=6,
            column=0,
            columnspan=3,
            sticky="nsew",
            pady=(10, 8),
        )

        ttk.Label(
            root,
            textvariable=self.status_var,
        ).grid(
            row=7,
            column=0,
            columnspan=3,
            sticky="w",
        )

    def update_output_for_preset(self, _event=None):
        input_text = self.input_var.get().strip()

        if not input_text:
            return

        preset = PRESETS[self.preset_var.get()]
        input_path = Path(input_text).expanduser()
        self.output_var.set(str(input_path.parent / preset))

    def choose_input(self):
        path = filedialog.askopenfilename(
            title="Choose audio",
            filetypes=[
                (
                    "Audio files",
                    "*.wav *.mp3 *.flac *.m4a *.ogg *.aiff *.aif",
                ),
                ("All files", "*"),
            ],
        )

        if path:
            self.input_var.set(path)
            self.update_output_for_preset()

    def choose_output(self):
        path = filedialog.askdirectory(
            title="Choose output folder",
        )

        if path:
            self.output_var.set(path)

    def append_log(self, text):
        self.log.configure(state="normal")
        self.log.insert("end", text)
        self.log.see("end")
        self.log.configure(state="disabled")

    def start(self):
        input_text = self.input_var.get().strip()
        output_text = self.output_var.get().strip()

        if not input_text:
            messagebox.showerror(
                "Input error",
                "Choose an input audio file.",
            )
            return

        input_path = Path(input_text).expanduser()

        if not input_path.is_file():
            messagebox.showerror(
                "Input error",
                "Choose a valid audio file.",
            )
            return

        if not output_text:
            self.update_output_for_preset()
            output_text = self.output_var.get().strip()

        output_path = Path(output_text).expanduser()

        if not self.wrapper.is_file():
            messagebox.showerror(
                "Backend error",
                f"stem-separate was not found:\n{self.wrapper}",
            )
            return

        if not os.access(self.wrapper, os.X_OK):
            messagebox.showerror(
                "Backend error",
                "stem-separate is not executable.\n\n"
                "Run:\nchmod +x scripts/stem-separate",
            )
            return

        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except OSError as error:
            messagebox.showerror(
                "Output error",
                f"Could not create the output folder:\n{error}",
            )
            return

        preset = PRESETS[self.preset_var.get()]

        command = [
            str(self.wrapper),
            preset,
            str(input_path),
            str(output_path),
        ]

        self.start_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.preset_box.configure(state="disabled")

        self.progress.configure(value=0)
        self.progress.start(12)

        self.status_var.set("Separating…")
        self.append_log(
            "\n$ "
            + " ".join(command)
            + "\n\n"
        )

        threading.Thread(
            target=self.run_process,
            args=(command,),
            daemon=True,
        ).start()

    def run_process(self, command):
        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )

            if self.process.stdout is not None:
                for line in self.process.stdout:
                    self.messages.put(("log", line))

            return_code = self.process.wait()
            self.messages.put(("finished", return_code))

        except Exception as error:
            self.messages.put(("error", str(error)))

    def cancel(self):
        if self.process and self.process.poll() is None:
            try:
                os.killpg(
                    os.getpgid(self.process.pid),
                    signal.SIGTERM,
                )
                self.status_var.set("Cancelling…")
            except ProcessLookupError:
                pass
            except OSError as error:
                self.append_log(
                    f"\nCould not cancel process: {error}\n"
                )

    def open_output(self):
        output_text = self.output_var.get().strip()

        if not output_text:
            messagebox.showinfo(
                "Output folder",
                "No output folder is selected.",
            )
            return

        path = Path(output_text).expanduser()

        if path.is_dir():
            try:
                subprocess.Popen(
                    ["xdg-open", str(path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
            except OSError as error:
                messagebox.showerror(
                    "Output folder",
                    f"Could not open the output folder:\n{error}",
                )
        else:
            messagebox.showinfo(
                "Output folder",
                "No output folder exists yet.",
            )

    def read_messages(self):
        try:
            while True:
                kind, value = self.messages.get_nowait()

                if kind == "log":
                    self.append_log(value)

                elif kind == "finished":
                    self.finish(value)

                elif kind == "error":
                    self.append_log(f"\nError: {value}\n")
                    self.finish(1)

        except queue.Empty:
            pass

        self.after(100, self.read_messages)

    def finish(self, return_code):
        self.process = None

        self.progress.stop()
        self.progress.configure(value=0)

        self.start_button.configure(state="normal")
        self.cancel_button.configure(state="disabled")
        self.preset_box.configure(state="readonly")

        if return_code == 0:
            self.status_var.set("Separation complete")
            self.append_log("\nSeparation complete.\n")

        elif return_code in (
            -signal.SIGTERM,
            128 + signal.SIGTERM,
        ):
            self.status_var.set("Cancelled")
            self.append_log("\nSeparation cancelled.\n")

        else:
            self.status_var.set(
                f"Failed with exit code {return_code}"
            )
            self.append_log(
                f"\nSeparation failed with exit code {return_code}.\n"
            )

    def close_app(self):
        if self.process and self.process.poll() is None:
            should_quit = messagebox.askyesno(
                "Quit",
                "Separation is running. Cancel it and quit?",
            )

            if not should_quit:
                return

            self.cancel()

        self.destroy()


if __name__ == "__main__":
    StemLab().mainloop()