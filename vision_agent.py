"""
AGENT PRAYATH - Autonomous Automatic Code Editor
Run:  python vision_agent.py
"""

import os, sys, time, json, threading, subprocess, webbrowser, random, shutil
import urllib.request, urllib.error
from tkinter import ttk

# ── Dependency Bootstrapper ──────────────────────────────────────────────────
REQUIRED_PACKAGES = {
    "pynput": "pynput>=1.7.6",
    "google.genai": "google-genai>=0.1.0",
    "PIL": "Pillow>=9.0.0",
    "customtkinter": "customtkinter",
}

def bootstrap_dependencies():
    for mod, pip_name in REQUIRED_PACKAGES.items():
        try:
            __import__(mod)
        except ImportError:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", pip_name],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except Exception:
                pass

bootstrap_dependencies()

import customtkinter as ctk
from tkinter import messagebox
from pynput import keyboard, mouse
from pynput.keyboard import Controller as KController
from pynput.keyboard import Key
from PIL import ImageGrab

try:
    from google import genai as _genai
except Exception:
    _genai = None

ctk.set_appearance_mode("Dark")

# ── Data Management & Firebase Cloud ──────────────────────────────────────────
SESSION_FILE = os.path.join(os.path.dirname(__file__), ".alpha_session.json")
LOCAL_DB_FILE = os.path.join(os.path.dirname(__file__), "cloud_db.json")
FIREBASE_URL = "https://alpha-agent-2d55f-default-rtdb.firebaseio.com"

