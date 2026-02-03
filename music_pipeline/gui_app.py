import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import random
import os
import sys
import queue
from dotenv import load_dotenv

# Import pipeline modules
# Assuming we are running this as a module (python -m music_pipeline.gui_app)
# or direct execution. We'll use relative imports if possible, or absolute if needed.
try:
    from .universe import extract_universe
    from .downloader import download_song
    from .tagger import tag_mp3
    from .vectorizer import vectorize_audio
    from .storage import upload_to_r2, store_vector_db
except ImportError:
    # Fallback for running script directly without -m
    from universe import extract_universe
    from downloader import download_song
    from tagger import tag_mp3
    from vectorizer import vectorize_audio
    from storage import upload_to_r2, store_vector_db

load_dotenv()

class TextRedirector:
    def __init__(self, queue, tag="stdout"):
        self.queue = queue
        self.tag = tag

    def write(self, str):
        self.queue.put({'action': 'log', 'data': (str, self.tag)})

    def flush(self):
        pass

class MusicPipelineApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Last.fm Music Vectorizer")
        self.geometry("900x800") # Increased height for logs
        
        # Session State
        self.username = None
        self.universe = []
        self.selected_tracks = []
        self.processing_queue = queue.Queue()
        
        # Redirect stdout/stderr
        sys.stdout = TextRedirector(self.processing_queue, "stdout")
        sys.stderr = TextRedirector(self.processing_queue, "stderr")
        
        # Container for frames
        self.container = ttk.Frame(self)
        self.container.pack(side="top", fill="both", expand=True, padx=10, pady=10)
        
        self.frames = {}
        for F in (LoginFrame, SelectionFrame, ProgressFrame):
            page_name = F.__name__
            frame = F(parent=self.container, controller=self)
            self.frames[page_name] = frame
            frame.grid(row=0, column=0, sticky="nsew")
            
        self.container.grid_rowconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
            
        # Log Console (Bottom)
        self.log_frame = ttk.LabelFrame(self, text="Console Logs")
        self.log_frame.pack(side="bottom", fill="x", padx=10, pady=10)
        
        self.log_text = scrolledtext.ScrolledText(self.log_frame, height=10, state='disabled', font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True)
        self.log_text.tag_config("stderr", foreground="red")
        
        self.show_frame("LoginFrame")
        
        # Check for message queue updates
        self.check_queue()

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()
        # Optional: Call a refresh/on_show method if it exists
        if hasattr(frame, "on_show"):
            frame.on_show()

    def check_queue(self):
        try:
            while True:
                msg = self.processing_queue.get_nowait()
                action = msg.get('action')
                data = msg.get('data')
                
                if action == 'log':
                    text, tag = data
                    self.log_text.config(state='normal')
                    self.log_text.insert(tk.END, text, tag)
                    self.log_text.see(tk.END)
                    self.log_text.config(state='disabled')

                elif action == 'universe_extracted':
                    self.universe = data
                    self.frames["LoginFrame"].stop_loading()
                    self.show_frame("SelectionFrame")
                    
                elif action == 'universe_error':
                    self.frames["LoginFrame"].stop_loading()
                    messagebox.showerror("Error", f"Failed to extract universe: {data}")
                    
                elif action == 'update_row':
                    # data = (index, column, value)
                    self.frames["ProgressFrame"].update_row(*data)
                    
                elif action == 'pipeline_complete':
                    self.frames["ProgressFrame"].finish_pipeline(data)
                    
        except queue.Empty:
            pass
        finally:
            self.after(50, self.check_queue) # Check faster for smoother logs


class LoginFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        label = ttk.Label(self, text="Enter Last.fm Username", font=("Helvetica", 16))
        label.pack(pady=20)
        
        self.username_entry = ttk.Entry(self)
        self.username_entry.pack(pady=10)
        self.username_entry.focus()
        
        # Songs per Artist Input
        limit_frame = ttk.Frame(self)
        limit_frame.pack(pady=5)
        ttk.Label(limit_frame, text="Songs per Artist (Deep Dive):").pack(side="left", padx=5)
        self.limit_entry = ttk.Entry(limit_frame, width=5)
        self.limit_entry.insert(0, "5")
        self.limit_entry.pack(side="left", padx=5)
        
        self.extract_btn = ttk.Button(self, text="Extract Universe", command=self.start_extraction)
        self.extract_btn.pack(pady=10)
        
        self.status_label = ttk.Label(self, text="")
        self.status_label.pack(pady=10)
        
        self.progress = ttk.Progressbar(self, mode='indeterminate')

    def start_extraction(self):
        username = self.username_entry.get().strip()
        if not username:
            messagebox.showwarning("Input Error", "Please enter a username")
            return
            
        try:
            limit = int(self.limit_entry.get())
            if limit <= 0: raise ValueError
        except ValueError:
            messagebox.showwarning("Input Error", "Please enter a valid positive integer for Songs per Artist")
            return
            
        self.controller.username = username
        self.extract_btn.config(state="disabled")
        self.status_label.config(text=f"Extracting universe for {username} (Limit: {limit})... This may take a while.")
        self.progress.pack(pady=10, fill='x', padx=50)
        self.progress.start()
        
        # Start thread
        threading.Thread(target=self.run_extraction, args=(username, limit), daemon=True).start()
        
    def run_extraction(self, username, limit):
        try:
            # Configurable limit could be added to UI, defaulting to 5 per artist for now
            tracks = extract_universe(username, limit_per_artist=limit)
            self.controller.processing_queue.put({'action': 'universe_extracted', 'data': tracks})
        except Exception as e:
            # Also log exception to console
            import traceback
            print(traceback.format_exc(), file=sys.stderr)
            self.controller.processing_queue.put({'action': 'universe_error', 'data': str(e)})

    def stop_loading(self):
        self.progress.stop()
        self.progress.pack_forget()
        self.extract_btn.config(state="normal")
        self.status_label.config(text="")


class SelectionFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        self.info_label = ttk.Label(self, text="Universe: 0 tracks", font=("Helvetica", 14))
        self.info_label.pack(pady=10)
        
        input_frame = ttk.Frame(self)
        input_frame.pack(pady=10)
        
        ttk.Label(input_frame, text="Number of songs to pick (N):").pack(side="left", padx=5)
        self.n_entry = ttk.Entry(input_frame, width=10)
        self.n_entry.pack(side="left", padx=5)
        
        self.pick_btn = ttk.Button(input_frame, text="Pick Random N", command=self.pick_random)
        self.pick_btn.pack(side="left", padx=5)
        
        self.listbox = tk.Listbox(self, width=80, height=15)
        self.listbox.pack(pady=10)
        
        self.remaining_label = ttk.Label(self, text="Remaining: 0")
        self.remaining_label.pack(pady=5)
        
        self.run_btn = ttk.Button(self, text="Run Pipeline", command=self.run_pipeline, state="disabled")
        self.run_btn.pack(pady=20)

    def on_show(self):
        count = len(self.controller.universe)
        self.info_label.config(text=f"Universe: {count} tracks found for {self.controller.username}")
        self.n_entry.delete(0, tk.END)
        self.n_entry.insert(0, str(min(10, count))) # Default to 10 or max
        self.listbox.delete(0, tk.END)
        self.remaining_label.config(text=f"Remaining: {count}")
        self.run_btn.config(state="disabled")

    def pick_random(self):
        try:
            n = int(self.n_entry.get())
        except ValueError:
            messagebox.showerror("Error", "Please enter a valid integer")
            return
            
        universe = self.controller.universe
        if n > len(universe):
            messagebox.showwarning("Warning", f"Only {len(universe)} songs available. Selecting all.")
            n = len(universe)
        if n <= 0:
            messagebox.showwarning("Warning", "Please select at least 1 song.")
            return

        # Selection Logic
        self.controller.selected_tracks = random.sample(universe, n)
        
        # Update UI
        self.listbox.delete(0, tk.END)
        for track in self.controller.selected_tracks:
            self.listbox.insert(tk.END, f"{track['artist']} - {track['title']}")
            
        remaining = len(universe) - n
        self.remaining_label.config(text=f"Remaining: {remaining}")
        self.run_btn.config(state="normal")

    def run_pipeline(self):
        self.controller.show_frame("ProgressFrame")
        # Automatically start processing when switching to the frame
        self.controller.frames["ProgressFrame"].start_processing()


