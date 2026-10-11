# Antigravity & Gemini Autonomous Code-Injecting Agent

A self-contained, single-file desktop automation agent powered by Python, the Google Antigravity Agent runtime, and Gemini models. The tool accepts coding prompts, produces clean, executable source code, and types it character-by-character into any web-based code editor using realistic, randomized human typing cadence.

This directly addresses platforms (such as assessment portals, online IDEs, and coding test environments) that intercept `onpaste` events, block the clipboard (`Ctrl+V`), or penalize instant bulk text injection.

---

## 1. Project Specifications

| Attribute | Details |
| :--- | :--- |
| **Language** | Python 3.10+ |
| **Primary Model** | `gemini-2.5-flash` |
| **API Provider** | Google AI Studio (`google-genai` / Google Antigravity Agent framework) |
| **GUI Framework** | Tkinter & TTK (Standard Library) |
| **Input Driver** | `pynput` (OS-level hardware virtual key driver) |
| **File Structure** | All-in-one single execution file (`app.py`) |
| **Supported OS** | Windows 10/11, macOS, Linux (X11 / XWayland) |

---

## 2. Technical Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Tkinter GUI)                          │
│  - Problem Statement / Task Prompt multi-line input box                │
│  - Programming Language Picker (Python, C++, Java, JS, Rust, Go, SQL)  │
│  - Switch Delay Timer (2s to 30s)                                      │
│  - Real-Time Execution Console & Code Stream Preview                   │
│  - Non-blocking asynchronous worker thread orchestration               │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Asynchronous Thread Dispatch)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                 BACKEND ENGINE (Gemini / Antigravity)                  │
│  - SDK Autoloader: Google Antigravity Agent + `google-genai`           │
│  - Zero-Markdown Strict Constraint Pipeline                            │
│  - Sanitizer: Strips accidental ``` code blocks & commentary           │
│  - Low Temperature (0.1) for deterministic, optimal code generation    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ (Sanitized Code String)
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│               KEYSTROKE INJECTION ENGINE (Pynput Driver)               │
│  - True low-level virtual key events (keydown / keypress / keyup)      │
│  - Bypasses browser JavaScript `onpaste` / clipboard interception      │
│  - Smart Auto-Indent Compensator (prevents double indentation on Enter)│
│  - Human Cadence Jitter Engine (variable character & syntax delays)    │
│  - Global Non-Blocking OS Kill Switch Hook (F8 / Esc)                  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Capabilities & Mechanics

### Anti-Paste & Clipboard Block Bypass
Web platforms often attach event listeners (`e.preventDefault()`, `window.addEventListener('paste', ...)`) to text areas and Monaco/Ace editors to detect or reject clipboard operations. Because this agent uses `pynput.keyboard.Controller`, the operating system issues genuine hardware interrupt signals that the browser registers as manual keyboard typing, bypassing clipboard-based detection.

### Auto-Indent Drift Compensation
Online editors automatically indent code to the expected indentation level when `Enter` is hit. If an automated script re-types the leading spaces on the new line, code blocks drift rightward (leading to syntax errors in indentation-sensitive languages like Python). The agent preserves whitespace on line 0, but automatically applies `.lstrip()` to subsequent lines before typing.

### Human Typing Simulation
Instead of outputting text at an inhuman constant rate, the keystroke engine injects:
* **Character-level jitter:** Random delays between `0.02s` and `0.05s` (~45–80 WPM).
* **Syntax-boundary hesitation:** Slightly longer pauses (`0.04s` to `0.08s`) after punctuation and structural tokens (` `, `,`, `;`, `{`, `}`, `(`, `)`, `:`, `[`, `]`, `=`).
* **Line-break thinking pauses:** Pauses between `0.12s` and `0.26s` before starting a new line to emulate a developer reviewing structure.

### Emergency Kill Switch
A background daemon listener runs globally across the operating system. If you switch to the wrong window or need to cancel typing immediately, pressing **`F8`** or **`Esc`** breaks the typing loop instantly without terminating the GUI.

---

## 4. Complete Application Code (`app.py`)

Save the entire code block below as `app.py`:

```python
import os
import sys
import time
import random
import threading
import subprocess