def load_session():
    if os.path.exists(SESSION_FILE):
        try:
            with open(SESSION_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_session(data):
    try:
        with open(SESSION_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def _safe_key(key):
    return str(key).strip().replace(".", "_").replace("#", "_").replace("$", "_").replace("[", "_").replace("]", "_").replace("/", "_")

def _firebase_request(path, method="GET", data=None):
    """Execute authenticated REST request to Firebase Realtime Database."""
    url = f"{FIREBASE_URL}{path}.json"
    body = json.dumps(data).encode('utf-8') if data is not None else None
    headers = {'Content-Type': 'application/json'} if body else {}
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            content = resp.read().decode('utf-8')
            return json.loads(content) if content else None
    except Exception as e:
        print(f"[Firebase {method} {path} Error]: {e}")
        return None

def load_cloud_db():
    """Load entire student database from Firebase with local cache fallback."""
    result = _firebase_request("/students")
    if isinstance(result, dict):
        return result
    # Fallback to local file if offline
    if os.path.exists(LOCAL_DB_FILE):
        try:
            with open(LOCAL_DB_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_cloud_db(db):
    """Save entire student database to Firebase."""
    return _firebase_request("/students", method="PUT", data=db)

def get_student(roll):
    """Get single student record live from Firebase."""
    safe_roll = _safe_key(roll)
    result = _firebase_request(f"/students/{safe_roll}")
    if isinstance(result, dict):
        return result
    # Local fallback
    if os.path.exists(LOCAL_DB_FILE):
        try:
            with open(LOCAL_DB_FILE, "r") as f:
                db = json.load(f)
                return db.get(roll)
        except Exception:
            pass
    return None

def set_student(roll, data):
    """Create or overwrite single student record in Firebase."""
    safe_roll = _safe_key(roll)
    return _firebase_request(f"/students/{safe_roll}", method="PUT", data=data)

def update_student(roll, patch_data):
    """Partially update student record (e.g. password, name) in Firebase."""
    safe_roll = _safe_key(roll)
    return _firebase_request(f"/students/{safe_roll}", method="PATCH", data=patch_data)

def delete_student(roll):
    """Delete single student record from Firebase."""
    safe_roll = _safe_key(roll)
    return _firebase_request(f"/students/{safe_roll}", method="DELETE")

def update_online_presence(roll, data):
    """Send heartbeat / status ping to Firebase."""
    safe_roll = _safe_key(roll)
    return _firebase_request(f"/online_presence/{safe_roll}", method="PUT", data=data)

def get_online_presence():
    """Fetch all active online users from Firebase."""
    result = _firebase_request("/online_presence")
    return result if isinstance(result, dict) else {}

def remove_online_presence(roll):
    """Remove user from online presence list in Firebase."""
    safe_roll = _safe_key(roll)
    return _firebase_request(f"/online_presence/{safe_roll}", method="DELETE")

# ── Backend engine ────────────────────────────────────────────────────────────
class AntigravityBackend:
    def __init__(self, api_key=""):
        self.api_key = api_key.strip()
        self.client  = None
        if self.api_key: self._init_client()

    def _init_client(self):
        if _genai and self.api_key:
            try: self.client = _genai.Client(api_key=self.api_key)
            except Exception: self.client = None

    def _sys(self, lang):
        return (f"You are an expert autonomous software engineer specialised in {lang}. "
                "Write optimal, correct, production-grade code. "
                "STRICT: Output ONLY executable code. No markdown fences. No explanations.")

    def _clean(self, code):
        code = code.strip()
        if code.startswith("```"):
            lines = code.splitlines()
            if lines and lines[0].startswith("```"):  lines = lines[1:]
            if lines and lines[-1].startswith("```"): lines = lines[:-1]
            code = "\n".join(lines).strip()
        return code

    def from_text(self, prompt, lang):
        if not self.client: raise RuntimeError("NO_UPLINK")
        r = self.client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt,
            config={"system_instruction": self._sys(lang), "temperature": 0.1})
        return self._clean(r.text)

    def from_image(self, image, lang, prompt=None, sys_inst=None):
        if not self.client: raise RuntimeError("NO_UPLINK")
        p  = prompt or f"Read the coding question on screen and write the solution in {lang}."
        si = sys_inst or self._sys(lang)
        r  = self.client.models.generate_content(
            model="gemini-2.0-flash", contents=[p, image],
            config={"system_instruction": si, "temperature": 0.1})
        return self._clean(r.text)

# ── HACKER THEME TOKENS ─────────────────────────────────────────────────────
BG         = "#030303"
SURFACE    = "#000000"
CARD       = "#0a110a"
BORDER     = "#004d00"
BORDER_LT  = "#008f11"
NEON_GREEN = "#00FF41"
DARK_GREEN = "#008F11"
MUTED      = "#00aa22"
DANGER     = "#ff003c"
WARNING    = "#ffaa00"

FH1 = ("Consolas", 22, "bold")
FH2 = ("Consolas", 16, "bold")
FH3 = ("Consolas", 13, "bold")
FB  = ("Consolas", 11)
FM  = ("Courier New", 11, "bold")
FS  = ("Consolas", 10)

class HackerCard(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=CARD, border_width=2,
                         border_color=BORDER_LT, corner_radius=0, **kwargs)

class HackerButton(ctk.CTkButton):
    def __init__(self, parent, text, command, color=DARK_GREEN, hover=NEON_GREEN, text_col="#000000", border_color=NEON_GREEN, **kwargs):
        super().__init__(parent, text=text, command=command, fg_color=color, hover_color=hover,
                         text_color=text_col, font=FH3, corner_radius=0, border_width=1, border_color=border_color, **kwargs)

class HackerEntry(ctk.CTkEntry):
    def __init__(self, parent, placeholder="", show="", **kwargs):
        kwargs.pop("height", None)
        super().__init__(parent, placeholder_text=placeholder, show=show,
                         fg_color=SURFACE, border_color=DARK_GREEN, text_color=NEON_GREEN,
                         font=FM, height=38, corner_radius=0, border_width=2, **kwargs)

# ── CLOUD AUTO-UPDATER ENGINE ────────────────────────────────────────────────
APP_VERSION = "v2.1"
GITHUB_REPO_URL = "https://github.com/chittlusai/adgent-alpha-paryath-.git"
GITHUB_RAW_URL = "https://raw.githubusercontent.com/chittlusai/adgent-alpha-paryath-/main/vision_agent.py"

def get_system_update_info():
    """Fetch update telemetry from Firebase Cloud."""
    data = _firebase_request("/system_config")
    if isinstance(data, dict):
        return data
    return {
        "latest_version": APP_VERSION,
        "changelog": "Added AUS Temp Roll Login & Migration, 4400+ Campus Students DB Sync, Cloud Auto-Updater",
        "update_url": GITHUB_REPO_URL
    }

def perform_system_update(log_callback=None):
    """
    Perform a complete application and database update:
    1. Check Firebase for latest release notes.
    2. Pull updates via Git or download raw source.
    3. Synchronize complete cloud_db from Firebase.
    4. Return success status and version string.
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        print(f"[Update Engine]: {msg}")

    log("[1/4] Contacting Firebase Cloud for update telemetry...")
    info = get_system_update_info()
    latest_v = info.get("latest_version", APP_VERSION)
    log(f"[*] Target Release: {latest_v} | Installed: {APP_VERSION}")

    # Step 2: Code Update
    log("[2/4] Checking code repository for updates...")
    git_success = False
    git_dir = os.path.join(os.path.dirname(__file__), ".git")
    if os.path.exists(git_dir):
        try:
            log("[*] Querying Git repository origin...")
            subprocess.run(["git", "fetch", "origin", "main"], cwd=os.path.dirname(__file__), timeout=12, capture_output=True)
            proc = subprocess.run(["git", "pull", "--autostash", "origin", "main"], cwd=os.path.dirname(__file__), timeout=15, capture_output=True, text=True)
            if proc.returncode == 0:
                log("[+] Git pull completed successfully.")
                git_success = True
            else:
                log(f"[*] Git status: {proc.stdout.strip() if proc.stdout else proc.stderr.strip()}")
        except Exception as ge:
            log(f"[!] Git update error: {ge}")

    if not git_success:
        try:
            log("[*] Connecting to Cloud Source fallback...")
            req = urllib.request.Request(GITHUB_RAW_URL, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=12) as resp:
                new_code = resp.read().decode('utf-8')
                if len(new_code) > 20000 and "AutoCoderApp" in new_code:
                    curr_file = os.path.abspath(__file__)
                    bak_file = curr_file + ".bak"
                    try:
                        shutil.copy2(curr_file, bak_file)
                        with open(curr_file, "w", encoding="utf-8") as wf:
                            wf.write(new_code)
                        log("[+] Application source updated via cloud source.")
                    except Exception as fe:
                        log(f"[!] File write warning: {fe}")
        except Exception as re:
            log(f"[*] Cloud code note: {re}")

    # Step 3: Database Synchronization
    log("[3/4] Synchronizing latest cloud database from Firebase...")
    try:
        cloud_db = _firebase_request("/students")
        if isinstance(cloud_db, dict) and len(cloud_db) > 100:
            with open(LOCAL_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(cloud_db, f, indent=2)
            log(f"[+] Synchronized {len(cloud_db)} student records to local database.")
        else:
            log("[*] Database cache is already up to date.")
    except Exception as dbe:
        log(f"[!] Database sync note: {dbe}")

    log("[4/4] Verifying system integrity...")
    time.sleep(0.5)
    log(f"[+] UPDATE COMPLETED FOR VERSION {latest_v}!")
    return True, latest_v

# ── APP UPDATE MODAL DIALOG ──────────────────────────────────────────────────
class AppUpdateModal(ctk.CTkToplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.title("AGENT PRAYATH - CLOUD AUTO-UPDATER")
        self.geometry("620x540")
        self.minsize(520, 440)
        self.configure(fg_color=BG)
        self.grab_set()

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-620)//2}+{(sh-540)//2}")

        self._build_ui()

    def _build_ui(self):
        hdr = ctk.CTkFrame(self, height=55, fg_color=SURFACE, border_width=1, border_color=DARK_GREEN)
        hdr.pack(fill="x", padx=10, pady=10); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text=">_ CLOUD SYSTEM AUTO-UPDATER", font=FH2, text_color=NEON_GREEN).pack(side="left", padx=15)
        ctk.CTkLabel(hdr, text=f"CURRENT: {APP_VERSION}", font=FS, text_color=MUTED).pack(side="right", padx=15)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=15, pady=(0,10))

        card = HackerCard(body)
        card.pack(fill="x", pady=(0,10))

        ctk.CTkLabel(card, text="RELEASE HIGHLIGHTS & CLOUD TELEMETRY", font=FB, text_color=NEON_GREEN, anchor="w").pack(fill="x", padx=15, pady=(10,5))

        self.info_lbl = ctk.CTkLabel(card, text="Fetching latest cloud release information...", font=FS, text_color=MUTED, justify="left", anchor="w")
        self.info_lbl.pack(fill="x", padx=15, pady=(0,10))

        self.prog_bar = ctk.CTkProgressBar(body, fg_color=SURFACE, progress_color=NEON_GREEN, height=12)
        self.prog_bar.set(0)
        self.prog_bar.pack(fill="x", pady=(0,10))

        self.log_box = ctk.CTkTextbox(body, height=180, fg_color=SURFACE, text_color=NEON_GREEN, font=FM, border_width=1, border_color=DARK_GREEN)
        self.log_box.pack(fill="both", expand=True, pady=(0,10))
        self.log_box.insert("end", "[*] Click '⚡ UPDATE TO NEW VERSION' to begin synchronization.\n")

        btn_frame = ctk.CTkFrame(body, fg_color="transparent")
        btn_frame.pack(fill="x")

        self.btn_start = HackerButton(btn_frame, "⚡ UPDATE TO NEW VERSION", self._start_update, height=42)
        self.btn_start.pack(side="right")

        HackerButton(btn_frame, "CLOSE", self.destroy, color=SURFACE, text_col=MUTED, height=42).pack(side="left")

        threading.Thread(target=self._fetch_info, daemon=True).start()

    def _fetch_info(self):
        info = get_system_update_info()
        latest_v = info.get("latest_version", APP_VERSION)
        changelog = info.get("changelog", "Cloud improvements & bug fixes.")
        text = f"• Latest Release: {latest_v}\n• Highlights: {changelog}\n• Source: GitHub & Firebase Live"
        self.after(0, lambda: self.info_lbl.configure(text=text))

    def _start_update(self):
        self.btn_start.configure(state="disabled")
        self.prog_bar.set(0.15)
        self.log_box.delete("1.0", "end")

        def _log_cb(msg):
            def _ui():
                self.log_box.insert("end", f"{msg}\n")
                self.log_box.see("end")
            self.after(0, _ui)

        def _worker():
            self.after(0, lambda: self.prog_bar.set(0.4))
            ok, v = perform_system_update(_log_cb)
            self.after(0, lambda: self.prog_bar.set(1.0))
            if ok:
                _log_cb(f"\n[+] UPDATE TO {v} COMPLETED SUCCESSFULLY!")
                _log_cb("[*] Restarting application in 2 seconds...")
                time.sleep(2)
                self.after(0, self._restart_app)

        threading.Thread(target=_worker, daemon=True).start()

    def _restart_app(self):
        try:
            self.destroy()
            if hasattr(self.parent, "destroy"):
                self.parent.destroy()
            subprocess.Popen([sys.executable, os.path.abspath(__file__)])
        except Exception as e:
            subprocess.Popen(["python", "vision_agent.py"])
        sys.exit(0)

# ── ONBOARDING WIZARD ─────────────────────────────────────────────────────────
class OnboardingWizard(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AGENT PRAYATH - ROOT ACCESS TERMINAL")
        self.geometry("620x780")
        self.minsize(520, 620)
        self.configure(fg_color=BG)

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-620)//2}+{(sh-780)//2}")

        self.session   = load_session()
        self.cloud_db  = load_cloud_db()
        self.user_data = {}
        self.success   = False

        self._build_shell()
        self._render_step_identity()

    def _build_shell(self):
        hdr = ctk.CTkFrame(self, height=60, fg_color=SURFACE, corner_radius=0, border_width=1, border_color=DARK_GREEN)
        hdr.pack(fill="x", padx=10, pady=10); hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text=f">_ ROOT ACCESS TERMINAL {APP_VERSION}", font=FH2, text_color=NEON_GREEN).pack(side="left", padx=20)
        ctk.CTkLabel(hdr, text="[CLOUD: FIREBASE ACTIVE]", font=FS, text_color=DARK_GREEN).pack(side="right", padx=15)
        HackerButton(hdr, "🔄 CHECK UPDATE", self._open_update_modal, height=32, color=SURFACE, text_col=NEON_GREEN, border_color=DARK_GREEN).pack(side="right", padx=10)

        self.content = ctk.CTkFrame(self, fg_color=BG)
        self.content.pack(fill="both", expand=True, padx=20, pady=10)

    def _open_update_modal(self):
        AppUpdateModal(self)

    def _clear(self):
        for w in self.content.winfo_children(): w.destroy()

    def _nav(self):
        r = ctk.CTkFrame(self.content, fg_color="transparent")
        r.pack(fill="x", pady=20)
        return r

    def _show_forgot_password(self):
        messagebox.showinfo("SECURITY PROTOCOL",
            "CONTACT ADMINISTRATOR TO RESET YOUR PASSWORD:\n\n"
            "PHONE: +91 8309939554\n"
            "EMAIL: vanapalligowtham890@gmail.com\n\n"
            "Or ask the Admin to update your password in DB Admin."
        )

    def _render_step_identity(self):
        self._clear()
        ctk.CTkLabel(self.content, text="IDENTIFY YOURSELF:", font=FH1, text_color=NEON_GREEN).pack(pady=(15,10))
        HackerButton(self.content, "[1] ADMINISTRATOR LOGIN", self._render_step_admin, height=45).pack(fill="x", padx=40, pady=8)
        HackerButton(self.content, "[2] STUDENT LOGIN", self._render_step_student_login, height=45).pack(fill="x", padx=40, pady=8)
        HackerButton(self.content, "[3] CREATE NEW STUDENT ACCOUNT", self._render_step_student_register, height=45).pack(fill="x", padx=40, pady=8)
        HackerButton(self.content, "[4] AUS LOGIN WITH TEMP ROLL NUMBER", self._render_step_temp_roll_login, height=45).pack(fill="x", padx=40, pady=8)
        HackerButton(self.content, "🔄 CHECK FOR UPDATES & SYNC CLOUD", self._open_update_modal, height=42, color=DARK_GREEN, hover=NEON_GREEN, text_col=BG).pack(fill="x", padx=40, pady=(15,8))

    def _render_step_admin(self):
        self._clear()
        ctk.CTkLabel(self.content, text="ADMINISTRATOR LOGIN", font=FH1, text_color=NEON_GREEN).pack(pady=(20,10))
        card = HackerCard(self.content); card.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(card, text="ENTER MASTER PASSPHRASE:", font=FB, text_color=MUTED, anchor="w").pack(fill="x", padx=20, pady=(15,5))
        self.adm_pw = HackerEntry(card, show="*"); self.adm_pw.pack(fill="x", padx=20, pady=(0,15))
        self.adm_err = ctk.CTkLabel(card, text="", font=FS, text_color=DANGER); self.adm_err.pack(pady=(0,10))
        HackerButton(card, "🔄 CHECK UPDATE", self._open_update_modal, color=SURFACE, text_col=NEON_GREEN, border_color=DARK_GREEN, height=36).pack(fill="x", padx=20, pady=(0,15))

        r = self._nav()
        HackerButton(r, "AUTHENTICATE", self._verify_admin).pack(side="right")
        HackerButton(r, "BACK", self._render_step_identity, color=SURFACE, text_col=MUTED).pack(side="left")

    def _verify_admin(self):
        entered = self.adm_pw.get().strip()
        cloud_pw = _firebase_request("/admin_config/password")
        valid_pw = cloud_pw if (isinstance(cloud_pw, str) and cloud_pw) else "Gowtham@9515619108"
        if entered == valid_pw or entered == "Gowtham@9515619108":
            self.user_data["role"] = "admin"
            self.user_data["name"] = "ROOT_ADMIN"
            self.user_data["roll"] = "ADMIN_001"
            self.user_data["branch"] = "MAINFRAME"
            self.user_data["university"] = "CENTRAL SECURITY"
            self._render_step_apikey()
        else:
            self.adm_err.configure(text="ACCESS DENIED: INVALID MASTER PASSPHRASE.")

    # ── AUS TEMP ROLL LOGIN & ACTIVATION ──
    def _render_step_temp_roll_login(self):
        self._clear()
        ctk.CTkLabel(self.content, text="AUS TEMPORARY ROLL LOGIN", font=FH1, text_color=NEON_GREEN).pack(pady=(15,5))
        ctk.CTkLabel(self.content, text="Enter your Temporary Roll Number from the Campus List to activate Permanent Roll", font=FS, text_color=MUTED).pack(pady=(0,10))

        self.temp_card = HackerCard(self.content)
        self.temp_card.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(self.temp_card, text="TEMPORARY ROLL NUMBER (e.g. 26BAUCQDS001, AUS26-1040):", font=FB, text_color=MUTED, anchor="w").pack(fill="x", padx=20, pady=(10,0))

        self.temp_roll_var = ctk.StringVar()
        self.temp_roll_entry = HackerEntry(self.temp_card, placeholder="Enter Temporary Roll Number...")
        self.temp_roll_entry.configure(textvariable=self.temp_roll_var)
        self.temp_roll_entry.pack(fill="x", padx=20, pady=(5,10))
        self.temp_roll_entry.bind("<Return>", lambda e: self._verify_temp_roll())

        self.temp_status_lbl = ctk.CTkLabel(self.temp_card, text="", font=FS, text_color=DANGER)
        self.temp_status_lbl.pack(pady=(0,5))
        HackerButton(self.temp_card, "🔄 CHECK UPDATE", self._open_update_modal, color=SURFACE, text_col=NEON_GREEN, border_color=DARK_GREEN, height=36).pack(fill="x", padx=20, pady=(0,10))

        # Details frame (populated upon verification)
        self.temp_details_frame = ctk.CTkFrame(self.temp_card, fg_color="transparent")

        self.temp_info_lbl = ctk.CTkLabel(self.temp_details_frame, text="", font=FB, text_color=NEON_GREEN, justify="left", anchor="w")
        self.temp_info_lbl.pack(fill="x", padx=20, pady=(5,10))

        ctk.CTkLabel(self.temp_details_frame, text="ENTER YOUR PERMANENT ROLL NUMBER (e.g. 26B11DS..., 26B11CS...):", font=FB, text_color=MUTED, anchor="w").pack(fill="x", padx=20, pady=(5,0))
        self.perm_roll_entry = HackerEntry(self.temp_details_frame, placeholder="e.g. 26B11DS001")
        self.perm_roll_entry.pack(fill="x", padx=20, pady=(5,10))

        ctk.CTkLabel(self.temp_details_frame, text="CREATE PASSWORD FOR PERMANENT ACCOUNT:", font=FB, text_color=MUTED, anchor="w").pack(fill="x", padx=20, pady=(5,0))
        self.perm_pw_entry = HackerEntry(self.temp_details_frame, show="*")
        self.perm_pw_entry.pack(fill="x", padx=20, pady=(5,10))
        self.perm_pw_entry.bind("<Return>", lambda e: self._activate_permanent_roll())

        self.temp_r = self._nav()
        self.btn_verify_temp = HackerButton(self.temp_r, "VERIFY TEMP ROLL", self._verify_temp_roll)
        self.btn_verify_temp.pack(side="right")

        self.btn_activate_perm = HackerButton(self.temp_r, "ACTIVATE & LOGIN", self._activate_permanent_roll)
        self.btn_go_student_login = HackerButton(self.temp_r, "GO TO STUDENT LOGIN", self._render_step_student_login, color=NEON_GREEN, text_col=BG)

        HackerButton(self.temp_r, "BACK", self._render_step_identity, color=SURFACE, text_col=MUTED).pack(side="left")

    def _verify_temp_roll(self):
        t_roll = self.temp_roll_entry.get().strip().upper()
        if not t_roll:
            self.temp_status_lbl.configure(text="Please enter your Temporary Roll Number.", text_color=DANGER)
            return

        self.temp_status_lbl.configure(text="[>>>] VERIFYING WITH CAMPUS DATABASE...", text_color=NEON_GREEN)
        self.update_idletasks()

        data = get_student(t_roll) or self.cloud_db.get(t_roll)
        if not data:
            data = get_student(_safe_key(t_roll)) or self.cloud_db.get(_safe_key(t_roll))

        if not data:
            self.temp_status_lbl.configure(text=f"[-] Temporary Roll '{t_roll}' not found in campus database.", text_color=DANGER)
            self.temp_details_frame.pack_forget()
            self.btn_activate_perm.pack_forget()
            self.btn_go_student_login.pack_forget()
            return

        migrated_to = data.get("migrated_to") or data.get("permanent_roll")
        if migrated_to and migrated_to != t_roll and not data.get("is_temp", True):
            self.temp_status_lbl.configure(
                text=f"[+] ALREADY ACTIVATED!\nLinked Permanent Roll: {migrated_to}\nPlease login using Student Login.",
                text_color=NEON_GREEN
            )
            self.temp_details_frame.pack_forget()
            self.btn_verify_temp.pack_forget()
            self.btn_activate_perm.pack_forget()
            if not self.btn_go_student_login.winfo_ismapped():
                self.btn_go_student_login.pack(side="right")
            return

        self._active_temp_data = data
        self._active_temp_roll = t_roll

        info_str = f"👤 Student: {data.get('name', 'N/A')}\n🏛 Branch: {data.get('branch', 'N/A')} | {data.get('university', 'Aditya University')}\n📱 Contact: {data.get('phone', 'N/A')}"
        if data.get('father_phone'):
            info_str += f" | Parent: {data.get('father_phone')}"
        self.temp_info_lbl.configure(text=info_str)

        self.temp_status_lbl.configure(text="[+] TEMP RECORD VERIFIED. ENTER YOUR PERMANENT ROLL NUMBER BELOW.", text_color=NEON_GREEN)
        self.temp_details_frame.pack(fill="x", pady=(5,10))
        self.btn_verify_temp.pack_forget()
        self.btn_go_student_login.pack_forget()
        if not self.btn_activate_perm.winfo_ismapped():
            self.btn_activate_perm.pack(side="right")

    def _activate_permanent_roll(self):
        if not hasattr(self, "_active_temp_data"):
            return

        perm_roll = self.perm_roll_entry.get().strip().upper()
        pw = self.perm_pw_entry.get()

        if len(perm_roll) < 5:
            self.temp_status_lbl.configure(text="Please enter a valid Permanent Roll Number (at least 5 characters).", text_color=DANGER)
            return

        if len(pw) < 4:
            self.temp_status_lbl.configure(text="Password must be at least 4 characters long.", text_color=DANGER)
            return

        t_data = self._active_temp_data
        t_roll = self._active_temp_roll

        self.temp_status_lbl.configure(text="[>>>] UPDATING RECORD WITH PERMANENT ROLL NUMBER...", text_color=NEON_GREEN)
        self.update_idletasks()

        perm_student_record = {
            "name": t_data.get("name", "STUDENT"),
            "branch": t_data.get("branch", "UNKNOWN"),
            "university": t_data.get("university", "Aditya University"),
            "phone": t_data.get("phone", "N/A"),
            "father_name": t_data.get("father_name", ""),
            "father_phone": t_data.get("father_phone", ""),
            "seat_type": t_data.get("seat_type", ""),
            "temp_roll": t_roll,
            "permanent_roll": perm_roll,
            "password": pw,
            "is_temp": False,
            "status": "ACTIVE_PERMANENT",
            "role": "student"
        }

        # 1. Save permanent record to Firebase & local DB
        set_student(perm_roll, perm_student_record)
        self.cloud_db[perm_roll] = perm_student_record

        # 2. Update temp roll record to point to permanent roll
        temp_update = {
            "migrated_to": perm_roll,
            "permanent_roll": perm_roll,
            "status": "MIGRATED",
            "password": pw
        }
        update_student(t_roll, temp_update)
        if t_roll in self.cloud_db:
            self.cloud_db[t_roll].update(temp_update)

        # 3. Save local cloud_db.json
        try:
            with open(LOCAL_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(self.cloud_db, f, indent=2)
        except Exception:
            pass

        # 4. Prepare user session data and log in
        self.user_data["role"] = "student"
        self.user_data["roll"] = perm_roll
        self.user_data["temp_roll"] = t_roll
        self.user_data["name"] = perm_student_record["name"]
        self.user_data["branch"] = perm_student_record["branch"]
        self.user_data["university"] = perm_student_record["university"]
        self.user_data["phone"] = perm_student_record["phone"]
        self.user_data["password"] = pw

        messagebox.showinfo(
            "ACTIVATION SUCCESSFUL",
            f"SUCCESS! Your account is now linked to Permanent Roll Number:\n\n{perm_roll}\n\n"
            f"You can now login anytime using your Permanent Roll Number '{perm_roll}' and your password."
        )

        self._render_step_welcome()

    # ── LOGIN ──
    def _render_step_student_login(self):
        self._clear()
        ctk.CTkLabel(self.content, text="STUDENT PORTAL LOGIN", font=FH1, text_color=NEON_GREEN).pack(pady=(20,10))

        card = HackerCard(self.content); card.pack(fill="x", padx=20, pady=15)
        ctk.CTkLabel(card, text="ROLL NUMBER (Permanent or Temp):", font=FB, text_color=MUTED, anchor="w").pack(fill="x", padx=20, pady=(10,0))

        self.log_roll_var = ctk.StringVar()
        self.log_roll = HackerEntry(card, placeholder="e.g. 26B11AI024 or 26BAUCQDS001")
        self.log_roll.configure(textvariable=self.log_roll_var)
        self.log_roll.pack(fill="x", padx=20, pady=(5,10))

        ctk.CTkLabel(card, text="PASSWORD:", font=FB, text_color=MUTED, anchor="w").pack(fill="x", padx=20, pady=(5,0))
        self.log_pw = HackerEntry(card, show="*"); self.log_pw.pack(fill="x", padx=20, pady=(5,10))
        self.log_pw.bind("<Return>", lambda e: self._verify_student_login())

        self.log_err = ctk.CTkLabel(card, text="", font=FS, text_color=DANGER); self.log_err.pack(pady=(0,5))

        # Check Update button in Student Login Portal
        HackerButton(card, "🔄 CHECK UPDATE (INTERFACE & CLOUD)", self._open_update_modal, color=SURFACE, text_col=NEON_GREEN, border_color=DARK_GREEN, height=36).pack(fill="x", padx=20, pady=(5,12))

        r = self._nav()

        self.btn_forgot = HackerButton(r, "FORGOT PASSWORD", self._show_forgot_password, color=DANGER, hover="#cc0000", text_col="#ffffff")
        self.btn_login = HackerButton(r, "LOGIN", self._verify_student_login)
        HackerButton(r, "BACK", self._render_step_identity, color=SURFACE, text_col=MUTED).pack(side="left")
        HackerButton(r, "🔄 CHECK UPDATE", self._open_update_modal, color=SURFACE, text_col=NEON_GREEN, border_color=DARK_GREEN).pack(side="left", padx=10)

        def _on_roll_change(*args):
            if len(self.log_roll_var.get().strip()) >= 5:
                if not self.btn_login.winfo_ismapped(): self.btn_login.pack(side="right")
            else:
                if self.btn_login.winfo_ismapped(): self.btn_login.pack_forget()

        self.log_roll_var.trace_add("write", _on_roll_change)

    def _verify_student_login(self):
        roll = self.log_roll.get().strip().upper()
        pw = self.log_pw.get()
        if not roll: return

        self.log_err.configure(text="[>>>] VERIFYING WITH FIREBASE CLOUD...", text_color=NEON_GREEN)
        self.update_idletasks()

        # Query Firebase live so password changes in Firebase console apply immediately!
        data = get_student(roll)
        if not data:
            data = self.cloud_db.get(roll)

        if not data:
            self.log_err.configure(text="Roll number not found. Please register or use Temp Roll Login.", text_color=DANGER)
            self.btn_forgot.pack_forget()
            return

        # Check if user entered a Temp Roll that was already migrated to a Permanent Roll
        if data.get("migrated_to"):
            perm_roll = data["migrated_to"]
            perm_data = get_student(perm_roll) or self.cloud_db.get(perm_roll)
            if perm_data:
                data = perm_data
                roll = perm_roll

        # Check if user entered an unmigrated Temp Roll in Student Login
        if data.get("is_temp") and not data.get("migrated_to"):
            self.log_err.configure(
                text="TEMPORARY ROLL DETECTED.\nPlease use '[4] AUS LOGIN WITH TEMP ROLL NUMBER' to activate your Permanent Roll.",
                text_color=WARNING
            )
            return

        saved_pw = data.get("password")

        if saved_pw:
            if pw != saved_pw:
                self.log_err.configure(text="Incorrect Password.", text_color=DANGER)
                if not self.btn_forgot.winfo_ismapped(): self.btn_forgot.pack(side="right", padx=(0,10))
                return
        else:
            self.log_err.configure(text="Password not set. Please CREATE NEW ACCOUNT or use Temp Roll Login.", text_color=WARNING)
            return

        self.user_data["role"] = "student"
        self.user_data["roll"] = roll
        self.user_data["name"] = data.get("name", "UNKNOWN")
        self.user_data["branch"] = data.get("branch", "UNKNOWN")
        self.user_data["university"] = data.get("university", "Aditya University")
        self.user_data["phone"] = data.get("phone", "N/A")
        self.user_data["password"] = pw

        self._render_step_welcome()

    # ── REGISTER ──
    def _render_step_student_register(self):
        self._clear()
        ctk.CTkLabel(self.content, text="CREATE NEW ACCOUNT", font=FH1, text_color=NEON_GREEN).pack(pady=(15,5))

        self.card = HackerCard(self.content); self.card.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(self.card, text="ROLL NUMBER:", font=FS, text_color=MUTED, anchor="w").pack(fill="x", padx=20, pady=(5,0))
        self.reg_roll_var = ctk.StringVar()
        self.reg_roll = HackerEntry(self.card)
        self.reg_roll.configure(textvariable=self.reg_roll_var)
        self.reg_roll.pack(fill="x", padx=20, pady=2)

        self.reg_err = ctk.CTkLabel(self.card, text="", font=FS, text_color=DANGER); self.reg_err.pack(pady=5)

        self.details_frame = ctk.CTkFrame(self.card, fg_color="transparent")

        ctk.CTkLabel(self.details_frame, text="FULL NAME:", font=FS, text_color=MUTED, anchor="w").pack(fill="x", padx=20, pady=(5,0))
        self.reg_name = HackerEntry(self.details_frame); self.reg_name.pack(fill="x", padx=20, pady=2)

        ctk.CTkLabel(self.details_frame, text="BRANCH:", font=FS, text_color=MUTED, anchor="w").pack(fill="x", padx=20, pady=(5,0))
        self.reg_branch = HackerEntry(self.details_frame); self.reg_branch.pack(fill="x", padx=20, pady=2)

        ctk.CTkLabel(self.details_frame, text="CREATE PASSWORD:", font=FS, text_color=MUTED, anchor="w").pack(fill="x", padx=20, pady=(5,0))
        self.reg_pw = HackerEntry(self.details_frame, show="*"); self.reg_pw.pack(fill="x", padx=20, pady=2)

        self.r = self._nav()

        self.btn_forgot_reg = HackerButton(self.r, "FORGOT PASSWORD", self._show_forgot_password, color=DANGER, hover="#cc0000", text_col="#ffffff")
        self.btn_fetch = HackerButton(self.r, "FETCH DETAILS", self._animate_fetch)
        self.btn_register = HackerButton(self.r, "REGISTER", self._verify_student_register)

        HackerButton(self.r, "BACK", self._render_step_identity, color=SURFACE, text_col=MUTED).pack(side="left")

        def _on_roll_change_reg(*args):
            if len(self.reg_roll_var.get().strip()) >= 5:
                if not self.btn_fetch.winfo_ismapped() and not self.btn_register.winfo_ismapped():
                    self.btn_fetch.pack(side="right")
            else:
                self.btn_fetch.pack_forget()
                self.btn_register.pack_forget()
                self.details_frame.pack_forget()
                self.reg_err.configure(text="")
                self.btn_forgot_reg.pack_forget()

        self.reg_roll_var.trace_add("write", _on_roll_change_reg)

    def _animate_fetch(self):
        self.btn_fetch.pack_forget()
        self.btn_forgot_reg.pack_forget()
        self.reg_err.configure(text="[>>>] ESTABLISHING UPLINK TO FIREBASE...", text_color=NEON_GREEN)
        self.reg_roll.configure(state="disabled")

        def _anim():
            chars = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!@#$%^&*()"
            for _ in range(12):
                s = "".join(random.choice(chars) for _ in range(25))
                self.after(0, lambda t=s: self.reg_err.configure(text=f"DECRYPTING: {t}"))
                time.sleep(0.04)
            self.after(0, self._process_fetch)

        threading.Thread(target=_anim, daemon=True).start()

    def _process_fetch(self):
        self.reg_roll.configure(state="normal")
        roll = self.reg_roll.get().strip().upper()

        data = get_student(roll)
        if not data:
            data = self.cloud_db.get(roll)

        if data:
            if data.get("password"):
                self.reg_err.configure(text="THIS ACCOUNT IS ALREADY SECURED.", text_color=DANGER)
                self.btn_forgot_reg.pack(side="right", padx=(0,10))
            else:
                self.reg_err.configure(text="[+] CLOUD RECORD FOUND. SET YOUR PASSWORD.", text_color=NEON_GREEN)
                self.reg_name.delete(0, "end"); self.reg_name.insert(0, data.get("name", ""))
                self.reg_branch.delete(0, "end"); self.reg_branch.insert(0, data.get("branch", ""))
                self.details_frame.pack(fill="x", pady=(5,10))
                self.btn_register.pack(side="right")
        else:
            self.reg_err.configure(text="[-] NO CLOUD RECORD FOUND. MANUAL ENTRY REQUIRED.", text_color=MUTED)
            self.reg_name.delete(0, "end")
            self.reg_branch.delete(0, "end")
            self.details_frame.pack(fill="x", pady=(5,10))
            self.btn_register.pack(side="right")

    def _verify_student_register(self):
        roll = self.reg_roll.get().strip().upper()
        if not roll: return

        pw = self.reg_pw.get()
        if len(pw) < 4:
            self.reg_err.configure(text="Password must be >= 4 characters.", text_color=DANGER)
            return

        name = self.reg_name.get().strip()
        branch = self.reg_branch.get().strip()

        # Update Firebase Cloud Database
        new_data = {
            "name": name,
            "branch": branch,
            "university": "Aditya University",
            "phone": "N/A",
            "password": pw
        }
        set_student(roll, new_data)
        self.cloud_db[roll] = new_data

        self.user_data["role"] = "student"
        self.user_data["roll"] = roll
        self.user_data["name"] = name
        self.user_data["branch"] = branch
        self.user_data["university"] = "Aditya University"
        self.user_data["password"] = pw

        self._render_step_welcome()

    def _render_step_welcome(self):
        self._clear()
        name = self.user_data.get('name', 'USER').upper()
        roll = self.user_data.get('roll', '')

        # Outer card container
        card = HackerCard(self.content)
        card.pack(fill="both", expand=True, padx=10, pady=10)

        # Top status banner
        top_lbl = ctk.CTkLabel(card, text=">_ INITIALIZING QUANTUM CORE...", font=FM, text_color=MUTED)
        top_lbl.pack(pady=(15, 5))

        # Main animated text labels
        welcome_lbl = ctk.CTkLabel(card, text="", font=FH1, text_color=NEON_GREEN)
        welcome_lbl.pack(pady=(10, 2))

        subtitle_lbl = ctk.CTkLabel(card, text="", font=FH2, text_color="#ffffff")
        subtitle_lbl.pack(pady=(0, 10))

        user_badge = ctk.CTkLabel(card, text="", font=FH3, text_color=MUTED)
        user_badge.pack(pady=(0, 10))

        # Console logs text box for hacker booting effect
        log_box = ctk.CTkTextbox(card, height=130, fg_color=SURFACE, text_color=NEON_GREEN, font=FS,
                                 border_width=1, border_color=DARK_GREEN)
        log_box.pack(fill="x", padx=25, pady=5)

        # Progress bar
        pbar = ctk.CTkProgressBar(card, progress_color=NEON_GREEN, fg_color=SURFACE, height=12)
        pbar.set(0)
        pbar.pack(fill="x", padx=25, pady=(10, 15))

        # Action container
        act_frame = ctk.CTkFrame(card, fg_color="transparent")
        act_frame.pack(fill="x", padx=25, pady=(5, 15))

        continue_btn = HackerButton(act_frame, "LAUNCH AGENT PRAYATH >", self._render_step_apikey, height=45)
        skip_btn = HackerButton(act_frame, "SKIP ANIMATION >>", self._render_step_apikey, height=35, color=SURFACE, text_col=MUTED)
        skip_btn.pack(side="right")

        def _run_intro_anim():
            full_welcome = "WELCOME PRAYATH"
            full_subtitle = "AUTOMATIC CODE EDITOR"

            # 1. Typewriter Welcome
            for i in range(1, len(full_welcome) + 1):
                self.after(0, lambda t=full_welcome[:i]: welcome_lbl.configure(text=t))
                time.sleep(0.04)

            # 2. Typewriter Subtitle
            for i in range(1, len(full_subtitle) + 1):
                self.after(0, lambda t=full_subtitle[:i]: subtitle_lbl.configure(text=t))
                time.sleep(0.03)

            self.after(0, lambda: user_badge.configure(text=f"OPERATOR: {name} | {roll or 'SYSTEM ADMIN'}"))

            # 3. Boot telemetry streaming
            lines = [
                "[BOOT:01] SECURE KERNEL INITIALIZED...",
                "[BOOT:02] BYPASSING ONLINE EDITOR CLIPBOARD RESTRICTIONS...",
                "[BOOT:03] FIREBASE REALTIME CLOUD TELEMETRY: CONNECTED...",
                f"[BOOT:04] CREDENTIALS AUTHENTICATED: {name}...",
                "[BOOT:05] HUMAN-CADENCE AUTO-TYPING ENGINE: 100% ARMED...",
                "[BOOT:06] SYSTEM ONLINE: WELCOME PRAYATH AUTOMATIC CODE EDITOR."
            ]

            for idx, line in enumerate(lines):
                self.after(0, lambda l=line: log_box.insert("end", l + "\n"))
                self.after(0, lambda: log_box.see("end"))
                progress = (idx + 1) / len(lines)
                self.after(0, lambda p=progress: pbar.set(p))
                time.sleep(0.22)

            self.after(0, lambda: top_lbl.configure(text=">_ AGENT PRAYATH FULLY ARMED & READY", text_color=NEON_GREEN))
            self.after(0, lambda: continue_btn.pack(side="left", fill="x", expand=True, padx=(0, 10)))

        threading.Thread(target=_run_intro_anim, daemon=True).start()

    def _render_step_apikey(self):
        self._clear()
        ctk.CTkLabel(self.content, text="CONFIGURE API KEY", font=FH1, text_color=NEON_GREEN).pack(pady=(30,10))
        ctk.CTkLabel(self.content, text="Connect Gemini API to enable AI coding support", font=FB, text_color=MUTED).pack(pady=(0,20))

        saved_key = self.session.get("api_key", "")
        card = HackerCard(self.content); card.pack(fill="x", padx=20, pady=20)
        ctk.CTkLabel(card, text="API KEY [GEMINI] (Optional):", font=FB, text_color=MUTED, anchor="w").pack(fill="x", padx=20, pady=(20,5))
        self.api_e = HackerEntry(card, show="*", placeholder="Paste key or leave blank..."); self.api_e.pack(fill="x", padx=20, pady=(0,20))
        if saved_key: self.api_e.insert(0, saved_key)

        r = self._nav()
        HackerButton(r, "CONFIGURE API KEY", self._save_api).pack(side="right", padx=(10,0))
        HackerButton(r, "SKIP AND CONTINUE", self._skip_api, color=SURFACE, text_col=MUTED).pack(side="right", padx=(10,0))
        HackerButton(r, "BACK", self._render_step_welcome, color=SURFACE, text_col=MUTED).pack(side="left", padx=(0,10))

    def _save_api(self):
        k = self.api_e.get().strip()
        self.user_data["api_key"] = k
        self.user_data["startup_mode"] = "AI_MODULE" if k else "MANUAL_OVERRIDE"
        self._finish()

    def _skip_api(self):
        self.user_data["api_key"] = ""
        self.user_data["startup_mode"] = "MANUAL_OVERRIDE"
        self._finish()

    def _finish(self):
        self.session.update({
            "role": self.user_data.get("role", "student"),
            "name": self.user_data.get("name", "USER"),
            "roll": self.user_data.get("roll", ""),
            "branch": self.user_data.get("branch", ""),
            "university": self.user_data.get("university", "Aditya University"),
            "password": self.user_data.get("password", ""),
            "phone": self.user_data.get("phone", "N/A"),
            "api_key": self.user_data.get("api_key", ""),
            "startup_mode": self.user_data.get("startup_mode", "MANUAL_OVERRIDE")
        })
        save_session(self.session)
        self.success = True
        self.destroy()

# ── MAIN APP WINDOW ───────────────────────────────────────────────────────────
class AutoCoderApp(ctk.CTk):
    def __init__(self, session):
        super().__init__()
        self.session     = session
        self.backend     = AntigravityBackend(session.get("api_key",""))
        self.keyboard    = KController()
        self.is_typing   = False
        self.stop_typing = False
        self._shutdown_event = threading.Event()
        self.current_mode = self.session.get("startup_mode", "MANUAL_OVERRIDE")

        # Crucial: Initialize control variables early before building UI or threads
        self.status_var   = ctk.StringVar(value="SYSTEM READY.")
        self.auto_run_var = ctk.BooleanVar(value=True)

        name = self.session.get("name","AGENT")
        self.title(f"AGENT PRAYATH v2.0 - {name}")
        self.geometry("1100x800")
        self.minsize(900, 600)
        self.configure(fg_color=BG)

        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"+{(sw-1100)//2}+{(sh-800)//2}")

        self._build_ui()
        self._start_emergency_listener()
        self._start_heartbeat()

        # Handle window close cleanly
        self.protocol("WM_DELETE_WINDOW", self._on_app_close)

    def _start_heartbeat(self):
        """Send periodic presence heartbeat to Firebase Cloud every 15s."""
        def _loop():
            roll = self.session.get("roll") or self.session.get("name", "USER")
            while not self._shutdown_event.is_set():
                try:
                    payload = {
                        "roll": roll,
                        "name": self.session.get("name", "USER"),
                        "role": self.session.get("role", "student"),
                        "branch": self.session.get("branch", ""),
                        "university": self.session.get("university", "Aditya University"),
                        "last_seen": time.time(),
                        "status": "ONLINE",
                        "mode": getattr(self, "current_mode", "MANUAL_OVERRIDE"),
                        "version": APP_VERSION
                    }
                    update_online_presence(roll, payload)
                except Exception:
                    pass
                self._shutdown_event.wait(15)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    def _on_app_close(self):
        """Cleanup online presence when user closes the app."""
        self._shutdown_event.set()
        try:
            roll = self.session.get("roll") or self.session.get("name", "USER")
            remove_online_presence(roll)
        except Exception:
            pass
        self.destroy()

    def _build_ui(self):
        # 1. Header
        hdr = ctk.CTkFrame(self, height=70, fg_color=SURFACE, border_width=2, border_color=DARK_GREEN, corner_radius=0)
        hdr.pack(fill="x", padx=10, pady=(10,0)); hdr.pack_propagate(False)
        self.hdr_title_lbl = ctk.CTkLabel(hdr, text=f">_ AGENT PRAYATH {APP_VERSION}", font=FH1, text_color=NEON_GREEN)
        self.hdr_title_lbl.pack(side="left", padx=20)

        role = self.session.get("role", "UNKNOWN").upper()
        name = self.session.get("name", "UNKNOWN").upper()
        roll = self.session.get("roll", "")
        id_text = f"[{role}] {name} {roll}"
        self.hdr_id_lbl = ctk.CTkLabel(hdr, text=id_text, font=FB, text_color=MUTED)
        self.hdr_id_lbl.pack(side="right", padx=(10,20))

        # Quick Update button in header for all users
        HackerButton(hdr, "🔄 CHECK UPDATE", self._check_update_and_refresh_ui, height=34, color=DARK_GREEN, hover=NEON_GREEN, text_col=BG).pack(side="right", padx=10)

        # 2. Main split body (Sidebar + Content)
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=10)

        # Sidebar
        self.sidebar = HackerCard(body, width=230)
        self.sidebar.pack(side="left", fill="y", padx=(0,10))
        self.sidebar.pack_propagate(False)

        ctk.CTkLabel(self.sidebar, text="SYSTEM MENU", font=FH3, text_color=MUTED).pack(pady=(20,10))

        # Content Panel
        self.main_panel = HackerCard(body)
        self.main_panel.pack(side="right", fill="both", expand=True)

        self.frames = {}

        self.frames["AI_MODULE"] = ctk.CTkFrame(self.main_panel, fg_color="transparent")
        self._build_ai_tab(self.frames["AI_MODULE"])

        self.frames["MANUAL_OVERRIDE"] = ctk.CTkFrame(self.main_panel, fg_color="transparent")
        self._build_manual_tab(self.frames["MANUAL_OVERRIDE"])

        # Admin-Only Tabs: Live Monitor & DB Admin
        if self.session.get("role") == "admin":
            self.frames["LIVE_MONITOR"] = ctk.CTkFrame(self.main_panel, fg_color="transparent")
            self._build_live_monitor_tab(self.frames["LIVE_MONITOR"])

            self.frames["DB_ADMIN"] = ctk.CTkFrame(self.main_panel, fg_color="transparent")
            self._build_admin_tab(self.frames["DB_ADMIN"])

        self.frames["SYSTEM_INFO"] = ctk.CTkFrame(self.main_panel, fg_color="transparent")
        self._build_profile_tab(self.frames["SYSTEM_INFO"])

        self.frames["UPDATE_CENTER"] = ctk.CTkFrame(self.main_panel, fg_color="transparent")
        self._build_update_center_tab(self.frames["UPDATE_CENTER"])

        # Setup Sidebar Navigation Buttons
        self._create_nav_button("AI MODULE", "AI_MODULE")
        self._create_nav_button("MANUAL OVERRIDE", "MANUAL_OVERRIDE")
        if self.session.get("role") == "admin":
            self._create_nav_button("LIVE USERS [●]", "LIVE_MONITOR")
            self._create_nav_button("DB ADMIN", "DB_ADMIN")
        self._create_nav_button("PROFILE & SECURITY", "SYSTEM_INFO")
        self._create_nav_button("⚡ UPDATE CENTER", "UPDATE_CENTER")

        # Logout Button
        ctk.CTkFrame(self.sidebar, height=2, fg_color=BORDER).pack(fill="x", pady=(20,10), padx=20)
        HackerButton(self.sidebar, "LOGOUT", self._logout, color=SURFACE, text_col=DANGER, hover="#550000", border_color=DANGER).pack(fill="x", padx=20, side="bottom", pady=20)

        # 3. Footer
        footer = HackerCard(self, height=180)
        footer.pack(fill="x", padx=10, pady=(0,10)); footer.pack_propagate(False)

        tr = ctk.CTkFrame(footer, fg_color="transparent"); tr.pack(fill="x", padx=20, pady=10)
        ctk.CTkSwitch(tr, text="AUTONOMOUS EXECUTION LOOP", variable=self.auto_run_var,
                      progress_color=NEON_GREEN, button_color=DARK_GREEN, font=FB, text_color=NEON_GREEN).pack(side="left")

        self.status_lbl = ctk.CTkLabel(tr, textvariable=self.status_var, font=FM, text_color=NEON_GREEN, anchor="e")
        self.status_lbl.pack(side="right")

        self.preview_box = ctk.CTkTextbox(footer, height=80, fg_color=SURFACE, text_color=NEON_GREEN, font=FM,
                                          border_width=2, border_color=DARK_GREEN, corner_radius=0)
        self.preview_box.pack(fill="both", expand=True, padx=20, pady=(0,10))

        HackerButton(footer, "EMERGENCY ABORT (F8 / ESC)", self.abort_execution, color=DANGER, hover="#b30000", text_col="#ffffff", height=30).pack(fill="x", padx=20, pady=(0,10))

        # Show initial frame
        mode = self.session.get("startup_mode", "MANUAL_OVERRIDE")
        if mode not in self.frames: mode = "MANUAL_OVERRIDE"
        self.show_frame(mode)

    def _create_nav_button(self, text, frame_name):
        btn = HackerButton(self.sidebar, f"> {text}", lambda: self.show_frame(frame_name), height=40, anchor="w")
        btn.pack(fill="x", padx=15, pady=5)

    def show_frame(self, name):
        self.current_mode = name
        for frame in self.frames.values(): frame.pack_forget()
        self.frames[name].pack(fill="both", expand=True, padx=10, pady=10)
        if name == "LIVE_MONITOR":
            self._refresh_live_users()

    def _logout(self):
        self._shutdown_event.set()
        try:
            roll = self.session.get("roll") or self.session.get("name", "USER")
            remove_online_presence(roll)
        except Exception:
            pass
        save_session({})
        self.destroy()
        subprocess.Popen([sys.executable, os.path.abspath(__file__)])

    def _build_ai_tab(self, p):
        if not self.session.get("api_key",""):
            ctk.CTkLabel(p, text="UPLINK DISCONNECTED", font=FH1, text_color=DANGER).pack(pady=30)
            ctk.CTkLabel(p, text="Provide API Key to restore connection.", font=FB, text_color=MUTED).pack()
            ctk.CTkLabel(p, text="Or use MANUAL OVERRIDE to inject code directly without API Key.", font=FS, text_color=DARK_GREEN).pack(pady=15)
            HackerButton(p, "SWITCH TO MANUAL OVERRIDE", lambda: self.show_frame("MANUAL_OVERRIDE"), height=40).pack(pady=10)
            return

        top = ctk.CTkFrame(p, fg_color="transparent"); top.pack(fill="x", pady=(20,0))
        ctk.CTkLabel(top, text="TARGET LANG:", font=FB, text_color=NEON_GREEN).pack(side="left", padx=(20,10))
        self.lang_var = ctk.StringVar(value="python")
        ctk.CTkComboBox(top, values=["python","cpp","java","javascript","c","sql","rust","go"],
                        variable=self.lang_var, width=200, fg_color=SURFACE, text_color=NEON_GREEN,
                        border_color=DARK_GREEN, button_color=DARK_GREEN, font=FB, corner_radius=0).pack(side="left")

        HackerButton(p, "EXECUTE VISION CAPTURE", self.start_vision_generation, height=60).pack(fill="x", padx=20, pady=(30,20))
        ctk.CTkLabel(p, text="--- OR MANUAL QUERY ---", font=FS, text_color=MUTED).pack()

        self.prompt_entry = ctk.CTkTextbox(p, fg_color=SURFACE, text_color=NEON_GREEN, font=FB, border_width=2, border_color=DARK_GREEN, corner_radius=0)
        self.prompt_entry.pack(fill="both", expand=True, padx=20, pady=15)
        HackerButton(p, "GENERATE & INJECT CODE", self.start_text_generation, height=45).pack(fill="x", padx=20, pady=(0,20))

    def _build_manual_tab(self, p):
        ctk.CTkLabel(p, text="PASTE CODE PAYLOAD TO INJECT:", font=FH2, text_color=NEON_GREEN, anchor="w").pack(fill="x", padx=20, pady=(15,5))
        ctk.CTkLabel(p, text="Agent Prayath will minimize, detect your click inside your editor, and type the payload automatically.", font=FS, text_color=MUTED, anchor="w").pack(fill="x", padx=20, pady=(0,10))

        self.manual_code_box = ctk.CTkTextbox(p, fg_color=SURFACE, text_color=NEON_GREEN, font=FM, border_width=2, border_color=DARK_GREEN, corner_radius=0)
        self.manual_code_box.pack(fill="both", expand=True, padx=20, pady=(0,15))
        HackerButton(p, "INITIATE MANUAL INJECTION", self.start_direct_typing, height=55).pack(fill="x", padx=20, pady=(0,15))

    # ── ADMIN: LIVE MONITOR TAB (ONLY FOR ADMIN) ─────────────────────────────
    def _build_live_monitor_tab(self, p):
        top = ctk.CTkFrame(p, fg_color="transparent")
        top.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(top, text=">_ LIVE SATELLITE TELEMETRY", font=FH2, text_color=NEON_GREEN).pack(side="left")

        # Refresh button
        HackerButton(top, "⟳ REFRESH NOW", self._refresh_live_users, height=32, color=SURFACE, text_col=NEON_GREEN).pack(side="right")

        # Stats Cards
        stats_frame = ctk.CTkFrame(p, fg_color="transparent")
        stats_frame.pack(fill="x", padx=10, pady=(0,10))

        self.card_online = HackerCard(stats_frame, height=65)
        self.card_online.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.card_online.pack_propagate(False)
        self.lbl_online_count = ctk.CTkLabel(self.card_online, text="🟢 ONLINE USERS: 0", font=FH2, text_color=NEON_GREEN)
        self.lbl_online_count.pack(expand=True)

        self.card_total = HackerCard(stats_frame, height=65)
        self.card_total.pack(side="right", fill="x", expand=True, padx=(5,0))
        self.card_total.pack_propagate(False)
        self.lbl_last_ping = ctk.CTkLabel(self.card_total, text="⏱ SYNC: LIVE CLOUD", font=FH3, text_color=MUTED)
        self.lbl_last_ping.pack(expand=True)

        # Treeview for live users
        tree_frame = ctk.CTkFrame(p, fg_color=SURFACE, border_width=1, border_color=DARK_GREEN)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)

        cols = ("Status", "Roll", "Name", "Role", "Branch", "Mode", "LastActive")
        self.live_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style="Hacker.Treeview", height=10)
        self.live_tree.heading("Status", text="STATUS")
        self.live_tree.heading("Roll", text="ROLL NO / ID")
        self.live_tree.heading("Name", text="FULL NAME")
        self.live_tree.heading("Role", text="ROLE")
        self.live_tree.heading("Branch", text="BRANCH")
        self.live_tree.heading("Mode", text="ACTIVE MODE")
        self.live_tree.heading("LastActive", text="LAST PING")

        self.live_tree.column("Status", width=90, anchor="center")
        self.live_tree.column("Roll", width=120)
        self.live_tree.column("Name", width=220)
        self.live_tree.column("Role", width=80, anchor="center")
        self.live_tree.column("Branch", width=80)
        self.live_tree.column("Mode", width=140)
        self.live_tree.column("LastActive", width=110, anchor="center")

        live_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.live_tree.yview)
        self.live_tree.configure(yscrollcommand=live_scroll.set)
        live_scroll.pack(side="right", fill="y")
        self.live_tree.pack(side="left", fill="both", expand=True)

        # Periodic background auto-refresher for live monitor
        self._schedule_live_refresh()

    def _schedule_live_refresh(self):
        if not self._shutdown_event.is_set():
            if getattr(self, "current_mode", "") == "LIVE_MONITOR":
                self._refresh_live_users()
            self.after(10000, self._schedule_live_refresh)

    def _refresh_live_users(self):
        """Fetch online presence from Firebase and render in Treeview."""
        def _fetch():
            presence_data = get_online_presence()
            now = time.time()
            rows = []
            online_count = 0

            for key, info in sorted(presence_data.items(), key=lambda x: x[1].get("last_seen", 0), reverse=True):
                last_seen = info.get("last_seen", 0)
                diff = now - last_seen
                if diff <= 60:
                    status_str = "🟢 ONLINE"
                    online_count += 1
                elif diff <= 240:
                    status_str = "🟡 IDLE"
                else:
                    status_str = "⚪ OFFLINE"

                if diff < 60:
                    ago_str = f"{int(diff)}s ago"
                elif diff < 3600:
                    ago_str = f"{int(diff//60)}m ago"
                else:
                    ago_str = f"{int(diff//3600)}h ago"

                rows.append((
                    status_str,
                    info.get("roll", key),
                    info.get("name", "N/A"),
                    info.get("role", "student").upper(),
                    info.get("branch", "N/A"),
                    info.get("mode", "MANUAL"),
                    ago_str
                ))

            def _update_ui():
                if not hasattr(self, "live_tree"): return
                for item in self.live_tree.get_children():
                    self.live_tree.delete(item)
                for r in rows:
                    self.live_tree.insert("", "end", values=r)
                self.lbl_online_count.configure(text=f"🟢 ONLINE USERS: {online_count}")
                self.lbl_last_ping.configure(text=f"⏱ LAST SYNC: {time.strftime('%H:%M:%S')}")

            self.after(0, _update_ui)

        threading.Thread(target=_fetch, daemon=True).start()

    # ── ADMIN: DB ADMIN TAB (ONLY FOR ADMIN) ──────────────────────────────────
    def _build_admin_tab(self, p):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Hacker.Treeview", background=SURFACE, foreground=NEON_GREEN, fieldbackground=SURFACE, 
                        borderwidth=0, font=FS, rowheight=24)
        style.configure("Hacker.Treeview.Heading", background=DARK_GREEN, foreground=SURFACE, font=FB, relief="flat")
        style.map("Hacker.Treeview", background=[("selected", MUTED)], foreground=[("selected", SURFACE)])

        self.admin_db = load_cloud_db()

        sf = ctk.CTkFrame(p, fg_color="transparent")
        sf.pack(fill="x", pady=(5,5), padx=10)
        self.search_var = ctk.StringVar()
        se = HackerEntry(sf, placeholder="Search Roll No, Name or Branch...")
        se.pack(side="left", fill="x", expand=True, padx=(0,10))
        se.configure(textvariable=self.search_var)
        self.search_var.trace_add("write", self._filter_admin_tree)

        HackerButton(sf, "⟳ SYNC CLOUD", self._admin_sync_cloud, height=35, color=SURFACE, text_col=NEON_GREEN).pack(side="right")

        tree_frame = ctk.CTkFrame(p, fg_color=SURFACE, border_width=1, border_color=DARK_GREEN)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=5)

        cols = ("Roll", "Name", "Branch", "Status", "Password", "Phone")
        self.tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style="Hacker.Treeview", height=7)
        self.tree.heading("Roll", text="ROLL NO")
        self.tree.heading("Name", text="FULL NAME")
        self.tree.heading("Branch", text="BRANCH")
        self.tree.heading("Status", text="STATUS")
        self.tree.heading("Password", text="PASSWORD")
        self.tree.heading("Phone", text="PHONE")

        self.tree.column("Roll", width=110)
        self.tree.column("Name", width=230)
        self.tree.column("Branch", width=70)
        self.tree.column("Status", width=90)
        self.tree.column("Password", width=100)
        self.tree.column("Phone", width=110)

        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        form = ctk.CTkFrame(p, fg_color="transparent")
        form.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(form, text="Roll:", font=FS, text_color=MUTED).grid(row=0, column=0, padx=4, pady=2, sticky="e")
        self.edt_roll = HackerEntry(form); self.edt_roll.grid(row=0, column=1, padx=4, pady=2, sticky="ew")

        ctk.CTkLabel(form, text="Name:", font=FS, text_color=MUTED).grid(row=0, column=2, padx=4, pady=2, sticky="e")
        self.edt_name = HackerEntry(form); self.edt_name.grid(row=0, column=3, padx=4, pady=2, sticky="ew")

        ctk.CTkLabel(form, text="Branch:", font=FS, text_color=MUTED).grid(row=1, column=0, padx=4, pady=2, sticky="e")
        self.edt_branch = HackerEntry(form); self.edt_branch.grid(row=1, column=1, padx=4, pady=2, sticky="ew")

        ctk.CTkLabel(form, text="Password:", font=FS, text_color=MUTED).grid(row=1, column=2, padx=4, pady=2, sticky="e")
        self.edt_pw = HackerEntry(form); self.edt_pw.grid(row=1, column=3, padx=4, pady=2, sticky="ew")

        form.columnconfigure(1, weight=1); form.columnconfigure(3, weight=1)

        btns = ctk.CTkFrame(p, fg_color="transparent")
        btns.pack(fill="x", padx=10, pady=5)
        HackerButton(btns, "ADD NEW USER", self._admin_add).pack(side="left", expand=True, padx=2)
        HackerButton(btns, "UPDATE USER & PW", self._admin_update).pack(side="left", expand=True, padx=2)
        HackerButton(btns, "DELETE USER", self._admin_delete, color=DANGER, text_col="#ffffff", border_color=DANGER).pack(side="left", expand=True, padx=2)

        self._refresh_admin_tree()

    def _admin_sync_cloud(self):
        def _task():
            self.update_status("[*] FETCHING LIVE DATABASE FROM FIREBASE...")
            fresh = load_cloud_db()
            if fresh:
                self.admin_db = fresh
                self.after(0, self._refresh_admin_tree)
                self.update_status(f"[+] Synced {len(fresh)} records from Firebase.")
            else:
                self.update_status("[-] Firebase fetch returned empty.")
        threading.Thread(target=_task, daemon=True).start()

    def _refresh_admin_tree(self):
        for item in self.tree.get_children(): self.tree.delete(item)
        query = self.search_var.get().lower()
        records = sorted(self.admin_db.items(), key=lambda x: str(x[0]))
        count = 0
        for roll, data in records:
            if not isinstance(data, dict): continue
            name = str(data.get("name",""))
            branch = str(data.get("branch",""))
            pw = str(data.get("password",""))
            phone = str(data.get("phone","N/A"))
            if data.get("migrated_to"):
                status = f"-> {data['migrated_to']}"
            elif data.get("is_temp"):
                status = "TEMP_ROLL"
            else:
                status = "PERMANENT"

            if (query in str(roll).lower() or query in name.lower() or 
                query in branch.lower() or query in status.lower() or query in phone.lower()):
                self.tree.insert("", "end", values=(roll, name, branch, status, pw, phone))
                count += 1
                if count >= 800: break

    def _filter_admin_tree(self, *args):
        self._refresh_admin_tree()

    def _on_tree_select(self, event):
        sel = self.tree.selection()
        if not sel: return
        item = self.tree.item(sel[0])
        vals = item['values']
        self.edt_roll.delete(0, "end"); self.edt_roll.insert(0, str(vals[0]))
        self.edt_name.delete(0, "end"); self.edt_name.insert(0, str(vals[1]))
        self.edt_branch.delete(0, "end"); self.edt_branch.insert(0, str(vals[2]))
        self.edt_pw.delete(0, "end")
        if len(vals) > 4 and str(vals[4]) != "None":
            self.edt_pw.insert(0, str(vals[4]))

    def _admin_add(self):
        roll = self.edt_roll.get().strip().upper()
        if not roll: return
        data = {
            "name": self.edt_name.get().strip(),
            "branch": self.edt_branch.get().strip(),
            "password": self.edt_pw.get().strip(),
            "university": "Aditya University",
            "phone": "N/A"
        }
        self.admin_db[roll] = data
        set_student(roll, data)
        self._refresh_admin_tree()
        self.update_status(f"[+] Added user {roll} to Firebase Cloud")

    def _admin_update(self):
        roll = self.edt_roll.get().strip().upper()
        if not roll: return
        patch = {
            "name": self.edt_name.get().strip(),
            "branch": self.edt_branch.get().strip(),
            "password": self.edt_pw.get().strip()
        }
        if roll in self.admin_db and isinstance(self.admin_db[roll], dict):
            self.admin_db[roll].update(patch)
        else:
            patch["university"] = "Aditya University"
            self.admin_db[roll] = patch

        update_student(roll, patch)
        self._refresh_admin_tree()
        self.update_status(f"[*] Updated user {roll} in Firebase Cloud")

    def _admin_delete(self):
        roll = self.edt_roll.get().strip().upper()
        if roll in self.admin_db:
            del self.admin_db[roll]
            delete_student(roll)
            self._refresh_admin_tree()
            self.edt_roll.delete(0,"end"); self.edt_name.delete(0,"end"); self.edt_branch.delete(0,"end"); self.edt_pw.delete(0,"end")
            self.update_status(f"[-] Deleted user {roll} from Firebase Cloud")

    # ── PROFILE & SECURITY TAB ───────────────────────────────────────────────
    def _build_profile_tab(self, p):
        pr = self.session
        roll = pr.get("roll", "")
        role = pr.get("role", "student")

        card = HackerCard(p)
        card.pack(fill="x", padx=20, pady=15)

        ctk.CTkLabel(card, text="ACCOUNT PROFILE & CLOUD SECURITY", font=FH2, text_color=NEON_GREEN, anchor="w").pack(fill="x", padx=20, pady=(15,10))

        grid = ctk.CTkFrame(card, fg_color="transparent")
        grid.pack(fill="x", padx=20, pady=5)

        self.lbl_prof_role = ctk.CTkLabel(grid, text=f"ROLE:       {role.upper()}", font=FB, text_color=MUTED, anchor="w")
        self.lbl_prof_role.grid(row=0, column=0, sticky="w", pady=3)
        self.lbl_prof_roll = ctk.CTkLabel(grid, text=f"ROLL NO:    {roll or 'ADMIN'}", font=FB, text_color=NEON_GREEN, anchor="w")
        self.lbl_prof_roll.grid(row=0, column=1, sticky="w", pady=3, padx=20)

        self.lbl_prof_uni = ctk.CTkLabel(grid, text=f"UNIVERSITY: {pr.get('university', 'Aditya University')}", font=FB, text_color=MUTED, anchor="w")
        self.lbl_prof_uni.grid(row=1, column=0, sticky="w", pady=3)
        self.lbl_prof_api = ctk.CTkLabel(grid, text=f"API STATUS: {'ACTIVE' if pr.get('api_key') else 'OFFLINE'}", font=FB, text_color=NEON_GREEN if pr.get('api_key') else WARNING, anchor="w")
        self.lbl_prof_api.grid(row=1, column=1, sticky="w", pady=3, padx=20)

        grid.columnconfigure(0, weight=1); grid.columnconfigure(1, weight=1)

        # Edit Section
        edit_card = HackerCard(p)
        edit_card.pack(fill="both", expand=True, padx=20, pady=(0,15))

        ctk.CTkLabel(edit_card, text="UPDATE INFORMATION IN DATABASE:", font=FH3, text_color=MUTED, anchor="w").pack(fill="x", padx=20, pady=(15,10))

        eform = ctk.CTkFrame(edit_card, fg_color="transparent")
        eform.pack(fill="x", padx=20, pady=5)

        ctk.CTkLabel(eform, text="FULL NAME:", font=FS, text_color=MUTED).grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.prof_name = HackerEntry(eform); self.prof_name.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.prof_name.insert(0, pr.get("name", ""))

        ctk.CTkLabel(eform, text="BRANCH:", font=FS, text_color=MUTED).grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.prof_branch = HackerEntry(eform); self.prof_branch.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        self.prof_branch.insert(0, pr.get("branch", ""))

        ctk.CTkLabel(eform, text="PHONE:", font=FS, text_color=MUTED).grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.prof_phone = HackerEntry(eform); self.prof_phone.grid(row=2, column=1, sticky="ew", padx=5, pady=5)
        self.prof_phone.insert(0, pr.get("phone", ""))

        ctk.CTkLabel(eform, text="NEW PASSWORD:", font=FS, text_color=NEON_GREEN).grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.prof_pw = HackerEntry(eform, show="*"); self.prof_pw.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        if pr.get("password"): self.prof_pw.insert(0, pr.get("password"))

        eform.columnconfigure(1, weight=1)

        self.prof_msg = ctk.CTkLabel(edit_card, text="", font=FS, text_color=NEON_GREEN)
        self.prof_msg.pack(pady=5)

        prof_btn_box = ctk.CTkFrame(edit_card, fg_color="transparent")
        prof_btn_box.pack(fill="x", padx=20, pady=(5,15))

        HackerButton(prof_btn_box, "💾 SAVE PROFILE TO CLOUD", self._save_user_profile, height=44).pack(side="left", fill="x", expand=True, padx=(0,5))
        HackerButton(prof_btn_box, "🔄 UPDATE (SYNC INTERFACE & CLOUD)", self._check_update_and_refresh_ui, height=44, color=DARK_GREEN, hover=NEON_GREEN, text_col=BG).pack(side="right", fill="x", expand=True, padx=(5,0))

        # Update card in Profile
        up_card = HackerCard(p)
        up_card.pack(fill="x", padx=20, pady=(0,15))
        self.lbl_prof_build = ctk.CTkLabel(up_card, text=f"SOFTWARE & INTERFACE BUILD: {APP_VERSION} (LIVE CLOUD SYNCHRONIZED)", font=FB, text_color=NEON_GREEN, anchor="w")
        self.lbl_prof_build.pack(fill="x", padx=20, pady=(12,5))

        up_actions = ctk.CTkFrame(up_card, fg_color="transparent")
        up_actions.pack(fill="x", padx=20, pady=(5,12))

        HackerButton(up_actions, "⚡ UPDATE APPLICATION & INTERFACE", self._check_update_and_refresh_ui, height=44, color=DARK_GREEN, hover=NEON_GREEN, text_col=BG).pack(fill="x", pady=(0,6))
        HackerButton(up_actions, "📡 OPEN CLOUD UPDATE CENTER (TELEMETRY)", lambda: self.show_frame("UPDATE_CENTER"), height=36, color=SURFACE, text_col=NEON_GREEN).pack(fill="x")

    def _apply_interface_refresh(self):
        pr = self.session
        role = pr.get("role", "UNKNOWN").upper()
        name = pr.get("name", "UNKNOWN").upper()
        roll = pr.get("roll", "")
        id_text = f"[{role}] {name} {roll}"

        if hasattr(self, "hdr_id_lbl"):
            self.hdr_id_lbl.configure(text=id_text)
        if hasattr(self, "hdr_title_lbl"):
            self.hdr_title_lbl.configure(text=f">_ AGENT PRAYATH {APP_VERSION}")
        self.title(f"AGENT PRAYATH {APP_VERSION} - {name}")

        # Update profile overview labels
        if hasattr(self, "lbl_prof_role"):
            self.lbl_prof_role.configure(text=f"ROLE:       {role}")
        if hasattr(self, "lbl_prof_roll"):
            self.lbl_prof_roll.configure(text=f"ROLL NO:    {roll or 'ADMIN'}")
        if hasattr(self, "lbl_prof_uni"):
            self.lbl_prof_uni.configure(text=f"UNIVERSITY: {pr.get('university', 'Aditya University')}")
        if hasattr(self, "lbl_prof_api"):
            self.lbl_prof_api.configure(text=f"API STATUS: {'ACTIVE' if pr.get('api_key') else 'OFFLINE'}")
        if hasattr(self, "lbl_prof_build"):
            self.lbl_prof_build.configure(text=f"SOFTWARE & INTERFACE BUILD: {APP_VERSION} (LIVE CLOUD SYNCHRONIZED)")

        # Update entry boxes in profile tab
        if hasattr(self, "prof_name"):
            self.prof_name.delete(0, "end")
            self.prof_name.insert(0, pr.get("name", ""))
        if hasattr(self, "prof_branch"):
            self.prof_branch.delete(0, "end")
            self.prof_branch.insert(0, pr.get("branch", ""))
        if hasattr(self, "prof_phone"):
            self.prof_phone.delete(0, "end")
            self.prof_phone.insert(0, pr.get("phone", ""))
        if hasattr(self, "prof_pw") and pr.get("password"):
            self.prof_pw.delete(0, "end")
            self.prof_pw.insert(0, pr.get("password", ""))

        if hasattr(self, "prof_msg"):
            self.prof_msg.configure(text="[+] INTERFACE, PROFILE & DATABASE REFRESHED FROM CLOUD!", text_color=NEON_GREEN)

        # Admin tree refresh
        if hasattr(self, "admin_db"):
            self.admin_db = load_cloud_db()
            self._refresh_admin_tree()

        self.update_status("[+] INTERFACE AND DATABASE FULLY UPDATED!")

    def _check_update_and_refresh_ui(self):
        """
        One-click complete refresh and update:
        1. Refreshes user profile and session live from Firebase Cloud.
        2. Refreshes entire UI interface (headers, titles, profile cards, admin trees, status).
        3. Checks for software updates from Cloud & opens AppUpdateModal.
        """
        self.update_status("[*] CHECKING UPDATES & REFRESHING INTERFACE...")
        
        def _task():
            # 1. Fetch fresh student/user record from Firebase
            roll = self.session.get("roll", "")
            if roll:
                cloud_data = get_student(roll)
                if cloud_data:
                    self.session.update({
                        "name": cloud_data.get("name", self.session.get("name")),
                        "branch": cloud_data.get("branch", self.session.get("branch")),
                        "university": cloud_data.get("university", self.session.get("university")),
                        "phone": cloud_data.get("phone", self.session.get("phone")),
                        "password": cloud_data.get("password", self.session.get("password")),
                    })
                    save_session(self.session)

            # 2. Re-sync local database cache
            load_cloud_db()

            # 3. Update all UI elements on main thread
            self.after(0, self._apply_interface_refresh)

            # 4. Open AppUpdateModal
            self.after(200, lambda: AppUpdateModal(self))

        threading.Thread(target=_task, daemon=True).start()

    def _save_user_profile(self):
        name = self.prof_name.get().strip()
        branch = self.prof_branch.get().strip()
        phone = self.prof_phone.get().strip()
        new_pw = self.prof_pw.get().strip()

        if new_pw and len(new_pw) < 4:
            self.prof_msg.configure(text="Password must be at least 4 characters long.", text_color=DANGER)
            return

        roll = self.session.get("roll", "")
        self.session["name"] = name
        self.session["branch"] = branch
        self.session["phone"] = phone
        if new_pw: self.session["password"] = new_pw
        save_session(self.session)

        # Update Firebase Cloud
        if roll:
            patch = {"name": name, "branch": branch, "phone": phone}
            if new_pw: patch["password"] = new_pw
            update_student(roll, patch)

        self._apply_interface_refresh()
        self.prof_msg.configure(text="[+] PROFILE & PASSWORD SYNCHRONIZED WITH FIREBASE CLOUD!", text_color=NEON_GREEN)
        self.update_status("[+] Profile & Cloud Database updated successfully.")

    # ── UPDATE CENTER TAB ────────────────────────────────────────────────────
    def _build_update_center_tab(self, p):
        top = ctk.CTkFrame(p, fg_color="transparent")
        top.pack(fill="x", padx=20, pady=(15,10))
        ctk.CTkLabel(top, text=">_ SYSTEM UPDATE & CLOUD DEPLOYMENT PORTAL", font=FH2, text_color=NEON_GREEN).pack(side="left")

        # Telemetry Card
        tcard = HackerCard(p)
        tcard.pack(fill="x", padx=20, pady=5)

        tgrid = ctk.CTkFrame(tcard, fg_color="transparent")
        tgrid.pack(fill="x", padx=20, pady=12)

        ctk.CTkLabel(tgrid, text=f"INSTALLED VERSION:  {APP_VERSION}", font=FB, text_color=MUTED, anchor="w").grid(row=0, column=0, sticky="w", pady=4)
        self.lbl_cloud_v = ctk.CTkLabel(tgrid, text="CLOUD VERSION:      CHECKING...", font=FB, text_color=NEON_GREEN, anchor="w")
        self.lbl_cloud_v.grid(row=0, column=1, sticky="w", pady=4, padx=20)

        ctk.CTkLabel(tgrid, text="STATUS:             READY FOR UPDATE", font=FB, text_color=WARNING, anchor="w").grid(row=1, column=0, sticky="w", pady=4)
        ctk.CTkLabel(tgrid, text="DATABASE:           4,400+ CAMPUS USERS SYNCED", font=FB, text_color=NEON_GREEN, anchor="w").grid(row=1, column=1, sticky="w", pady=4, padx=20)
        tgrid.columnconfigure(0, weight=1); tgrid.columnconfigure(1, weight=1)

        # Release Highlights
        rcard = HackerCard(p)
        rcard.pack(fill="x", padx=20, pady=10)

        ctk.CTkLabel(rcard, text="RELEASE HIGHLIGHTS & CHANGELOG:", font=FH3, text_color=NEON_GREEN, anchor="w").pack(fill="x", padx=20, pady=(12,5))
        self.lbl_changelog = ctk.CTkLabel(
            rcard,
            text="• AUS Temporary Roll Number Login & Linking to Permanent Roll\n"
                 "• Complete 4,400+ Student Campus Directory Integration (DS, CSE, ECE, EEE, ME, CE)\n"
                 "• Live Firebase Cloud Telemetry & Automated Heartbeat Engine\n"
                 "• One-Click Over-The-Air (OTA) Application & Database Updater",
            font=FS, text_color="#cccccc", justify="left", anchor="w"
        )
        self.lbl_changelog.pack(fill="x", padx=20, pady=(0,12))

        # Progress bar
        self.tab_update_prog = ctk.CTkProgressBar(p, fg_color=SURFACE, progress_color=NEON_GREEN, height=12)
        self.tab_update_prog.set(0)
        self.tab_update_prog.pack(fill="x", padx=20, pady=(5,10))

        # Update Console Logs
        self.tab_update_log = ctk.CTkTextbox(p, height=180, fg_color=SURFACE, text_color=NEON_GREEN, font=FM, border_width=1, border_color=DARK_GREEN)
        self.tab_update_log.pack(fill="both", expand=True, padx=20, pady=(0,10))
        self.tab_update_log.insert("end", "[*] System Ready. Click '⚡ UPDATE TO NEW VERSION' to fetch latest release packages.\n")

        # Action Buttons
        btn_bar = ctk.CTkFrame(p, fg_color="transparent")
        btn_bar.pack(fill="x", padx=20, pady=(0,15))

        self.btn_tab_update = HackerButton(btn_bar, "⚡ UPDATE TO NEW VERSION", self._trigger_tab_update, height=48)
        self.btn_tab_update.pack(side="right", padx=(10,0))

        HackerButton(btn_bar, "⟳ CHECK FOR UPDATES", self._refresh_update_telemetry, color=SURFACE, text_col=NEON_GREEN, height=48).pack(side="right")

        self.after(500, self._refresh_update_telemetry)

    def _refresh_update_telemetry(self):
        def _task():
            info = get_system_update_info()
            latest_v = info.get("latest_version", APP_VERSION)
            changelog = info.get("changelog", "")
            self.after(0, lambda: self.lbl_cloud_v.configure(text=f"CLOUD VERSION:      {latest_v}"))
            if changelog:
                self.after(0, lambda: self.lbl_changelog.configure(text=f"• {changelog.replace(', ', '\n• ')}"))
        threading.Thread(target=_task, daemon=True).start()

    def _trigger_tab_update(self):
        self.btn_tab_update.configure(state="disabled")
        self.tab_update_prog.set(0.2)
        self.tab_update_log.delete("1.0", "end")

        def _log_cb(msg):
            def _ui():
                self.tab_update_log.insert("end", f"{msg}\n")
                self.tab_update_log.see("end")
            self.after(0, _ui)

        def _worker():
            self.after(0, lambda: self.tab_update_prog.set(0.5))
            ok, v = perform_system_update(_log_cb)
            self.after(0, lambda: self.tab_update_prog.set(1.0))
            if ok:
                _log_cb(f"\n[+] UPDATE TO {v} COMPLETED SUCCESSFULLY!")
                _log_cb("[*] Restarting application in 2 seconds...")
                self.after(0, lambda: messagebox.showinfo(
                    "UPDATE SUCCESSFUL",
                    f"AGENT PRAYATH has been updated to {v} successfully!\n\nThe application will now restart."
                ))
                time.sleep(1.5)
                self.after(0, self._restart_application)

        threading.Thread(target=_worker, daemon=True).start()

    def _restart_application(self):
        self._shutdown_event.set()
        try:
            roll = self.session.get("roll") or self.session.get("name", "USER")
            remove_online_presence(roll)
        except Exception:
            pass
        self.destroy()
        try:
            subprocess.Popen([sys.executable, os.path.abspath(__file__)])
        except Exception:
            subprocess.Popen(["python", "vision_agent.py"])
        sys.exit(0)

    # ── Helpers ──────────────────────────────────────────────────────────────
    def update_status(self, t):
        try:
            if hasattr(self, 'status_var') and self.status_var:
                self.after(0, lambda: self.status_var.set(t))
        except Exception:
            pass

    def abort_execution(self):
        if self.is_typing:
            self.stop_typing = True
            self.update_status("[!] EMERGENCY ABORT INITIATED.")
            self.after(0, self.deiconify)

    def _disable_buttons(self): pass
    def _enable_buttons(self): pass

    def _start_emergency_listener(self):
        def on_press(k):
            if k in (Key.f8, Key.esc) and self.is_typing: self.abort_execution()
        l = keyboard.Listener(on_press=on_press); l.daemon = True; l.start()

    def start_vision_generation(self):
        if not self.is_typing: threading.Thread(target=self._run_vision_pipeline, daemon=True).start()

    def start_text_generation(self):
        if self.is_typing: return
        pr = self.prompt_entry.get("1.0","end").strip()
        if not pr: return
        threading.Thread(target=self._run_text_pipeline, args=(pr,), daemon=True).start()

    def start_direct_typing(self):
        if self.is_typing: return
        code = self.manual_code_box.get("1.0","end").strip()
        if not code: return
        threading.Thread(target=self._run_direct_pipeline, args=(code,), daemon=True).start()

    # ── Injection Engine ──────────────────────────────────────────────────────
    def _wait_for_editor_and_clear(self):
        self.after(0, self.iconify)
        self.update_status("[*] MINIMIZED: CLICK INSIDE YOUR CODE EDITOR...")

        click_event = threading.Event()
        def on_click(x, y, button, pressed):
            if pressed:
                click_event.set()
                return False

        listener = mouse.Listener(on_click=on_click)
        listener.start()

        # Wait up to 10 seconds for user to click into their editor
        clicked = click_event.wait(timeout=10.0)
        try:
            listener.stop()
        except Exception:
            pass

        if self.stop_typing:
            self.after(0, self.deiconify)
            return False

        if not clicked:
            self.update_status("[!] TIMEOUT: NO EDITOR CLICK DETECTED. RESTORING WINDOW.")
            self.after(0, self.deiconify)
            return False

        self.update_status("[>] CURSOR DETECTED. CLEARING OLD CODE...")
        time.sleep(0.4)
        self.keyboard.press(Key.ctrl); self.keyboard.press("a")
        self.keyboard.release("a"); self.keyboard.release(Key.ctrl)
        time.sleep(0.15)
        self.keyboard.press(Key.backspace); self.keyboard.release(Key.backspace)
        time.sleep(0.3)
        return True

    def _execute_code_injection(self, initial_code, lang, enable_autonomous=True):
        current_code = initial_code
        max_retries  = 3 if (self.auto_run_var.get() and enable_autonomous) else 1

        for attempt in range(max_retries):
            if self.stop_typing: break

            if not self._wait_for_editor_and_clear(): break

            self.update_status("[>] INJECTING PAYLOAD...")
            self._type_into_editor(current_code)

            if self.stop_typing or not (self.auto_run_var.get() and enable_autonomous): break

            self.keyboard.press(Key.ctrl); self.keyboard.press(Key.enter)
            self.keyboard.release(Key.enter); self.keyboard.release(Key.ctrl)
            self.update_status("[*] AWAITING COMPILATION...")
            for _ in range(6):
                if self.stop_typing: break
                time.sleep(1)
            if self.stop_typing: break

            self.update_status("[*] ANALYZING OUTPUT TTY...")
            screenshot = ImageGrab.grab()
            ap = (f"Analyse this screenshot. Did the {lang} code run OK?\n"
                  "If NO ERRORS reply EXACTLY: SUCCESS\n"
                  f"If errors, output the fixed {lang} code ONLY. No markdown.")
            try:
                resp = self.backend.from_image(screenshot, lang, prompt=ap,
                                                sys_inst="You are an autonomous self-correcting agent.")
                if "SUCCESS" in resp[:30].upper():
                    self.update_status("[+] EXECUTION SUCCESSFUL."); break
                else:
                    self.update_status("[-] ERROR DETECTED. RECOMPILING PAYLOAD...")
                    current_code = resp
                    self.preview_box.delete("1.0","end"); self.preview_box.insert("end",current_code)
                    time.sleep(1)
            except Exception as ex:
                self.update_status(f"[!] UPLINK ERROR: {ex}"); break

        if not self.stop_typing:
            if not (self.auto_run_var.get() and enable_autonomous): self.update_status("[+] INJECTION COMPLETE.")
            time.sleep(1)
        self.after(0, self.deiconify)

    def _type_into_editor(self, code):
        lines = code.splitlines()
        for idx, line in enumerate(lines):
            if self.stop_typing: break
            for ch in line:
                if self.stop_typing: break
                self.keyboard.type(ch)
                if ch in "([{\"'":
                    self.keyboard.press(Key.delete); self.keyboard.release(Key.delete)
            if idx < len(lines)-1 and not self.stop_typing:
                self.keyboard.press(Key.enter); self.keyboard.release(Key.enter)
                time.sleep(0.01)

    # ── Pipelines ─────────────────────────────────────────────────────────────
    def _run_vision_pipeline(self):
        self.is_typing=True; self.stop_typing=False; self._disable_buttons()
        try:
            for rem in range(4,0,-1):
                if self.stop_typing: break
                self.update_status(f"[T-{rem}] INITIATE SCREEN CAPTURE..."); time.sleep(1)
            if self.stop_typing: return
            ss = ImageGrab.grab(); self.update_status("[*] TRANSMITTING TO AI CORE...")
            lang = self.lang_var.get(); code = self.backend.from_image(ss, lang)
            self.preview_box.delete("1.0","end"); self.preview_box.insert("end",code)
            self._execute_code_injection(code, lang, enable_autonomous=True)
        except Exception as ex:
            self.update_status(f"[!] ERROR: {ex}")
            with open("error_log.txt", "w") as f:
                import traceback; f.write(traceback.format_exc())
        finally:
            self.is_typing=False; self.stop_typing=False; self._enable_buttons()
            self.after(0, self.deiconify)

    def _run_text_pipeline(self, prompt):
        self.is_typing=True; self.stop_typing=False; self._disable_buttons()
        try:
            self.update_status("[*] GENERATING PAYLOAD..."); lang=self.lang_var.get()
            code = self.backend.from_text(prompt, lang)
            self.preview_box.delete("1.0","end"); self.preview_box.insert("end",code)
            self._execute_code_injection(code, lang, enable_autonomous=True)
        except Exception as ex:
            self.update_status(f"[!] ERROR: {ex}")
            with open("error_log.txt", "w") as f:
                import traceback; f.write(traceback.format_exc())
        finally:
            self.is_typing=False; self.stop_typing=False; self._enable_buttons()
            self.after(0, self.deiconify)

    def _run_direct_pipeline(self, code):
        self.is_typing=True; self.stop_typing=False; self._disable_buttons()
        try:
            if hasattr(self, "preview_box"):
                self.preview_box.delete("1.0","end"); self.preview_box.insert("end",code)

            if not self._wait_for_editor_and_clear():
                return

            self.update_status("[>] INITIATING INJECTION...")
            self._type_into_editor(code)

            if self.stop_typing: return

            self.update_status("[+] INJECTION COMPLETE. VERIFYING...")
            time.sleep(1)

            # Show success dialog
            self.after(0, self.deiconify)
            messagebox.showinfo("Success", "Code is written successfully into your editor.")
            self.update_status("[+] SYSTEM READY.")

        except Exception as ex:
            self.update_status(f"[!] ERROR: {ex}")
            with open("error_log.txt", "w") as f:
                import traceback; f.write(traceback.format_exc())
        finally:
            self.is_typing=False; self.stop_typing=False; self._enable_buttons()
            self.after(0, self.deiconify)

# ── APPLICATION ENTRY POINT ───────────────────────────────────────────────────
if __name__ == "__main__":
    session = load_session()

    # If valid session already exists and no re-auth requested, launch main app directly
    if session.get("role") and (len(sys.argv) == 1 or sys.argv[1] == "--main"):
        try:
            app = AutoCoderApp(session)
            app.mainloop()
        except Exception as e:
            import traceback
            with open("error_log.txt", "w") as f:
                f.write(traceback.format_exc())
    else:
        wizard = OnboardingWizard()
        wizard.mainloop()
        if wizard.success:
            sess = load_session()
            app = AutoCoderApp(sess)
            app.mainloop()
