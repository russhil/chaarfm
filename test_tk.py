
import tkinter as tk
from tkinter import filedialog, messagebox

def test_gui():
    try:
        root = tk.Tk()
        root.withdraw()
        print("Tkinter initialized successfully")
        root.destroy()
    except Exception as e:
        print(f"Tkinter failed: {e}")

if __name__ == "__main__":
    test_gui()
