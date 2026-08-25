#!/usr/bin/env python3
"""Bruteforce d'un PIN (4 chiffres) sur un fichier ZIP, PDF ou GPG protege."""

import argparse
import itertools
import shutil
import subprocess
import sys
import threading
import zipfile


def try_zip_pin(path, pin):
    with zipfile.ZipFile(path) as zf:
        name = zf.namelist()[0]
        try:
            zf.read(name, pwd=pin.encode())
            return True
        except RuntimeError:
            return False
        except Exception:
            return False


def try_pdf_pin(path, pin):
    try:
        from pypdf import PdfReader
    except ImportError:
        from PyPDF2 import PdfReader

    reader = PdfReader(path)
    if not reader.is_encrypted:
        return True
    result = reader.decrypt(pin)
    return bool(result)


def try_gpg_pin(path, pin):
    if shutil.which("gpg") is None:
        raise RuntimeError("gpg n'est pas installe (requis pour les fichiers .gpg).")

    result = subprocess.run(
        [
            "gpg", "--batch", "--yes", "--pinentry-mode", "loopback",
            "--passphrase", pin, "--decrypt", "--output", "/dev/null", path,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def get_checker(path):
    lower = path.lower()
    if lower.endswith(".gpg"):
        return try_gpg_pin
    elif lower.endswith(".zip"):
        return try_zip_pin
    elif lower.endswith(".pdf"):
        return try_pdf_pin
    return None


def bruteforce(path, length, stop_event=None, on_progress=None):
    check = get_checker(path)
    if check is None:
        print("Type de fichier non supporte (attendu .zip, .pdf ou .gpg)")
        sys.exit(1)

    total = 10 ** length
    for i in range(total):
        if stop_event is not None and stop_event.is_set():
            return None
        pin = str(i).zfill(length)
        if check(path, pin):
            if on_progress:
                on_progress(pin, i, total, found=True)
            else:
                print(f"PIN trouve : {pin}")
            return pin
        if on_progress:
            on_progress(pin, i, total, found=False)
        elif i % 1000 == 0:
            print(f"...essai {pin} ({i}/{total})", end="\r")

    if not on_progress:
        print("Aucun PIN trouve dans la plage testee.")
    return None


def launch_gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    BG = "#0d1117"
    PANEL = "#161b22"
    FG = "#c9d1d9"
    ACCENT = "#39ff88"
    ACCENT_DIM = "#1fae5c"
    DANGER = "#ff5c5c"
    MONO = ("Consolas", 10) if sys.platform == "win32" else ("Courier New", 11)
    MONO_BOLD = (MONO[0], MONO[1], "bold")

    root = tk.Tk()
    root.title("⚡ PIN Bruteforcer")
    root.geometry("520x460")
    root.minsize(520, 460)
    root.configure(bg=BG)

    style = ttk.Style()
    style.theme_use("clam")
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG, font=MONO)
    style.configure("Title.TLabel", background=BG, foreground=ACCENT, font=(MONO[0], 18, "bold"))
    style.configure("Sub.TLabel", background=BG, foreground="#8b949e", font=(MONO[0], 9))
    style.configure("TEntry", fieldbackground=PANEL, foreground=FG, insertcolor=ACCENT, borderwidth=0)
    style.configure("TSpinbox", fieldbackground=PANEL, foreground=FG, arrowcolor=ACCENT, borderwidth=0)
    style.configure(
        "Accent.TButton",
        background=ACCENT_DIM, foreground="#0d1117", font=MONO_BOLD,
        borderwidth=0, focusthickness=0, padding=8,
    )
    style.map("Accent.TButton", background=[("active", ACCENT), ("disabled", "#30363d")],
              foreground=[("disabled", "#6e7681")])
    style.configure(
        "Danger.TButton",
        background="#301717", foreground=DANGER, font=MONO_BOLD,
        borderwidth=0, focusthickness=0, padding=8,
    )
    style.map("Danger.TButton", background=[("active", "#4a1f1f"), ("disabled", "#21262d")],
              foreground=[("disabled", "#6e7681")])
    style.configure("Cool.Horizontal.TProgressbar", troughcolor=PANEL, background=ACCENT,
                     lightcolor=ACCENT, darkcolor=ACCENT, borderwidth=0, thickness=14)

    state = {"stop_event": None, "thread": None}

    path_var = tk.StringVar()
    length_var = tk.IntVar(value=4)
    status_var = tk.StringVar(value="En attente d'un fichier...")
    percent_var = tk.StringVar(value="0%")

    def log(line):
        console.configure(state="normal")
        console.insert("end", line + "\n")
        console.see("end")
        console.configure(state="disabled")

    def choose_file():
        chosen = filedialog.askopenfilename(
            title="Choisir un fichier ZIP, PDF ou GPG",
            filetypes=[("ZIP, PDF ou GPG", "*.zip *.pdf *.gpg"), ("Tous les fichiers", "*.*")],
        )
        if chosen:
            path_var.set(chosen)
            log(f"[*] Fichier selectionne : {chosen}")

    def on_progress(pin, i, total, found):
        def apply():
            percent = (i / total) * 100
            progress["value"] = percent
            percent_var.set(f"{percent:.1f}%")
            if found:
                status_var.set(f"PIN trouve : {pin}")
                log(f"[+] SUCCES -> {pin}")
            else:
                status_var.set(f"essai en cours : {pin}")
                if i % 250 == 0:
                    log(f"[.] {pin}  ({i}/{total})")
        root.after(0, apply)

    def worker(path, length, stop_event):
        error = None
        result = None
        try:
            result = bruteforce(path, length, stop_event=stop_event, on_progress=on_progress)
        except Exception as exc:
            error = str(exc)

        def finish():
            start_btn.config(state="normal")
            stop_btn.config(state="disabled")
            if error:
                status_var.set("Erreur.")
                log(f"[!] Erreur : {error}")
                messagebox.showerror("Erreur", error)
            elif stop_event.is_set():
                status_var.set("Arrete par l'utilisateur.")
                log("[!] Arrete par l'utilisateur.")
            elif result:
                status_var.set(f"PIN trouve : {result}")
                messagebox.showinfo("Succes", f"PIN trouve : {result}")
            else:
                status_var.set("Aucun PIN trouve.")
                log("[!] Aucun PIN trouve dans la plage testee.")
                messagebox.showwarning("Termine", "Aucun PIN trouve dans la plage testee.")

        root.after(0, finish)

    def start():
        path = path_var.get()
        if not path:
            messagebox.showerror("Erreur", "Choisis d'abord un fichier.")
            return
        if get_checker(path) is None:
            messagebox.showerror("Erreur", "Type de fichier non supporte (.zip, .pdf ou .gpg uniquement).")
            return
        if path.lower().endswith(".gpg") and shutil.which("gpg") is None:
            messagebox.showerror("Erreur", "gpg n'est pas installe sur ce systeme.")
            return
        length = length_var.get()
        if length < 1 or length > 8:
            messagebox.showerror("Erreur", "Longueur de PIN invalide (1 a 8).")
            return

        progress["value"] = 0
        percent_var.set("0%")
        status_var.set("Demarrage...")
        console.configure(state="normal")
        console.delete("1.0", "end")
        console.configure(state="disabled")
        log(f"[*] Demarrage du bruteforce ({length} chiffres, {10 ** length} combinaisons)")

        stop_event = threading.Event()
        state["stop_event"] = stop_event
        thread = threading.Thread(target=worker, args=(path, length, stop_event), daemon=True)
        state["thread"] = thread
        start_btn.config(state="disabled")
        stop_btn.config(state="normal")
        thread.start()

    def stop():
        if state["stop_event"] is not None:
            state["stop_event"].set()
        stop_btn.config(state="disabled")

    outer = ttk.Frame(root, padding=16)
    outer.pack(fill="both", expand=True)

    ttk.Label(outer, text="⚡ PIN BRUTEFORCER", style="Title.TLabel").pack(anchor="w")
    ttk.Label(outer, text="ZIP / PDF / GPG - usage local et autorise uniquement", style="Sub.TLabel").pack(
        anchor="w", pady=(0, 14)
    )

    file_row = ttk.Frame(outer)
    file_row.pack(fill="x", pady=4)
    ttk.Label(file_row, text="Fichier").pack(side="left")
    ttk.Entry(file_row, textvariable=path_var).pack(side="left", fill="x", expand=True, padx=8)
    ttk.Button(file_row, text="Parcourir", command=choose_file).pack(side="left")

    len_row = ttk.Frame(outer)
    len_row.pack(fill="x", pady=8)
    ttk.Label(len_row, text="Longueur du PIN").pack(side="left")
    ttk.Spinbox(len_row, from_=1, to=8, textvariable=length_var, width=5).pack(side="left", padx=8)

    btn_row = ttk.Frame(outer)
    btn_row.pack(fill="x", pady=(4, 10))
    start_btn = ttk.Button(btn_row, text="▶ Demarrer", style="Accent.TButton", command=start)
    start_btn.pack(side="left", fill="x", expand=True, padx=(0, 6))
    stop_btn = ttk.Button(btn_row, text="■ Arreter", style="Danger.TButton", command=stop, state="disabled")
    stop_btn.pack(side="left", fill="x", expand=True, padx=(6, 0))

    prog_row = ttk.Frame(outer)
    prog_row.pack(fill="x", pady=(0, 4))
    progress = ttk.Progressbar(
        prog_row, orient="horizontal", mode="determinate", style="Cool.Horizontal.TProgressbar"
    )
    progress.pack(side="left", fill="x", expand=True)
    ttk.Label(prog_row, textvariable=percent_var, width=6).pack(side="left", padx=(8, 0))

    ttk.Label(outer, textvariable=status_var, style="Sub.TLabel").pack(anchor="w", pady=(0, 8))

    console = tk.Text(
        outer, height=10, bg="#010409", fg=ACCENT, insertbackground=ACCENT,
        font=MONO, borderwidth=0, highlightthickness=1, highlightbackground="#21262d",
    )
    console.pack(fill="both", expand=True)
    console.configure(state="disabled")

    root.mainloop()


def main():
    parser = argparse.ArgumentParser(description="Bruteforce un PIN numerique sur un fichier ZIP/PDF/GPG protege.")
    parser.add_argument("file", nargs="?", help="Chemin du fichier ZIP, PDF ou GPG a debloquer")
    parser.add_argument("--length", type=int, default=4, help="Nombre de chiffres du PIN (defaut: 4)")
    parser.add_argument("--gui", action="store_true", help="Lancer l'interface graphique")
    args = parser.parse_args()

    if args.gui or not args.file:
        launch_gui()
    else:
        bruteforce(args.file, args.length)


if __name__ == "__main__":
    main()
