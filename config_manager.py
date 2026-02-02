import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional
import dotenv

CONFIG_FILE = "chaarfm_config.json"
ENV_FILE = ".env"

DEFAULT_CONFIG = {
    "folders": {},        # source_name -> local_path
    "collections": {},    # source_name -> collection_name
    "use_combined": True
}

# ============================================================================
# CONFIG LOGIC
# ============================================================================

def load_config() -> Dict:
    """Load configuration from JSON file."""
    if not os.path.exists(CONFIG_FILE):
        return DEFAULT_CONFIG.copy()
    
    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
            if "folders" not in config: config["folders"] = {}
            if "collections" not in config: config["collections"] = {}
            return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return DEFAULT_CONFIG.copy()

def save_config(config: Dict):
    """Save configuration to JSON file."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)
        print(f"✅ Configuration saved to {CONFIG_FILE}")
    except Exception as e:
        print(f"❌ Error saving config: {e}")

def load_env_vars():
    """Load .env file."""
    dotenv.load_dotenv(ENV_FILE)

def save_env_vars(vars_dict: Dict[str, str]):
    """Update .env file with new variables."""
    # Read existing
    lines = []
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE, "r") as f:
            lines = f.readlines()
            
    existing_keys = {}
    for i, line in enumerate(lines):
        if "=" in line:
            key = line.split("=", 1)[0].strip()
            existing_keys[key] = i
            
    for key, val in vars_dict.items():
        line = f'{key}="{val}"\n'
        if key in existing_keys:
            lines[existing_keys[key]] = line
        else:
            lines.append(line)
            
    with open(ENV_FILE, "w") as f:
        f.writelines(lines)
    
    # Reload immediately
    dotenv.load_dotenv(ENV_FILE, override=True)
    print("✅ Environment variables saved to .env")

def add_source(name: str, path: str):
    """Add a new music source/folder."""
    config = load_config()
    abs_path = str(Path(path).expanduser().absolute())
    config["folders"][name] = abs_path
    config["collections"][name] = f"music_{name}"
    if config.get("use_combined", True):
        config["collections"]["combined"] = "music_combined"
    save_config(config)

def remove_source(name: str):
    """Remove a music source."""
    config = load_config()
    if name in config["folders"]: del config["folders"][name]
    if name in config["collections"]: del config["collections"][name]
    save_config(config)

def get_collection_roots() -> Dict[str, str]:
    config = load_config()
    roots = {}
    for name, path in config["folders"].items():
        col_name = config["collections"].get(name, f"music_{name}")
        roots[col_name] = path
        roots[f"{col_name}_p03"] = path
    if config["folders"]:
        primary_path = list(config["folders"].values())[0]
        roots["music_combined"] = primary_path 
    return roots

# ============================================================================
# GUI TOOLS
# ============================================================================

def configure_interactive():
    """Launch a mini GUI to manage folders and cloud credentials."""
    import tkinter as tk
    from tkinter import messagebox, simpledialog, filedialog, ttk
    
    root = tk.Tk()
    root.title("ChaarFM Control Panel")
    root.geometry("600x500")
    
    style = ttk.Style()
    style.theme_use('clam')
    
    # --- Local Music Folders ---
    lbl = tk.Label(root, text="Local Music Folders", font=("Helvetica", 14, "bold"))
    lbl.pack(pady=(10, 5))
    
    frame = tk.Frame(root)
    frame.pack(fill="both", expand=True, padx=20, pady=5)
    
    listbox = tk.Listbox(frame, font=("Courier", 12), height=8)
    listbox.pack(side="left", fill="both", expand=True)
    
    scrollbar = tk.Scrollbar(frame, orient="vertical", command=listbox.yview)
    scrollbar.pack(side="right", fill="y")
    listbox.config(yscrollcommand=scrollbar.set)
    
    def refresh_list():
        listbox.delete(0, tk.END)
        config = load_config()
        for name, path in config["folders"].items():
            listbox.insert(tk.END, f"{name}: {path}")
    refresh_list()
    
    # --- Action Buttons ---
    btn_frame = tk.Frame(root)
    btn_frame.pack(pady=10)
    
    def add_click():
        path = filedialog.askdirectory(title="Select Music Folder")
        if not path: return
        name = simpledialog.askstring("Source Name", "Enter name (e.g. 'russhil'):")
        if not name: return
        add_source(name.lower().replace(" ", "_"), path)
        refresh_list()
        
    def remove_click():
        sel = listbox.curselection()
        if not sel: return
        item = listbox.get(sel[0])
        name = item.split(":")[0]
        if messagebox.askyesno("Confirm", f"Remove '{name}'?"):
            remove_source(name)
            refresh_list()
            
    tk.Button(btn_frame, text="➕ Add Folder", command=add_click, bg="#e0e0e0").pack(side="left", padx=5)
    tk.Button(btn_frame, text="➖ Remove", command=remove_click, bg="#ffcccc").pack(side="left", padx=5)
    
    # --- Cloud Configuration ---
    tk.Label(root, text="Cloud Configuration (Supabase & R2)", font=("Helvetica", 14, "bold")).pack(pady=(20, 5))
    
    cloud_frame = tk.Frame(root)
    cloud_frame.pack(pady=10)
    
    def open_cloud_setup():
        # Load current env
        dotenv.load_dotenv(ENV_FILE)
        
        cwin = tk.Toplevel(root)
        cwin.title("Cloud Credentials")
        cwin.geometry("500x350")
        
        tk.Label(cwin, text="Supabase Connection String (DATABASE_URL):").pack(anchor="w", padx=20, pady=(10,0))
        db_var = tk.StringVar(value=os.environ.get("DATABASE_URL", ""))
        tk.Entry(cwin, textvariable=db_var, width=50).pack(padx=20, pady=5)
        
        tk.Label(cwin, text="Optional: Cloudflare R2 / S3 Endpoint:").pack(anchor="w", padx=20, pady=(10,0))
        s3_ep_var = tk.StringVar(value=os.environ.get("S3_ENDPOINT", ""))
        tk.Entry(cwin, textvariable=s3_ep_var, width=50).pack(padx=20, pady=5)
        
        tk.Label(cwin, text="Optional: S3 Access Key:").pack(anchor="w", padx=20, pady=(10,0))
        s3_key_var = tk.StringVar(value=os.environ.get("S3_ACCESS_KEY", ""))
        tk.Entry(cwin, textvariable=s3_key_var, width=50).pack(padx=20, pady=5)
        
        tk.Label(cwin, text="Optional: S3 Secret Key:").pack(anchor="w", padx=20, pady=(10,0))
        s3_sec_var = tk.StringVar(value=os.environ.get("S3_SECRET_KEY", ""))
        tk.Entry(cwin, textvariable=s3_sec_var, show="*", width=50).pack(padx=20, pady=5)

        def save_cloud():
            save_env_vars({
                "DATABASE_URL": db_var.get().strip(),
                "S3_ENDPOINT": s3_ep_var.get().strip(),
                "S3_ACCESS_KEY": s3_key_var.get().strip(),
                "S3_SECRET_KEY": s3_sec_var.get().strip()
            })
            messagebox.showinfo("Saved", "Credentials saved to .env")
            cwin.destroy()
            
        tk.Button(cwin, text="💾 Save Credentials", command=save_cloud, bg="#4cd964", font=("Helvetica", 12, "bold")).pack(pady=20)
    
    tk.Button(cloud_frame, text="☁️ Setup Credentials", command=open_cloud_setup, font=("Helvetica", 12)).pack()
    
    tk.Button(root, text="Done", command=root.destroy, width=20).pack(side="bottom", pady=20)
    
    root.mainloop()

if __name__ == "__main__":
    configure_interactive()
