import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import os
import shutil
import threading

class PhotoOrganizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Photo Organizer")
        self.root.geometry("500x550")
        self.root.resizable(False, False)
        
        style = ttk.Style()
        style.configure("TButton", padding=6, relief="flat", background="#ccc")
        style.configure("TLabel", padding=5, font=("Arial", 10))

        
        # 1. Source Folder Selection
        ttk.Label(root, text="Source Folder (Where photos are now):").pack(anchor="w", padx=20, pady=(15, 0))
        self.source_frame = ttk.Frame(root)
        self.source_frame.pack(fill="x", padx=20)
        
        self.source_path_var = tk.StringVar()
        self.source_entry = ttk.Entry(self.source_frame, textvariable=self.source_path_var)
        self.source_entry.pack(side="left", fill="x", expand=True)
        ttk.Button(self.source_frame, text="Browse", command=self.browse_folder).pack(side="right", padx=(5, 0))

        # 2. Sequence Input
        ttk.Label(root, text="Number Sequence (e.g. 1210, 211, 15):").pack(anchor="w", padx=20, pady=(15, 0))
        self.text_seq = tk.Text(root, height=4, font=("Arial", 10))
        self.text_seq.pack(fill="x", padx=20)

        # 3. Prefix & Extension
        opts_frame = ttk.Frame(root)
        opts_frame.pack(fill="x", padx=20, pady=10)

        # Prefix
        ttk.Label(opts_frame, text="Prefix (e.g. IMG_,DSC, MOV):").grid(row=0, column=0, sticky="w")
        self.prefix_var = tk.StringVar(value="IMG_")
        ttk.Entry(opts_frame, textvariable=self.prefix_var, width=15).grid(row=1, column=0, sticky="w", padx=(0, 10))

        # Extension
        ttk.Label(opts_frame, text="Extensions (e.g. JPG,CR2,MOV,..):").grid(row=0, column=1, sticky="w")
        self.ext_var = tk.StringVar(value="JPG,CR2")
        ttk.Entry(opts_frame, textvariable=self.ext_var, width=20).grid(row=1, column=1, sticky="w")

        # 4. Target Folder Name
        ttk.Label(root, text="New Folder Name:").pack(anchor="w", padx=20)
        self.target_name_var = tk.StringVar(value="Selected_Photos")
        ttk.Entry(root, textvariable=self.target_name_var).pack(fill="x", padx=20)

        # 5. Action Type
        self.action_var = tk.StringVar(value="copy")
        action_frame = ttk.Frame(root)
        action_frame.pack(fill="x", padx=20, pady=10)
        ttk.Radiobutton(action_frame, text="Copy Files", variable=self.action_var, value="copy").pack(side="left", padx=(0, 20))
        ttk.Radiobutton(action_frame, text="Move Files", variable=self.action_var, value="move").pack(side="left")

        # 6. Log / Output
        self.log_text = tk.Text(root, height=6, state="disabled", bg="#f0f0f0", font=("Consolas", 9))
        self.log_text.pack(fill="both", expand=True, padx=20, pady=(0, 10))

        # 7. Run Button
        self.btn_run = ttk.Button(root, text="Start Processing", command=self.start_thread)
        self.btn_run.pack(fill="x", padx=20, pady=(0, 20))

        # 8. Credits
        ttk.Label(root, text="Made by Musaib Bin Bashir", font=("Arial", 8), foreground="gray").pack(pady=(0, 10))

        self.root.bind("<Return>", lambda event: self.start_thread())

    def set_window_icon(self):
        try:
            if getattr(sys, 'frozen', False):
                application_path = sys._MEIPASS
            else:
                application_path = os.path.dirname(os.path.abspath(__file__))

            if os.name == 'nt':
                icon_path = os.path.join(application_path, "app_icon.ico")
                if os.path.exists(icon_path):
                    self.root.iconbitmap(icon_path)
            else:
                icon_path = os.path.join(application_path, "app_icon.png")
                if os.path.exists(icon_path):
                    img = tk.PhotoImage(file=icon_path)
                    self.root.iconphoto(True, img)
        except Exception:
            pass
    
    def browse_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.source_path_var.set(folder)

    def log(self, message):
        self.log_text.config(state="normal")
        self.log_text.insert("end", message + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def start_thread(self):
        threading.Thread(target=self.process_files, daemon=True).start()

    def process_files(self):
        source_dir = self.source_path_var.get()
        raw_seq = self.text_seq.get("1.0", "end").strip()
        prefix = self.prefix_var.get().strip()
        exts = [e.strip().replace(".", "") for e in self.ext_var.get().split(",")]
        target_name = self.target_name_var.get().strip()
        action = self.action_var.get()

        if not source_dir or not os.path.exists(source_dir):
            messagebox.showerror("Error", "Please select a valid source folder.")
            return
        if not raw_seq:
            messagebox.showerror("Error", "Please enter a number sequence.")
            return

        target_dir = os.path.join(source_dir, target_name)
        if not os.path.exists(target_dir):
            try:
                os.makedirs(target_dir)
            except Exception as e:
                messagebox.showerror("Error", f"Could not create folder: {e}")
                return

        self.btn_run.config(state="disabled")
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")

        numbers = [x.strip() for x in raw_seq.replace("\n", ",").split(",") if x.strip()]
        last_full = ""
        success = 0
        errors = 0

        self.log(f"Processing {len(numbers)} items...")

        for num_str in numbers:
            current_full = ""    
    
            if not last_full:
                current_full = num_str
            else:
                if len(num_str) < len(last_full):
                    prefix_len = len(last_full) - len(num_str)
                    current_full = last_full[:prefix_len] + num_str
                else:
                    current_full = num_str
            
            last_full = current_full

            for ext in exts:
                filename = f"{prefix}{current_full}.{ext}"
                src_path = os.path.join(source_dir, filename)
                dst_path = os.path.join(target_dir, filename)

                if os.path.exists(src_path):
                    try:
                        if action == "move":
                            shutil.move(src_path, dst_path)
                            self.log(f"[MOVED] {filename}")
                        else:
                            shutil.copy2(src_path, dst_path)
                            self.log(f"[COPIED] {filename}")
                        success += 1
                    except Exception as e:
                        self.log(f"[ERR] {filename}: {str(e)}")
                        errors += 1
                else:
                    self.log(f"[MISSING] {filename}")
                    errors += 1

        self.log("-" * 30)
        self.log(f"Done! Success: {success}, Errors/Missing: {errors}")
        messagebox.showinfo("Complete", f"Operation finished.\nSuccess: {success}\nIssues: {errors}")
        self.btn_run.config(state="normal")

if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoOrganizerApp(root)
    root.mainloop()