class ProgressFrame(ttk.Frame):
    def __init__(self, parent, controller):
        super().__init__(parent)
        self.controller = controller
        
        ttk.Label(self, text="Pipeline Progress", font=("Helvetica", 16)).pack(pady=10)
        
        # Treeview for status
        columns = ("artist", "title", "status")
        self.tree = ttk.Treeview(self, columns=columns, show="headings", height=15)
        self.tree.heading("artist", text="Artist")
        self.tree.heading("title", text="Title")
        self.tree.heading("status", text="Status")
        self.tree.column("artist", width=200)
        self.tree.column("title", width=250)
        self.tree.column("status", width=300)
        self.tree.pack(pady=10, fill="both", expand=True)
        
        self.progress_bar = ttk.Progressbar(self, orient="horizontal", mode="determinate")
        self.progress_bar.pack(fill="x", padx=20, pady=10)
        
        self.summary_label = ttk.Label(self, text="Ready to start...")
        self.summary_label.pack(pady=10)
        
        # self.start_btn = ttk.Button(self, text="Start Processing", command=self.start_processing)
        # self.start_btn.pack(pady=10)

    def on_show(self):
        # Clear previous
        for i in self.tree.get_children():
            self.tree.delete(i)
            
        tracks = self.controller.selected_tracks
        for i, track in enumerate(tracks):
            # We use the i as the iid (item id)
            self.tree.insert("", "end", iid=str(i), values=(track['artist'], track['title'], "Pending"))
            
        self.progress_bar["maximum"] = len(tracks)
        self.progress_bar["value"] = 0
        self.summary_label.config(text="Processing...")
        # self.start_btn.config(state="normal")

    def start_processing(self):
        # self.start_btn.config(state="disabled")
        threading.Thread(target=self.run_pipeline_thread, daemon=True).start()

    def update_row(self, index, status):
        # Update treeview
        # We need to get current values to preserve artist/title
        try:
            current = self.tree.item(str(index))["values"]
            if current:
                self.tree.item(str(index), values=(current[0], current[1], status))
                self.tree.see(str(index)) # Scroll to item
        except:
            pass
            
    def run_pipeline_thread(self):
        tracks = self.controller.selected_tracks
        username = self.controller.username
        
        success_count = 0
        fail_count = 0
        
        print(f"\n--- Starting Pipeline for {len(tracks)} tracks ---")
        
        for i, track in enumerate(tracks):
            artist = track['artist']
            title = track['title']
            
            # Helper to update status safely
            def set_status(s):
                self.controller.processing_queue.put({'action': 'update_row', 'data': (i, s)})
            
            print(f"\nProcessing [{i+1}/{len(tracks)}]: {artist} - {title}")
            
            set_status("Downloading...")
            filepath = download_song(artist, title)
            if not filepath:
                set_status("Skipped (Download Failed)")
                fail_count += 1
                continue
                
            set_status("Tagging...")
            tag_mp3(filepath, artist, title)
            
            set_status("Vectorizing...")
            vector = vectorize_audio(filepath)
            if not vector:
                set_status("Skipped (Vectorization Failed)")
                fail_count += 1
                try: os.remove(filepath) 
                except: pass
                continue
            
            set_status("Uploading to R2...")
            object_name = os.path.basename(filepath)
            s3_url = upload_to_r2(filepath, object_name)
            if not s3_url:
                set_status("Skipped (Upload Failed)")
                fail_count += 1
                try: os.remove(filepath) 
                except: pass
                continue
                
            set_status("Storing in DB...")
            success = store_vector_db(username, track, vector, s3_url)
            
            if success:
                set_status("Done")
                success_count += 1
                try:
                    os.remove(filepath)
                    print("  Cleaned up local file.")
                except:
                    pass
            else:
                set_status("Skipped (DB Error)")
                fail_count += 1
                
        print(f"\n--- Pipeline Complete: {success_count} Success, {fail_count} Failed ---")
            
        self.controller.processing_queue.put({
            'action': 'pipeline_complete', 
            'data': f"Processed: {success_count}, Failed: {fail_count}"
        })

    def finish_pipeline(self, summary_text):
        self.summary_label.config(text=summary_text)
        self.progress_bar["value"] = self.progress_bar["maximum"]
        messagebox.showinfo("Complete", summary_text)


if __name__ == "__main__":
    app = MusicPipelineApp()
    app.mainloop()
