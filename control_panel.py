import tkinter as tk
from tkinter import ttk, messagebox
import subprocess
import webbrowser
import os
import sys
from pathlib import Path

# Configuration
PROJECT_ROOT = Path(__file__).parent.absolute()
CHAARFM_SCRIPT = PROJECT_ROOT / "server_user.py"
VECTOR_UI_SCRIPT = PROJECT_ROOT / "pipeline_server.py"

# Theme Colors
BG_COLOR = "#0a0a0a"
CARD_BG = "#1a1a2e"
TEXT_COLOR = "#e0e0e0"
ACCENT_COLOR = "#f093fb"
DANGER_COLOR = "#f5576c"
SUCCESS_COLOR = "#4cd964"

class ControlPanel(tk.Tk):
    def __init__(self):
        super().__init__()
        
        self.title("ChaarFM Control Panel")
        self.geometry("400x500")
        self.configure(bg=BG_COLOR)
        self.resizable(False, False)
        
        # Header
        header = tk.Frame(self, bg=BG_COLOR)
        header.pack(fill="x", pady=20)
        
        title_label = tk.Label(
            header, 
            text="chaar.fm", 
            font=("Helvetica", 24, "bold"),
            bg=BG_COLOR,
            fg=ACCENT_COLOR
        )
        title_label.pack()
        
        subtitle = tk.Label(
            header,
            text="Control Center (Supabase Edition)",
            font=("Helvetica", 12),
            bg=BG_COLOR,
            fg="gray"
        )
        subtitle.pack()
        
        # Buttons Container
        self.container = tk.Frame(self, bg=BG_COLOR)
        self.container.pack(fill="both", expand=True, padx=40)
        
        self.create_button("Start ChaarFM App", "🚀", self.start_chaarfm, SUCCESS_COLOR)
        self.create_button("Start Vectorising UI", "🎛️", self.start_vector_ui, "#9b59b6")
        self.create_button("Public Tunnel (ngrok)", "🌐", self.start_tunnel, "#e67e22")
        self.create_button("Configure Project", "⚙️", self.configure_dirs, "#f1c40f")
        
        # Footer
        footer = tk.Label(
            self,
            text=f"Running in: {PROJECT_ROOT.name}",
            bg=BG_COLOR,
            fg="gray",
            font=("Helvetica", 8)
        )
        footer.pack(pady=10)

    def create_button(self, text, icon, command, color):
        btn_frame = tk.Frame(self.container, bg=CARD_BG, pady=2)
        btn_frame.pack(fill="x", pady=8)
        
        btn = tk.Button(
            btn_frame,
            text=f"{icon}  {text}",
            font=("Helvetica", 14),
            bg=CARD_BG,
            fg=text == "Start ChaarFM App" and "black" or "white", # simple contrast check
            activebackground=color,
            activeforeground="white",
            relief="flat",
            command=command,
            highlightthickness=0,
            bd=0,
            cursor="hand2"
        )
        # Hacky styling for standard buttons on Mac (they are restrictive)
        btn.config(highlightbackground=color)
        btn.pack(fill="both", expand=True, ipady=10)

    def run_in_terminal(self, command, title="Process"):
        """Run command in a new Mac Terminal window."""
        script = f'tell application "Terminal" to do script "cd {PROJECT_ROOT} && {command}"'
        try:
            subprocess.run(["osascript", "-e", script], check=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to launch terminal: {e}")

    def start_chaarfm(self):
        self.run_in_terminal("python3 server_user.py", "ChaarFM App")
        self.after(2000, lambda: webbrowser.open("http://localhost:5001"))

    def start_vector_ui(self):
        self.run_in_terminal("python3 pipeline_server.py", "Vector UI")
        self.after(2000, lambda: webbrowser.open("http://localhost:5002"))

    def start_tunnel(self):
        self.run_in_terminal("ngrok http 5001", "Public Tunnel")

    def configure_dirs(self):
        """Invoke the config manager GUI."""
        try:
            subprocess.Popen(["python3", "config_manager.py"])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open config: {e}")

if __name__ == "__main__":
    app = ControlPanel()
    app.mainloop()
