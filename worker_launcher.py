#!/usr/bin/env python3
"""
Simple GUI launcher for ChaarFM Remote Worker
Provides a user-friendly interface for entering server URL and pairing code
"""

import sys
import os
import subprocess
import tkinter as tk
from tkinter import messagebox, ttk

def run_worker():
    """Launch the worker with the provided settings."""
    url = url_entry.get().strip()
    code = code_entry.get().strip()
    
    if not url:
        messagebox.showerror("Error", "Server URL is required")
        return
    
    if not code:
        messagebox.showerror("Error", "Pairing code is required")
        return
    
    # Determine if we're running as an executable or script
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        worker_path = sys.executable
    else:
        # Running as script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        worker_path = os.path.join(script_dir, 'remote_worker.py')
        if not os.path.exists(worker_path):
            messagebox.showerror("Error", f"Worker script not found: {worker_path}")
            return
    
    # Launch worker in a new terminal/console window
    try:
        if sys.platform == 'win32':
            # Windows: open in new console window
            subprocess.Popen([
                'cmd', '/c', 'start', 'cmd', '/k',
                f'"{worker_path}" --url "{url}" --code "{code}"'
            ], shell=True)
        elif sys.platform == 'darwin':
            # macOS: open in new Terminal window
            script = f'cd "{os.path.dirname(worker_path)}" && python3 "{worker_path}" --url "{url}" --code "{code}"'
            subprocess.Popen([
                'osascript', '-e',
                f'tell application "Terminal" to do script "{script}"'
            ])
        else:
            # Linux: open in new terminal
            subprocess.Popen([
                'xterm', '-e',
                f'python3 "{worker_path}" --url "{url}" --code "{code}"; read -p "Press Enter to close..."'
            ])
        
        messagebox.showinfo("Success", "Worker launched! Check the terminal window for status.")
        root.quit()
    except Exception as e:
        messagebox.showerror("Error", f"Failed to launch worker: {e}")

# Create GUI
root = tk.Tk()
root.title("ChaarFM Remote Worker Launcher")
root.geometry("500x200")
root.resizable(False, False)

# Style
style = ttk.Style()
style.theme_use('clam')

# Instructions
instructions = tk.Label(
    root,
    text="Enter your server URL and pairing code to start the worker",
    font=('Arial', 10),
    pady=10
)
instructions.pack()

# Server URL
url_frame = tk.Frame(root, pady=5)
url_frame.pack(fill=tk.X, padx=20)
tk.Label(url_frame, text="Server URL:", width=15, anchor='w').pack(side=tk.LEFT)
url_entry = tk.Entry(url_frame, width=40)
url_entry.insert(0, "https://chaarfm.onrender.com")
url_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

# Pairing Code
code_frame = tk.Frame(root, pady=5)
code_frame.pack(fill=tk.X, padx=20)
tk.Label(code_frame, text="Pairing Code:", width=15, anchor='w').pack(side=tk.LEFT)
code_entry = tk.Entry(code_frame, width=40)
code_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

# Info label
info_label = tk.Label(
    root,
    text="Tip: You can run multiple workers with the same code to speed up processing!",
    font=('Arial', 8),
    fg='gray',
    pady=5
)
info_label.pack()

# Buttons
button_frame = tk.Frame(root, pady=10)
button_frame.pack()

launch_btn = tk.Button(
    button_frame,
    text="Launch Worker",
    command=run_worker,
    bg='#4CAF50',
    fg='white',
    font=('Arial', 12, 'bold'),
    padx=20,
    pady=5
)
launch_btn.pack(side=tk.LEFT, padx=5)

quit_btn = tk.Button(
    button_frame,
    text="Quit",
    command=root.quit,
    bg='#f44336',
    fg='white',
    font=('Arial', 12),
    padx=20,
    pady=5
)
quit_btn.pack(side=tk.LEFT, padx=5)

# Focus on code entry
code_entry.focus()

# Run GUI
root.mainloop()