# ---------------------------------------------------------------------------
# 1. DEPENDENCY BOOTSTRAPPER
# ---------------------------------------------------------------------------
REQUIRED_PACKAGES = {
    "pynput": "pynput>=1.7.6",
    "google.genai": "google-genai>=0.1.0"
}

def bootstrap_dependencies():
    for module_name, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(module_name)
        except ImportError:
            print(f"[*] Missing package '{pip_name}'. Installing automatically...")
            subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name])

bootstrap_dependencies()

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
from pynput import keyboard
from pynput.keyboard import Controller, Key
from google import genai

HAS_ANTIGRAVITY = False
try:
    from google.antigravity import Agent, LocalAgentConfig
    HAS_ANTIGRAVITY = True
except ImportError:
    HAS_ANTIGRAVITY = False

# ---------------------------------------------------------------------------
# 2. BACKEND ENGINE (GEMINI / ANTIGRAVITY)
# ---------------------------------------------------------------------------
class AntigravityBackend:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.client = None
        if self.api_key:
            self._initialize_client()

    def _initialize_client(self):
        self.client = genai.Client(api_key=self.api_key)

    def generate_code(self, prompt: str, language: str) -> str:
        if not self.api_key:
            self.api_key = os.environ.get("GEMINI_API_KEY", "").strip()
            if not self.api_key:
                raise ValueError("GEMINI_API_KEY environment variable is not set.")
            self._initialize_client()

        system_instruction = (
            f"You are an expert autonomous software engineer specialized in {language}. "
            "Write optimal, correct, production-grade code that completely solves the problem. "
            "STRICT CONSTRAINTS:\n"
            "1. Output ONLY executable code.\n"
            "2. NEVER use markdown code fences (no ``` or ```{language}).\n"
            "3. NO explanations, thoughts, comments about the prompt, or conversational notes.\n"
            "4. Start directly with imports/functions on line 1."
        )

        response = self.client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={
                "system_instruction": system_instruction,
                "temperature": 0.1,
            }
        )
        code = response.text.strip()

        # Sanitize accidental markdown wrappers
        if code.startswith("```"):
            lines = code.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            code = "\n".join(lines).strip()

        return code

