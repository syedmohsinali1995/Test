"""
Entry point for the .exe version.
Starts the FastAPI server in a background thread,
then opens the browser automatically.
"""

import os
import sys
import time
import threading
import webbrowser
import tkinter as tk
from tkinter import messagebox

PORT = 8000
URL  = f"http://localhost:{PORT}"


def _resource(relative_path: str) -> str:
    """Get absolute path — works for both dev and PyInstaller bundle."""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)


def _start_server():
    """Run FastAPI/Uvicorn in a background thread."""
    # Change to the bundle directory so relative paths work
    os.chdir(_resource("."))
    os.makedirs("data", exist_ok=True)

    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, log_level="error")


def _wait_and_open():
    """Wait for server to be ready, then open the browser."""
    import urllib.request
    for _ in range(30):          # try for up to 30 seconds
        try:
            urllib.request.urlopen(f"{URL}/health", timeout=1)
            webbrowser.open(URL)
            return
        except Exception:
            time.sleep(1)
    messagebox.showerror("خرابی", "سرور شروع نہیں ہو سکا۔ دوبارہ کوشش کریں۔")


def main():
    # System tray / GUI window (simple)
    root = tk.Tk()
    root.title("🏠 AI کالنگ ایجنٹ")
    root.geometry("380x200")
    root.resizable(False, False)
    root.configure(bg="#0f2027")

    tk.Label(root, text="🏠 AI Real Estate Calling Agent",
             font=("Arial", 14, "bold"), fg="#00d4aa", bg="#0f2027").pack(pady=20)
    tk.Label(root, text="سرور شروع ہو رہا ہے...",
             font=("Arial", 11), fg="white", bg="#0f2027").pack()

    status_var = tk.StringVar(value="براہ کرم انتظار کریں...")
    tk.Label(root, textvariable=status_var,
             font=("Arial", 10), fg="#adb5bd", bg="#0f2027").pack(pady=5)

    def open_browser():
        webbrowser.open(URL)

    btn = tk.Button(root, text="براؤزر میں کھولیں", command=open_browser,
                    bg="#00d4aa", fg="white", font=("Arial", 10, "bold"),
                    relief="flat", padx=16, pady=6, cursor="hand2")
    btn.pack(pady=10)

    tk.Button(root, text="بند کریں", command=root.quit,
              bg="#c0392b", fg="white", font=("Arial", 9),
              relief="flat", padx=12, pady=4).pack()

    # Start server thread
    server_thread = threading.Thread(target=_start_server, daemon=True)
    server_thread.start()

    # Open browser after server is ready
    def _open_after_ready():
        import urllib.request
        for _ in range(30):
            try:
                urllib.request.urlopen(f"{URL}/health", timeout=1)
                status_var.set(f"✅ تیار — {URL}")
                root.after(500, open_browser)
                return
            except Exception:
                time.sleep(1)
        status_var.set("❌ سرور شروع نہیں ہو سکا")

    threading.Thread(target=_open_after_ready, daemon=True).start()
    root.mainloop()


if __name__ == "__main__":
    main()