# ---------------------------------------------------------------------------
# 3. FRONTEND UI & KEYSTROKE INJECTOR
# ---------------------------------------------------------------------------
class AutoCoderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Antigravity / Gemini Human-Cadence Auto-Coder")
        self.root.geometry("640x740")
        self.root.minsize(520, 600)
        self.root.configure(bg="#181825")

        self.backend = AntigravityBackend()
        self.keyboard = Controller()

        self.is_typing = False
        self.stop_typing = False

        self._init_theme()
        self._build_ui()
        self._start_emergency_listener()

    def _init_theme(self):
        self.style = ttk.Style()
        self.style.theme_use("clam")

        self.colors = {
            "bg": "#181825",
            "surface": "#1e1e2e",
            "card": "#313244",
            "text": "#cdd6f4",
            "subtext": "#a6adc8",
            "accent": "#89b4fa",
            "green": "#a6e3a1",
            "red": "#f38ba8"
        }

        self.style.configure(".", background=self.colors["bg"], foreground=self.colors["text"])
        self.style.configure("TLabel", background=self.colors["bg"], foreground=self.colors["text"], font=("Segoe UI", 10))
        self.style.configure("Header.TLabel", font=("Segoe UI", 15, "bold"), foreground=self.colors["accent"])
        self.style.configure("Muted.TLabel", foreground=self.colors["subtext"], font=("Segoe UI", 9))
        self.style.configure("TCombobox", fieldbackground=self.colors["card"], background=self.colors["card"], foreground=self.colors["text"])

    def _build_ui(self):
        container = tk.Frame(self.root, bg=self.colors["bg"], padx=18, pady=18)
        container.pack(fill=tk.BOTH, expand=True)

        title_text = "🚀 Antigravity Agent + Gemini Engine" if HAS_ANTIGRAVITY else "🚀 Gemini Native Engine"
        title = ttk.Label(container, text=title_text, style="Header.TLabel")
        title.pack(anchor="w")

        subtitle = ttk.Label(
            container,
            text="Autonomous human-cadence code injector. Bypasses online paste blockers.",
            style="Muted.TLabel"
        )
        subtitle.pack(anchor="w", pady=(2, 12))

        ttk.Label(container, text="Problem Instructions / Prompt:").pack(anchor="w", pady=(0, 4))
        self.prompt_entry = scrolledtext.ScrolledText(
            container,
            height=7,
            wrap=tk.WORD,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            insertbackground="white",
            font=("Consolas", 10),
            relief="flat",
            padx=10,
            pady=8
        )
        self.prompt_entry.pack(fill=tk.X, pady=(0, 10))

        settings_frame = tk.Frame(container, bg=self.colors["bg"])
        settings_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(settings_frame, text="Language:").pack(side=tk.LEFT, padx=(0, 6))
        self.lang_var = tk.StringVar(value="python")
        self.lang_dropdown = ttk.Combobox(
            settings_frame,
            textvariable=self.lang_var,
            values=["python", "cpp", "java", "javascript", "c", "sql", "rust", "go"],
            width=11,
            state="readonly"
        )
        self.lang_dropdown.pack(side=tk.LEFT, padx=(0, 18))

        ttk.Label(settings_frame, text="Switch Delay (s):").pack(side=tk.LEFT, padx=(0, 6))
        self.delay_var = tk.IntVar(value=5)
        self.delay_spin = tk.Spinbox(
            settings_frame,
            from_=2,
            to=30,
            textvariable=self.delay_var,
            width=4,
            bg=self.colors["surface"],
            fg=self.colors["text"],
            relief="flat"
        )
        self.delay_spin.pack(side=tk.LEFT)

        btn_frame = tk.Frame(container, bg=self.colors["bg"])
        btn_frame.pack(fill=tk.X, pady=(4, 12))

        self.start_btn = tk.Button(
            btn_frame,
            text="Generate & Auto-Type",
            command=self.start_generation,
            bg=self.colors["accent"],
            fg="#11111b",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            activebackground="#b4befe",
            cursor="hand2",
            padx=14,
            pady=7
        )
        self.start_btn.pack(side=tk.LEFT, padx=(0, 10))

        self.abort_btn = tk.Button(
            btn_frame,
            text="Emergency Stop (F8 / Esc)",
            command=self.abort_execution,
            bg=self.colors["red"],
            fg="#11111b",
            font=("Segoe UI", 10, "bold"),
            relief="flat",
            cursor="hand2",
            padx=14,
            pady=7
        )
        self.abort_btn.pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Status: Ready")
        self.status_bar = tk.Label(
            container,
            textvariable=self.status_var,
            bg=self.colors["surface"],
            fg=self.colors["accent"],
            anchor="w",
            font=("Consolas", 10),
            padx=10,
            pady=7
        )
        self.status_bar.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(container, text="Generated Solution (Direct Stream):").pack(anchor="w", pady=(0, 4))
        self.preview_box = scrolledtext.ScrolledText(
            container,
            height=12,
            wrap=tk.NONE,
            bg=self.colors["surface"],
            fg=self.colors["green"],
            insertbackground="white",
            font=("Consolas", 10),
            relief="flat",
            padx=10,
            pady=8
        )
        self.preview_box.pack(fill=tk.BOTH, expand=True)

    def _start_emergency_listener(self):
        def on_press(key):
            if key in (Key.f8, Key.esc):
                if self.is_typing:
                    self.abort_execution()

        listener = keyboard.Listener(on_press=on_press)
        listener.daemon = True
        listener.start()

    def update_status(self, text: str):
        self.status_var.set(f"Status: {text}")
        self.root.update_idletasks()

    def abort_execution(self):
        if self.is_typing:
            self.stop_typing = True
            self.update_status("EMERGENCY ABORT TRIGGERED (Stopped).")

    def start_generation(self):
        if self.is_typing:
            return

        prompt = self.prompt_entry.get("1.0", tk.END).strip()
        if not prompt:
            messagebox.showwarning("Notice", "Please enter a coding prompt.")
            return

        worker = threading.Thread(
            target=self._run_pipeline, 
            args=(prompt, self.lang_var.get()), 
            daemon=True
        )
        worker.start()

    def _run_pipeline(self, prompt: str, language: str):
        self.is_typing = True
        self.stop_typing = False
        self.start_btn.config(state="disabled")

        try:
            self.update_status("Contacting Gemini backend...")
            code = self.backend.generate_code(prompt, language)

            self.preview_box.delete("1.0", tk.END)
            self.preview_box.insert(tk.END, code)

            delay = self.delay_var.get()
            for rem in range(delay, 0, -1):
                if self.stop_typing:
                    break
                self.update_status(f"SWITCH TO YOUR BROWSER EDITOR! Typing in {rem}s...")
                time.sleep(1)

            if not self.stop_typing:
                self.update_status("TYPING IN PROGRESS... Hands off keyboard & mouse!")
                self._type_into_editor(code)

            if not self.stop_typing:
                self.update_status("Done! Code injected successfully.")

        except Exception as ex:
            self.update_status(f"Error: {str(ex)}")
            messagebox.showerror("Execution Error", str(ex))
        finally:
            self.is_typing = False
            self.stop_typing = False
            self.start_btn.config(state="normal")

    def _type_into_editor(self, code: str):
        lines = code.splitlines()
        total_lines = len(lines)

        for idx, line in enumerate(lines):
            if self.stop_typing:
                break

            text_to_type = line if idx == 0 else line.lstrip()
            time.sleep(random.uniform(0.12, 0.26))

            for char in text_to_type:
                if self.stop_typing:
                    break

                self.keyboard.type(char)

                if char in " ,.;(){}:[]=":
                    time.sleep(random.uniform(0.04, 0.08))
                else:
                    time.sleep(random.uniform(0.02, 0.05))

            if idx < total_lines - 1 and not self.stop_typing:
                self.keyboard.press(Key.enter)
                self.keyboard.release(Key.enter)

if __name__ == "__main__":
    app_window = tk.Tk()
    app = AutoCoderApp(app_window)
    app_window.mainloop()
```

---

## 5. Setup & Operational Guide

### 1. Environment Variable Setup
Before running the agent, export your API key obtained from [Google AI Studio](https://aistudio.google.com/):

```bash
# Windows Command Prompt
set GEMINI_API_KEY=your_actual_api_key_here

# Windows PowerShell
$env:GEMINI_API_KEY="your_actual_api_key_here"

# Linux / macOS / Git Bash
export GEMINI_API_KEY="your_actual_api_key_here"
```

### 2. Launch the Application
```bash
python app.py
```
*(The built-in bootstrapper automatically detects and installs any missing packages such as `pynput` and `google-genai`).*

### 3. Usage Workflow
1. **Enter Requirements:** Type or paste the coding question or task description into the top text box.
2. **Configure Parameters:** Pick the language (`python`, `cpp`, `java`, etc.) and set the window-switch countdown (default: 5 seconds).
3. **Execute:** Click **Generate & Auto-Type**.
4. **Focus Window:** During the countdown, click inside the target code box in your web browser.
5. **Auto-Typing:** The agent simulates manual typing until completion.
6. **Emergency Kill Switch:** Press **`F8`** or **`Esc`** at any moment to cancel immediately.

---

## 6. Permissions & Environment Requirements

* **macOS Accessibility Permissions:** Under `System Settings > Privacy & Security > Accessibility`, grant permission to your terminal emulator (Terminal, iTerm2, VS Code) so `pynput` can monitor keys and simulate keystrokes.
* **Linux Display Server:** Uses the X11 protocol. If using Wayland on Ubuntu/Fedora, ensure the application runs under XWayland or switch to an X11 session at login.

---

## 7. Disclaimer
This tool is created for accessibility assistance, developer productivity, and automation testing. Users must ensure compliance with institutional policies, terms of service, and testing integrity guidelines on platforms where this script is used.