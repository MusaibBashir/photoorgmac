import tkinter as tk
from tkinter import filedialog, messagebox, ttk, simpledialog
import os
import shutil
import threading
import sys
import subprocess
import time
import io
from datetime import datetime

# --- Library Checks ---
try:
    from PIL import Image, ImageTk, ImageOps, ImageDraw, ExifTags
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Optional: OpenCV for video frame extraction
try:
    import cv2
    HAS_CV2 = True
except ImportError:
    HAS_CV2 = False

class PhotoOrganizerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Smart Shoot Organizer | Musaib Bin Bashir")
        self.root.geometry("1250x900")

        if not HAS_PIL:
            messagebox.showwarning("Missing Library", "Pillow is required.\nRun: pip install Pillow")

        self.set_window_icon()

        # --- State Data ---
        self.vlc_path = self.find_vlc()
        
        # Visual Sorter Data
        self.visual_source_dir = ""
        self.visual_output_dir = "" 
        self.image_files = [] 
        self.file_labels = {}         
        self.file_renames_sorted = {} 
        self.current_image_index = -1
        
        # Smart Renamer Data
        self.renamer_source_dir = ""
        self.renamer_files = []
        self.file_groups = {} # {filename: "Group 1"}
        self.current_renamer_index = -1
        
        # Shared/Canvas State
        self.pil_image_raw = None     
        self.img_scale = 1.0
        self.img_pos_x = 0
        self.img_pos_y = 0
        
        # Ribbon Data
        self.thumb_cache = {} 
        self.ribbon_widgets = {} 
        self.thumb_cache_renamer = {}
        self.ribbon_widgets_renamer = {}

        # --- UI Layout ---
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Tab 1: Visual Sorter
        self.tab_visual = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_visual, text="Visual Sorter")
        self.init_visual_tab()
        
        # Tab 2: Smart Renamer (New)
        self.tab_renamer = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_renamer, text="Smart Group & Renamer")
        self.init_smart_rename_tab()

        # Tab 3: Sequence Sorter
        self.tab_sequence = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_sequence, text="Sequence Sorter")
        self.init_sequence_tab()

        # Tab 4: Help (New)
        self.tab_help = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_help, text="Help")
        self.init_help_tab()

        if not HAS_CV2:
            ttk.Label(root, text="Warning: OpenCV (cv2) not found. Video thumbnails will be placeholders.", foreground="red").pack(pady=2)

    def set_window_icon(self):
        try:
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(os.path.abspath(__file__))

            if os.name == 'nt':
                icon_path = os.path.join(base_path, "app_icon.ico")
                if os.path.exists(icon_path):
                    self.root.iconbitmap(icon_path)
            else:
                icon_path = os.path.join(base_path, "app_icon.png")
                if os.path.exists(icon_path):
                    img = tk.PhotoImage(file=icon_path)
                    self.root.iconphoto(True, img)
        except Exception:
            pass

    def find_vlc(self):
        paths = []
        if sys.platform == 'win32':
            paths = [r"C:\Program Files\VideoLAN\VLC\vlc.exe", r"C:\Program Files (x86)\VideoLAN\VLC\vlc.exe"]
        elif sys.platform == 'darwin':
            paths = ["/Applications/VLC.app/Contents/MacOS/VLC"]
        for p in paths:
            if os.path.exists(p): return p
        return shutil.which("vlc")

    # ==========================================
    #           TAB 1: VISUAL SORTER
    # ==========================================
    def init_visual_tab(self):
        # 1. Top Controls
        top_frame = ttk.LabelFrame(self.tab_visual, text="Configuration")
        top_frame.pack(fill="x", padx=10, pady=5)
        top_frame.columnconfigure(1, weight=1)
        top_frame.columnconfigure(3, weight=1)

        ttk.Button(top_frame, text="1. Select Source", command=self.load_images_visual).grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.lbl_visual_source = ttk.Label(top_frame, text="No source selected", foreground="gray", width=30, anchor="w")
        self.lbl_visual_source.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        ttk.Button(top_frame, text="2. Select Destination", command=self.select_output_folder).grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.lbl_visual_output = ttk.Label(top_frame, text="Same as Source (Default)", foreground="gray", width=30, anchor="w")
        self.lbl_visual_output.grid(row=0, column=3, padx=5, pady=5, sticky="ew")

        self.var_move_related = tk.BooleanVar(value=True)
        ttk.Checkbutton(top_frame, text="Include Related Files (RAW/XMP/Sidecars)", variable=self.var_move_related).grid(row=1, column=0, columnspan=4, sticky="w", padx=5, pady=(0,5))

        # 2. Main Canvas
        self.canvas_container = tk.Frame(self.tab_visual, bg="#222")
        self.canvas_container.pack(fill="both", expand=True, padx=10)
        
        self.image_canvas = tk.Canvas(self.canvas_container, bg="#222", highlightthickness=0)
        self.image_canvas.pack(fill="both", expand=True)
        
        # 3. Ribbon
        ribbon_frame = ttk.Frame(self.tab_visual, height=110)
        ribbon_frame.pack(fill="x", padx=10, pady=5)
        
        self.ribbon_scroll = ttk.Scrollbar(ribbon_frame, orient="horizontal")
        self.ribbon_scroll.pack(side="bottom", fill="x")
        
        self.ribbon_canvas = tk.Canvas(ribbon_frame, height=90, bg="#e0e0e0", xscrollcommand=self.ribbon_scroll.set)
        self.ribbon_canvas.pack(side="top", fill="x", expand=True)
        self.ribbon_scroll.config(command=self.ribbon_canvas.xview)
        
        self.ribbon_inner = tk.Frame(self.ribbon_canvas, bg="#e0e0e0")
        self.ribbon_window_id = self.ribbon_canvas.create_window((0,0), window=self.ribbon_inner, anchor="nw")
        self.ribbon_inner.bind("<Configure>", lambda e: self.ribbon_canvas.configure(scrollregion=self.ribbon_canvas.bbox("all")))

        # 4. Bottom Controls
        btm_frame = ttk.Frame(self.tab_visual)
        btm_frame.pack(fill="x", padx=10, pady=10)

        f_nav = ttk.Frame(btm_frame)
        f_nav.pack(side="left")
        
        ttk.Button(f_nav, text="< Prev", command=self.prev_image).pack(side="left")
        ttk.Button(f_nav, text="Open File (P)", command=self.open_current_file, width=18).pack(side="left", padx=5)
        ttk.Button(f_nav, text="R (Rename)", command=self.open_rename_dialog, width=10).pack(side="left", padx=5)
        self.lbl_counter = ttk.Label(f_nav, text="0 / 0", width=10, anchor="center")
        self.lbl_counter.pack(side="left", padx=5)
        ttk.Button(f_nav, text="Next >", command=self.next_image).pack(side="left")

        ttk.Button(btm_frame, text="SORT NOW", command=self.run_visual_sort).pack(side="right", padx=(10, 0))

        f_action = ttk.LabelFrame(btm_frame, text="Action")
        f_action.pack(side="right", padx=10)
        self.var_visual_action = tk.StringVar(value="move")
        ttk.Radiobutton(f_action, text="Move", variable=self.var_visual_action, value="move").pack(side="left", padx=5)
        ttk.Radiobutton(f_action, text="Copy", variable=self.var_visual_action, value="copy").pack(side="left", padx=5)

        f_lbl = ttk.LabelFrame(btm_frame, text="Label")
        f_lbl.pack(side="right", padx=10)
        
        self.var_current_label = tk.StringVar(value="Unmarked")
        self.colors = {"Green": "#90EE90", "Yellow": "#FFFF99", "Red": "#FFcccb", "Unmarked": "#e0e0e0"}

        tk.Radiobutton(f_lbl, text="Unmarked", variable=self.var_current_label, value="Unmarked", command=self.save_label, indicatoron=0, width=8).pack(side="left", padx=2)
        tk.Radiobutton(f_lbl, text="Green", variable=self.var_current_label, value="Green", command=self.save_label, indicatoron=0, width=6, bg=self.colors["Green"], selectcolor=self.colors["Green"]).pack(side="left", padx=2)
        tk.Radiobutton(f_lbl, text="Yellow", variable=self.var_current_label, value="Yellow", command=self.save_label, indicatoron=0, width=6, bg=self.colors["Yellow"], selectcolor=self.colors["Yellow"]).pack(side="left", padx=2)
        tk.Radiobutton(f_lbl, text="Delete (Red)", variable=self.var_current_label, value="Red", command=self.save_label, indicatoron=0, width=10, bg=self.colors["Red"], selectcolor=self.colors["Red"]).pack(side="left", padx=2)

        self.bind_events(self.image_canvas)

        self.ext_imgs = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tiff"}
        self.ext_vids = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}

    # ==========================================
    #           TAB 2: SMART RENAMER
    # ==========================================
    def init_smart_rename_tab(self):
        # 1. Top Controls
        top_frame = ttk.LabelFrame(self.tab_renamer, text="Configuration")
        top_frame.pack(fill="x", padx=10, pady=5)
        
        ttk.Button(top_frame, text="Select Source Folder", command=self.load_images_renamer).pack(side="left", padx=5, pady=5)
        self.lbl_renamer_source = ttk.Label(top_frame, text="No source selected", foreground="gray")
        self.lbl_renamer_source.pack(side="left", padx=10)

        # 2. Main Canvas
        self.renamer_canvas_container = tk.Frame(self.tab_renamer, bg="#222")
        self.renamer_canvas_container.pack(fill="both", expand=True, padx=10)
        
        self.renamer_canvas = tk.Canvas(self.renamer_canvas_container, bg="#222", highlightthickness=0)
        self.renamer_canvas.pack(fill="both", expand=True)

        # 3. Ribbon
        r_frame = ttk.Frame(self.tab_renamer, height=110)
        r_frame.pack(fill="x", padx=10, pady=5)
        
        self.r_scroll = ttk.Scrollbar(r_frame, orient="horizontal")
        self.r_scroll.pack(side="bottom", fill="x")
        
        self.r_canvas = tk.Canvas(r_frame, height=90, bg="#e0e0e0", xscrollcommand=self.r_scroll.set)
        self.r_canvas.pack(side="top", fill="x", expand=True)
        self.r_scroll.config(command=self.r_canvas.xview)
        
        self.r_inner = tk.Frame(self.r_canvas, bg="#e0e0e0")
        self.r_window_id = self.r_canvas.create_window((0,0), window=self.r_inner, anchor="nw")
        self.r_inner.bind("<Configure>", lambda e: self.r_canvas.configure(scrollregion=self.r_canvas.bbox("all")))

        # 4. Bottom Controls
        btm_frame = ttk.Frame(self.tab_renamer)
        btm_frame.pack(fill="x", padx=10, pady=10)
        
        # Navigation
        f_nav = ttk.Frame(btm_frame)
        f_nav.pack(side="left")
        ttk.Button(f_nav, text="< Prev", command=self.prev_image_renamer).pack(side="left")
        ttk.Button(f_nav, text="Open File (P)", command=self.open_current_renamer, width=15).pack(side="left", padx=5)
        self.lbl_renamer_counter = ttk.Label(f_nav, text="0 / 0", width=10, anchor="center")
        self.lbl_renamer_counter.pack(side="left", padx=5)
        ttk.Button(f_nav, text="Next >", command=self.next_image_renamer).pack(side="left")

        # Process Button
        ttk.Button(btm_frame, text="PROCESS GROUPS...", command=self.open_group_process_dialog).pack(side="right", padx=(20, 0))

        # Groups
        f_groups = ttk.LabelFrame(btm_frame, text="Assign to Group")
        f_groups.pack(side="right", padx=10)
        
        self.var_renamer_group = tk.StringVar(value="Unassigned")
        self.group_colors = {"Unassigned": "#e0e0e0", "Group 1": "#82181A", "Group 2": "#F3397B", "Group 3": "#FFD900", "Group 4": "#178236", "Group 5": "#0343CE"}

        tk.Radiobutton(f_groups, text="Unassigned", variable=self.var_renamer_group, value="Unassigned", command=self.save_group, indicatoron=0, width=10).pack(side="left", padx=2)
        for i in range(1, 6):
            gname = f"Group {i}"
            tk.Radiobutton(f_groups, text=gname, variable=self.var_renamer_group, value=gname, command=self.save_group, indicatoron=0, width=8, bg=self.group_colors[gname], selectcolor=self.group_colors[gname]).pack(side="left", padx=2)

        self.bind_events(self.renamer_canvas, is_renamer=True)

    def bind_events(self, canvas, is_renamer=False):
        # Bind generic events to specific canvas
        canvas.bind("<Configure>", lambda e: self.on_canvas_resize(e, is_renamer))
        canvas.bind("<MouseWheel>", lambda e: self.on_zoom(e, is_renamer))     
        canvas.bind("<Button-4>", lambda e: self.on_zoom(e, is_renamer))       
        canvas.bind("<Button-5>", lambda e: self.on_zoom(e, is_renamer))       
        canvas.bind("<ButtonPress-1>", self.on_drag_start)
        canvas.bind("<B1-Motion>", lambda e: self.on_drag_move(e, is_renamer))
        
        # Shortcuts (Global)
        self.root.bind("<p>", lambda e: self.handle_shortcut('p'))
        self.root.bind("<P>", lambda e: self.handle_shortcut('p'))
        self.root.bind("<Left>", lambda e: self.handle_shortcut('left'))
        self.root.bind("<Right>", lambda e: self.handle_shortcut('right'))
        
        # Grouping Shortcuts (Ctrl+1 to Ctrl+5)
        for i in range(1, 6):
            self.root.bind(f"<Control-Key-{i}>", lambda e, n=i: self.handle_shortcut(str(n)))

    def handle_shortcut(self, key):
        # Determine active tab
        current_tab = self.notebook.index(self.notebook.select())
        if current_tab == 0: # Visual Sorter
            if key == 'p': self.open_current_file()
            elif key == 'left': self.prev_image()
            elif key == 'right': self.next_image()
        elif current_tab == 1: # Smart Renamer
            if key == 'p': self.open_current_renamer()
            elif key == 'left': self.prev_image_renamer()
            elif key == 'right': self.next_image_renamer()
            elif key in ['1', '2', '3', '4', '5']:
                self.var_renamer_group.set(f"Group {key}")
                self.save_group()

    # ==========================================
    #           TAB 4: HELP
    # ==========================================
    def init_help_tab(self):
        # Main container with scrollbar
        frame = self.tab_help
        
        scrollbar = ttk.Scrollbar(frame)
        scrollbar.pack(side="right", fill="y")
        
        text_area = tk.Text(frame, wrap="word", yscrollcommand=scrollbar.set, font=("Arial", 11), padx=10, pady=10)
        text_area.pack(fill="both", expand=True)
        scrollbar.config(command=text_area.yview)
        
        # Help Content
        content = """
SMART SHOOT ORGANIZER - USER GUIDE

TAB 1: VISUAL SORTER
-----------------------------------------
Purpose: Manually review and sort photos into folders or delete bad shots.

Instructions:
1. Click 'Select Source' to choose your folder.
2. (Optional) 'Select Destination' if you want sorted folders elsewhere.
3. Use Arrow Keys or Buttons to navigate.
4. Mark files:
   - Green: Moves to 'Green' folder (Good photos).
   - Yellow: Moves to 'Yellow' folder (Review Later).
   - Red: PERMANENTLY DELETES the file from disk.
5. Click 'SORT NOW' to execute moves/deletes.

Shortcuts:
- Left Arrow: Previous Image
- Right Arrow: Next Image
- P: Open file in default viewer (or VLC for video)
- R: Rename current file
- Scroll Wheel: Zoom In/Out
- Click & Drag: Pan zoomed image

TAB 2: SMART GROUP & RENAMER
-----------------------------------------
Purpose: Sort photos/videos into numbered groups and batch rename them chronologically.

Instructions:
1. Select Source Folder.
2. Assign files to Group 1, 2, 3, 4, or 5.
3. Click 'PROCESS GROUPS'.
4. Choose a group to rename (e.g., Group 1).
5. Enter Scene Name (e.g., 'Transit').
6. (Optional) Enter Camera Name. If blank, it tries to read metadata.
7. Select Action: Rename (Default), Move to new folder, or Copy to new folder.
8. Result: 'Transit_001.mov' or 'Transit_001_FX30.mov'.

Shortcuts:
- Ctrl + 1: Assign to Group 1
- Ctrl + 2: Assign to Group 2
- Ctrl + 3: Assign to Group 3
- Ctrl + 4: Assign to Group 4
- Ctrl + 5: Assign to Group 5
- Left/Right/P: Navigation and Open

TAB 3: SEQUENCE SORTER
-----------------------------------------
Purpose: For photographers who write down shorthand shot numbers (e.g., 1210, 11, 12).

Instructions:
1. Select Source Folder.
2. Paste shorthand sequence: "1210,1,5, 67, 347, 4728".
3. App interprets as: 1210, 1211, 1215, 1267, 1347, 4728.
4. Set Prefix (IMG_) and Extensions (JPG,CR2,ARW).
5. Click Process to copy/move those specific files.

GENERAL NOTES
-----------------------------------------
- Video Support: Videos play in external player (VLC recommended).
- Related Files: If enabled, sorting a JPG will also move the matching RAW/XMP file.

Credits:
-----------------------------------------
- Developed by Musaib Bin Bashir
- By TFPS for TFPS
- www.tfps.site
"""
        text_area.insert("1.0", content)
        text_area.config(state="disabled") # Read-only

    # ==========================================
    #       SMART RENAMER LOGIC
    # ==========================================
    def load_images_renamer(self):
        folder = filedialog.askdirectory()
        if not folder: return
        self.renamer_source_dir = folder
        self.lbl_renamer_source.config(text=folder)
        
        valid_exts = self.ext_imgs.union(self.ext_vids)
        try:
            files = [f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in valid_exts]
            files.sort()
            self.renamer_files = files
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return

        self.file_groups = {}
        self.current_renamer_index = 0
        self.ribbon_widgets_renamer = {}
        
        for w in self.r_inner.winfo_children(): w.destroy()
        
        if self.renamer_files:
            self.show_image_renamer()
            threading.Thread(target=self.generate_thumbnails_renamer_thread, daemon=True).start()
        else:
            self.renamer_canvas.delete("all")
            self.renamer_canvas.create_text(400, 300, text="No Media Found", fill="white")

    def show_image_renamer(self):
        if not self.renamer_files: return
        
        filename = self.renamer_files[self.current_renamer_index]
        self.lbl_renamer_counter.config(text=f"{self.current_renamer_index + 1} / {len(self.renamer_files)}")
        
        grp = self.file_groups.get(filename, "Unassigned")
        self.var_renamer_group.set(grp)
        
        # Highlight Ribbon
        if filename in self.ribbon_widgets_renamer:
             self.ensure_ribbon_visible(self.ribbon_widgets_renamer[filename], self.r_canvas, self.r_inner)

        self.display_media_on_canvas(self.renamer_canvas, self.renamer_source_dir, filename)

    def save_group(self):
        if not self.renamer_files: return
        fname = self.renamer_files[self.current_renamer_index]
        grp = self.var_renamer_group.get()
        self.file_groups[fname] = grp
        
        # Update Ribbon Color
        if fname in self.ribbon_widgets_renamer:
            color = self.group_colors.get(grp, "#e0e0e0")
            self.ribbon_widgets_renamer[fname].config(bg=color)

    def prev_image_renamer(self):
        if self.current_renamer_index > 0:
            self.current_renamer_index -= 1
            self.show_image_renamer()

    def next_image_renamer(self):
        if self.current_renamer_index < len(self.renamer_files) - 1:
            self.current_renamer_index += 1
            self.show_image_renamer()

    def open_current_renamer(self):
        if not self.renamer_files: return
        fname = self.renamer_files[self.current_renamer_index]
        self.open_file_external(self.renamer_source_dir, fname)

    def open_group_process_dialog(self):
        if not self.file_groups:
            messagebox.showinfo("Info", "No files have been assigned to groups yet.")
            return

        dlg = tk.Toplevel(self.root)
        dlg.title("Process Groups")
        dlg.geometry("450x400")
        
        ttk.Label(dlg, text="Batch Rename Group", font=("Arial", 12, "bold")).pack(pady=10)
        
        f_form = ttk.Frame(dlg)
        f_form.pack(pady=10, padx=20, fill="x")

        # 1. Select Group
        ttk.Label(f_form, text="Select Group:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        var_grp = tk.StringVar(value="Group 1")
        cb_grp = ttk.Combobox(f_form, textvariable=var_grp, values=[f"Group {i}" for i in range(1,6)], state="readonly")
        cb_grp.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        
        # 2. Scene Name
        ttk.Label(f_form, text="Scene Name (Req):").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        e_scene = ttk.Entry(f_form, width=30)
        e_scene.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        # 3. Camera Name
        ttk.Label(f_form, text="Camera Name (Opt):").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        e_cam = ttk.Entry(f_form, width=30)
        e_cam.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        ttk.Label(f_form, text="(Leave blank for metadata or omit)", font=("Arial", 8), foreground="gray").grid(row=3, column=1, sticky="w", padx=5)

        # 4. Action Choice
        ttk.Label(f_form, text="Action:").grid(row=4, column=0, sticky="ne", padx=5, pady=10)
        f_actions = ttk.Frame(f_form)
        f_actions.grid(row=4, column=1, sticky="w", padx=5, pady=10)
        
        var_action = tk.StringVar(value="rename")
        ttk.Radiobutton(f_actions, text="Rename in Original Folder", variable=var_action, value="rename").pack(anchor="w", pady=2)
        ttk.Radiobutton(f_actions, text="Move to New Folder", variable=var_action, value="move").pack(anchor="w", pady=2)
        ttk.Radiobutton(f_actions, text="Copy to New Folder", variable=var_action, value="copy").pack(anchor="w", pady=2)
        ttk.Label(f_actions, text="*New Folder will be named after Scene", font=("Arial", 8), foreground="gray").pack(anchor="w", padx=20)

        def run_rename():
            target_group = var_grp.get()
            scene = e_scene.get().strip()
            manual_cam = e_cam.get().strip()
            action = var_action.get()
            
            if not scene:
                messagebox.showerror("Error", "Scene Name is required!")
                return
            
            # 1. Collect files in group
            files_in_group = [f for f, g in self.file_groups.items() if g == target_group]
            if not files_in_group:
                messagebox.showerror("Error", f"No files assigned to {target_group}")
                return

            # 2. Sort Chronologically (Metadata or File Date)
            files_with_dates = []
            for f in files_in_group:
                full_path = os.path.join(self.renamer_source_dir, f)
                date_taken = self.get_date_taken(full_path)
                files_with_dates.append((f, date_taken))
            
            # Sort by date
            files_with_dates.sort(key=lambda x: x[1])
            
            # 3. Prepare Paths
            dest_dir = self.renamer_source_dir
            if action in ["move", "copy"]:
                safe_scene_folder = "".join([c for c in scene if c.isalnum() or c in (' ', '_', '-')]).strip()
                dest_dir = os.path.join(self.renamer_source_dir, safe_scene_folder)
                if not os.path.exists(dest_dir):
                    try: os.makedirs(dest_dir)
                    except Exception as e:
                        messagebox.showerror("Error", f"Could not create folder: {e}")
                        return

            # 4. Rename Loop
            count = 0
            for idx, (fname, _) in enumerate(files_with_dates):
                src_path = os.path.join(self.renamer_source_dir, fname)
                ext = os.path.splitext(fname)[1]
                
                # Determine Camera Name
                cam_name = manual_cam
                if not cam_name:
                    cam_name = self.get_camera_model(src_path)
                
                # Sanitize inputs
                safe_scene = "".join([c for c in scene if c.isalnum() or c in (' ', '_', '-')]).strip()
                
                # Format Filename
                if cam_name:
                    safe_cam = "".join([c for c in cam_name if c.isalnum() or c in (' ', '_', '-')]).strip()
                    new_name = f"{safe_scene}_{str(idx+1).zfill(3)}_{safe_cam}{ext}"
                else:
                    # No Camera Name logic
                    new_name = f"{safe_scene}_{str(idx+1).zfill(3)}{ext}"
                
                new_path = os.path.join(dest_dir, new_name)
                
                try:
                    if action == "rename":
                        # Standard Rename
                        os.rename(src_path, new_path)
                        # Update internal lists if renamed in place
                        if new_name != fname:
                            self.renamer_files[self.renamer_files.index(fname)] = new_name
                            self.file_groups[new_name] = self.file_groups.pop(fname)
                            if fname in self.ribbon_widgets_renamer:
                                self.ribbon_widgets_renamer[new_name] = self.ribbon_widgets_renamer.pop(fname)
                    elif action == "move":
                        shutil.move(src_path, new_path)
                        # For simplicity, we don't update the view for moved files out of root
                        # as they are now "gone" from source dir perspective
                    elif action == "copy":
                        shutil.copy2(src_path, new_path)
                    
                    count += 1
                except Exception as e:
                    print(f"Failed to process {fname}: {e}")

            msg_action = "Renamed" if action == "rename" else "Processed"
            messagebox.showinfo("Success", f"{msg_action} {count} files in {target_group}")
            
            # Refresh view if files were moved/renamed in place
            self.load_images_renamer() 
            dlg.destroy()

        ttk.Button(dlg, text="Execute", command=run_rename).pack(pady=20)

    # --- Helpers for Renamer ---
    def get_date_taken(self, filepath):
        """ Returns datetime object. Tries EXIF, falls back to file mod time. """
        if HAS_PIL:
            try:
                img = Image.open(filepath)
                exif = img.getexif()
                if exif:
                    # Tags: 36867 (DateTimeOriginal), 306 (DateTime)
                    date_str = exif.get(36867) or exif.get(306)
                    if date_str:
                        return datetime.strptime(date_str, "%Y:%m:%d %H:%M:%S")
            except: pass
        return datetime.fromtimestamp(os.path.getmtime(filepath))

    def get_camera_model(self, filepath):
        """ Tries to extract camera model from EXIF """
        if HAS_PIL:
            try:
                img = Image.open(filepath)
                exif = img.getexif()
                if exif:
                    # Tag 272 is Model
                    model = exif.get(272)
                    if model: return str(model).strip()
            except: pass
        return None

    def generate_thumbnails_renamer_thread(self):
        size = (80, 60)
        for idx, filename in enumerate(self.renamer_files):
            filepath = os.path.join(self.renamer_source_dir, filename)
            thumb = self.create_thumbnail(filepath, size)
            if thumb:
                self.root.after(10, self.add_renamer_ribbon_item, idx, filename, thumb)
            if idx % 5 == 0: time.sleep(0.01)

    def add_renamer_ribbon_item(self, idx, filename, thumb):
        self.thumb_cache_renamer[filename] = thumb
        f = tk.Frame(self.r_inner, bg=self.group_colors["Unassigned"], padx=3, pady=3)
        f.pack(side="left", fill="y", padx=1)
        btn = tk.Button(f, image=thumb, command=lambda: self.jump_to_renamer_file(filename), relief="flat", bd=0)
        btn.pack(fill="both", expand=True)
        self.ribbon_widgets_renamer[filename] = f
        if idx == self.current_renamer_index:
             self.ensure_ribbon_visible(f, self.r_canvas, self.r_inner)

    def jump_to_renamer_file(self, filename):
        if filename in self.renamer_files:
            self.current_renamer_index = self.renamer_files.index(filename)
            self.show_image_renamer()

    # ==========================================
    #       SHARED / COMMON HELPERS
    # ==========================================
    def create_thumbnail(self, filepath, size):
        ext = os.path.splitext(filepath)[1].lower()
        if ext in self.ext_imgs and HAS_PIL:
            try:
                img = Image.open(filepath)
                img.thumbnail(size)
                return ImageTk.PhotoImage(img)
            except: pass
        elif ext in self.ext_vids:
            if HAS_CV2:
                try:
                    cap = cv2.VideoCapture(filepath)
                    cap.set(cv2.CAP_PROP_POS_MSEC, 1000)
                    ret, frame = cap.read()
                    cap.release()
                    if ret:
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        img = Image.fromarray(frame)
                        img.thumbnail(size)
                        draw = ImageDraw.Draw(img)
                        draw.polygon([(35, 20), (35, 40), (55, 30)], fill="white", outline="black")
                        return ImageTk.PhotoImage(img)
                except: pass
            
            if HAS_PIL:
                base = Image.new('RGB', size, color='#333')
                draw = ImageDraw.Draw(base)
                draw.text((10, 20), "VIDEO", fill="white")
                return ImageTk.PhotoImage(base)
        return None

    def display_media_on_canvas(self, canvas, folder, filename):
        # Reset Scale
        self.img_scale = 1.0
        self.img_pos_x = 0
        self.img_pos_y = 0
        
        filepath = os.path.join(folder, filename)
        ext = os.path.splitext(filename)[1].lower()
        canvas.delete("all")
        
        loaded_pil = None
        is_video = False

        if ext in self.ext_imgs and HAS_PIL:
            try:
                loaded_pil = Image.open(filepath)
                try: loaded_pil = ImageOps.exif_transpose(loaded_pil)
                except: pass
            except: pass
        elif ext in self.ext_vids:
            is_video = True
            if HAS_CV2:
                try:
                    cap = cv2.VideoCapture(filepath)
                    ret, frame = cap.read()
                    cap.release()
                    if ret:
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        loaded_pil = Image.fromarray(frame)
                except: pass

        self.pil_image_raw = loaded_pil
        if self.pil_image_raw:
            self.draw_canvas_image(canvas)
            if is_video: self.draw_video_overlay(canvas, filename)
            self.draw_filename_overlay(canvas, filename)
        elif is_video:
            self.draw_video_placeholder(canvas, filename)
        else:
            self.draw_placeholder(canvas, f"Cannot preview: {filename}")

    def draw_canvas_image(self, canvas):
        if not self.pil_image_raw: return
        cw = canvas.winfo_width()
        ch = canvas.winfo_height()
        iw, ih = self.pil_image_raw.size
        if iw == 0 or ih == 0: return

        ratio = min(cw/iw, ch/ih)
        final_scale = ratio * self.img_scale
        new_w, new_h = int(iw * final_scale), int(ih * final_scale)
        
        try:
            resized = self.pil_image_raw.resize((new_w, new_h), Image.Resampling.BILINEAR)
            self.tk_image = ImageTk.PhotoImage(resized)
            cx = cw // 2 + self.img_pos_x
            cy = ch // 2 + self.img_pos_y
            canvas.create_image(cx, cy, image=self.tk_image)
        except: pass

    def on_zoom(self, event, is_renamer=False):
        if not self.pil_image_raw: return
        if event.num == 5 or event.delta < 0: factor = 0.9
        else: factor = 1.1
        self.img_scale *= factor
        if self.img_scale < 0.1: self.img_scale = 0.1
        if self.img_scale > 10.0: self.img_scale = 10.0
        
        canvas = self.renamer_canvas if is_renamer else self.image_canvas
        canvas.delete("all")
        self.draw_canvas_image(canvas)
        
        # Redraw Overlays
        files = self.renamer_files if is_renamer else self.image_files
        idx = self.current_renamer_index if is_renamer else self.current_image_index
        if files:
            fname = files[idx]
            ext = os.path.splitext(fname)[1].lower()
            if ext in self.ext_vids: self.draw_video_overlay(canvas, fname)
            self.draw_filename_overlay(canvas, fname)

    def on_drag_start(self, event):
        self._drag_start_x = event.x
        self._drag_start_y = event.y

    def on_drag_move(self, event, is_renamer=False):
        if not self.pil_image_raw: return
        dx = event.x - self._drag_start_x
        dy = event.y - self._drag_start_y
        self.img_pos_x += dx
        self.img_pos_y += dy
        self._drag_start_x = event.x
        self._drag_start_y = event.y
        
        canvas = self.renamer_canvas if is_renamer else self.image_canvas
        canvas.delete("all")
        self.draw_canvas_image(canvas)
        # Redraw overlays... (Simplified for brevity, same logic as zoom)

    def on_canvas_resize(self, event, is_renamer=False):
        if self.pil_image_raw:
            canvas = self.renamer_canvas if is_renamer else self.image_canvas
            self.draw_canvas_image(canvas)
            # Re-draw overlays logic needed here in full impl

    # --- Overlay Drawing Helpers ---
    def draw_video_overlay(self, canvas, filename):
        cw, ch = canvas.winfo_width(), canvas.winfo_height()
        cx = cw // 2 + self.img_pos_x
        cy = ch // 2 + self.img_pos_y
        canvas.create_oval(cx-50, cy-50, cx+50, cy+50, outline="white", width=4, fill="#000000", stipple="gray25")
        canvas.create_polygon(cx-15, cy-25, cx-15, cy+25, cx+30, cy, fill="white")
        canvas.create_text(cw/2, ch - 50, text=f"[VIDEO] {filename}", fill="white", font=("Arial", 14, "bold"))

    def draw_filename_overlay(self, canvas, text):
        canvas.create_rectangle(10, 10, 15 + len(text)*8, 35, fill="#000000", stipple="gray50", outline="")
        canvas.create_text(15, 22, text=text, fill="white", anchor="w", font=("Arial", 10, "bold"))

    def draw_video_placeholder(self, canvas, filename):
        cw, ch = canvas.winfo_width(), canvas.winfo_height()
        cx, cy = cw//2, ch//2
        canvas.create_oval(cx-60, cy-60, cx+60, cy+60, outline="white", width=4)
        canvas.create_polygon(cx-15, cy-30, cx-15, cy+30, cx+35, cy, fill="white")
        canvas.create_text(cx, cy+90, text=f"[VIDEO] {filename}", fill="white", font=("Arial", 12))
        canvas.create_text(cx, cy+115, text="Press 'P' to Open", fill="#aaa")

    def draw_placeholder(self, canvas, text):
        canvas.delete("all")
        cw, ch = canvas.winfo_width(), canvas.winfo_height()
        canvas.create_text(cw//2, ch//2, text=text, fill="white")

    # --- Common File Ops ---
    def open_file_external(self, folder, filename):
        fpath = os.path.abspath(os.path.join(folder, filename))
        ext = os.path.splitext(filename)[1].lower()
        try:
            if ext in self.ext_imgs:
                if os.name == 'nt': os.startfile(fpath)
                elif sys.platform == 'darwin': subprocess.call(['open', fpath])
                else: subprocess.call(['xdg-open', fpath])
            elif ext in self.ext_vids and self.vlc_path:
                subprocess.Popen([self.vlc_path, fpath])
            else:
                if os.name == 'nt': os.startfile(fpath)
                elif sys.platform == 'darwin': subprocess.call(['open', fpath])
                else: subprocess.call(['xdg-open', fpath])
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def ensure_ribbon_visible(self, widget, canvas, inner):
        try:
            x1 = widget.winfo_x()
            cw = canvas.winfo_width()
            iw = inner.winfo_width()
            if iw <= cw: return
            want_x = x1 - cw/2 + widget.winfo_width()/2
            pct = want_x / iw
            canvas.xview_moveto(pct)
        except: pass

    # ==========================================
    #       VISUAL SORTER (TAB 1) LOGIC
    # ==========================================
    def load_images_visual(self):
        folder = filedialog.askdirectory()
        if not folder: return
        self.visual_source_dir = folder
        self.lbl_visual_source.config(text=folder)
        if not self.visual_output_dir: self.lbl_visual_output.config(text="Same as Source (Default)")
        self.refresh_file_list()

    def select_output_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.visual_output_dir = folder
            self.lbl_visual_output.config(text=folder)

    def refresh_file_list(self):
        if not self.visual_source_dir: return
        valid_exts = self.ext_imgs.union(self.ext_vids)
        try:
            files = [f for f in os.listdir(self.visual_source_dir) if os.path.splitext(f)[1].lower() in valid_exts]
            files.sort()
            self.image_files = files
        except Exception as e:
            messagebox.showerror("Error", str(e))
            return
        self.file_labels = {}
        self.file_renames_sorted = {}
        self.current_image_index = 0
        self.ribbon_widgets = {}
        for w in self.ribbon_inner.winfo_children(): w.destroy()
        if self.image_files:
            self.show_image()
            threading.Thread(target=self.generate_thumbnails_thread, daemon=True).start()
        else:
            self.image_canvas.delete("all")
            self.image_canvas.create_text(400, 300, text="No Media Found", fill="white")

    def show_image(self):
        if not self.image_files: return
        filename = self.image_files[self.current_image_index]
        self.lbl_counter.config(text=f"{self.current_image_index + 1} / {len(self.image_files)}")
        self.var_current_label.set(self.file_labels.get(filename, "Unmarked"))
        if filename in self.ribbon_widgets:
             self.ensure_ribbon_visible(self.ribbon_widgets[filename], self.ribbon_canvas, self.ribbon_inner)
        self.display_media_on_canvas(self.image_canvas, self.visual_source_dir, filename)

    def prev_image(self):
        if self.current_image_index > 0:
            self.current_image_index -= 1
            self.show_image()

    def next_image(self):
        if self.current_image_index < len(self.image_files) - 1:
            self.current_image_index += 1
            self.show_image()
            
    def open_current_file(self):
        if not self.image_files: return
        fname = self.image_files[self.current_image_index]
        self.open_file_external(self.visual_source_dir, fname)

    def save_label(self):
        if not self.image_files: return
        fname = self.image_files[self.current_image_index]
        lbl = self.var_current_label.get()
        self.file_labels[fname] = lbl
        if fname in self.ribbon_widgets:
            color = self.colors.get(lbl, "#e0e0e0")
            self.ribbon_widgets[fname].config(bg=color)

    def generate_thumbnails_thread(self):
        size = (80, 60)
        for idx, filename in enumerate(self.image_files):
            filepath = os.path.join(self.visual_source_dir, filename)
            thumb = self.create_thumbnail(filepath, size)
            if thumb:
                self.root.after(10, self.add_ribbon_item, idx, filename, thumb)
            if idx % 5 == 0: time.sleep(0.01)

    def add_ribbon_item(self, idx, filename, thumb):
        self.thumb_cache[filename] = thumb
        f = tk.Frame(self.ribbon_inner, bg=self.colors["Unmarked"], padx=3, pady=3)
        f.pack(side="left", fill="y", padx=1)
        btn = tk.Button(f, image=thumb, command=lambda: self.jump_to_file(filename), relief="flat", bd=0)
        btn.pack(fill="both", expand=True)
        self.ribbon_widgets[filename] = f
        if idx == self.current_image_index:
             self.ensure_ribbon_visible(f, self.ribbon_canvas, self.ribbon_inner)

    def jump_to_file(self, filename):
        if filename in self.image_files:
            self.current_image_index = self.image_files.index(filename)
            self.show_image()
            
    def open_rename_dialog(self):
        if not self.image_files: return
        fname = self.image_files[self.current_image_index]
        base, ext = os.path.splitext(fname)
        dlg = tk.Toplevel(self.root)
        dlg.title("Rename File")
        dlg.geometry("400x350")
        ttk.Label(dlg, text=f"Current: {fname}", font=("Arial", 10, "bold")).pack(pady=10)
        f_inputs = ttk.Frame(dlg)
        f_inputs.pack(pady=5)
        ttk.Label(f_inputs, text="Prefix:").grid(row=0, column=0)
        e_prefix = ttk.Entry(f_inputs, width=15)
        e_prefix.grid(row=0, column=1, padx=5)
        ttk.Label(f_inputs, text="Name:").grid(row=1, column=0)
        e_base = ttk.Entry(f_inputs, width=25)
        e_base.insert(0, base)
        e_base.grid(row=1, column=1, padx=5, pady=5)
        ttk.Label(f_inputs, text="Suffix:").grid(row=2, column=0)
        e_suffix = ttk.Entry(f_inputs, width=15)
        e_suffix.grid(row=2, column=1, padx=5)
        var_mode = tk.StringVar(value="original")
        f_opts = ttk.LabelFrame(dlg, text="Apply To")
        f_opts.pack(fill="x", padx=20, pady=10)
        ttk.Radiobutton(f_opts, text="Rename Original File (Immediately)", variable=var_mode, value="original").pack(anchor="w", padx=10, pady=2)
        ttk.Radiobutton(f_opts, text="Rename Sorted File Only (On Sort)", variable=var_mode, value="sorted").pack(anchor="w", padx=10, pady=2)
        def do_rename():
            new_name_base = e_prefix.get() + e_base.get() + e_suffix.get()
            new_full_name = new_name_base + ext
            if var_mode.get() == "original":
                src = os.path.join(self.visual_source_dir, fname)
                dst = os.path.join(self.visual_source_dir, new_full_name)
                try:
                    os.rename(src, dst)
                    self.image_files[self.current_image_index] = new_full_name
                    if fname in self.file_labels: self.file_labels[new_full_name] = self.file_labels.pop(fname)
                    if fname in self.ribbon_widgets: self.ribbon_widgets[new_full_name] = self.ribbon_widgets.pop(fname)
                    self.show_image() 
                    dlg.destroy()
                except Exception as e: messagebox.showerror("Rename Error", str(e))
            else:
                self.file_renames_sorted[fname] = new_full_name
                self.show_image()
                dlg.destroy()
        ttk.Button(dlg, text="Apply Rename", command=do_rename).pack(pady=10)

    def run_visual_sort(self):
        if not self.visual_source_dir: return
        out_root = self.visual_output_dir if self.visual_output_dir else self.visual_source_dir
        count = 0
        action = self.var_visual_action.get()
        include_related = self.var_move_related.get()
        for filename, label in self.file_labels.items():
            if label == "Unmarked": continue
            src = os.path.join(self.visual_source_dir, filename)
            if label == "Red": 
                try: os.remove(src)
                except Exception as e: print(f"Failed to delete {filename}: {e}"); continue
                if include_related:
                    base_orig = os.path.splitext(filename)[0]
                    related = [f for f in os.listdir(self.visual_source_dir) if f.startswith(base_orig) and f != filename]
                    for r_file in related:
                        try: os.remove(os.path.join(self.visual_source_dir, r_file))
                        except: pass
                count += 1
                continue
            dest_folder = os.path.join(out_root, label)
            if not os.path.exists(dest_folder): os.makedirs(dest_folder)
            target_name = self.file_renames_sorted.get(filename, filename)
            dst = os.path.join(dest_folder, target_name)
            try:
                if action == "move": shutil.move(src, dst)
                else: shutil.copy2(src, dst)
            except Exception as e: print(e); continue
            if include_related:
                base_orig = os.path.splitext(filename)[0]
                base_targ = os.path.splitext(target_name)[0]
                related = [f for f in os.listdir(self.visual_source_dir) if f.startswith(base_orig) and f != filename]
                for r_file in related:
                    r_ext = os.path.splitext(r_file)[1]
                    r_new_name = base_targ + r_ext
                    r_src = os.path.join(self.visual_source_dir, r_file)
                    r_dst = os.path.join(dest_folder, r_new_name)
                    try:
                        if action == "move": shutil.move(r_src, r_dst)
                        else: shutil.copy2(r_src, r_dst)
                    except: pass
            count += 1
        messagebox.showinfo("Sort Complete", f"Processed {count} files.\n(Red items were deleted)")
        self.refresh_file_list()

    # ==========================================
    #           TAB 3: SEQUENCE SORTER
    # ==========================================
    def init_sequence_tab(self):
        frame = self.tab_sequence
        ttk.Label(frame, text="Source Folder:").pack(anchor="w", padx=20, pady=(15, 0))
        f_src = ttk.Frame(frame)
        f_src.pack(fill="x", padx=20)
        self.seq_source = tk.StringVar()
        ttk.Entry(f_src, textvariable=self.seq_source).pack(side="left", fill="x", expand=True)
        ttk.Button(f_src, text="Browse", command=lambda: self.seq_source.set(filedialog.askdirectory())).pack(side="left")
        ttk.Label(frame, text="Sequence (e.g. 1210, 211, 15):").pack(anchor="w", padx=20, pady=(10, 0))
        self.seq_text = tk.Text(frame, height=5, font=("Arial", 10))
        self.seq_text.pack(fill="x", padx=20, pady=5)
        opts_frame = ttk.Frame(frame)
        opts_frame.pack(fill="x", padx=20, pady=5)
        ttk.Label(opts_frame, text="Prefix (e.g. IMG_):").grid(row=0, column=0, sticky="w")
        self.seq_prefix_var = tk.StringVar(value="IMG_")
        ttk.Entry(opts_frame, textvariable=self.seq_prefix_var, width=15).grid(row=1, column=0, sticky="w", padx=(0, 10))
        ttk.Label(opts_frame, text="Extensions (e.g. JPG,CR2):").grid(row=0, column=1, sticky="w")
        self.seq_ext_var = tk.StringVar(value="JPG,CR2,MP4,MOV")
        ttk.Entry(opts_frame, textvariable=self.seq_ext_var, width=25).grid(row=1, column=1, sticky="w")
        ttk.Label(frame, text="New Folder Name:").pack(anchor="w", padx=20, pady=(10,0))
        self.seq_target_name = tk.StringVar(value="Selected_Photos")
        ttk.Entry(frame, textvariable=self.seq_target_name).pack(fill="x", padx=20)
        self.seq_action_var = tk.StringVar(value="copy")
        f_act = ttk.Frame(frame)
        f_act.pack(fill="x", padx=20, pady=10)
        ttk.Radiobutton(f_act, text="Copy", variable=self.seq_action_var, value="copy").pack(side="left", padx=(0, 20))
        ttk.Radiobutton(f_act, text="Move", variable=self.seq_action_var, value="move").pack(side="left")
        ttk.Button(frame, text="Process Sequence", command=self.run_sequence_logic).pack(pady=10)
        self.seq_log = tk.Text(frame, height=10, state="disabled", bg="#f0f0f0", font=("Consolas", 9))
        self.seq_log.pack(fill="both", expand=True, padx=20, pady=(0, 10))

    def run_sequence_logic(self):
        threading.Thread(target=self.process_seq_files, daemon=True).start()

    def process_seq_files(self):
        source_dir = self.seq_source.get()
        if not source_dir or not os.path.exists(source_dir): messagebox.showerror("Error", "Please select a valid source folder."); return
        raw_seq = self.seq_text.get("1.0", "end").strip()
        if not raw_seq: messagebox.showerror("Error", "Please enter a number sequence."); return
        prefix = self.seq_prefix_var.get().strip()
        exts = [e.strip().replace(".", "") for e in self.seq_ext_var.get().split(",")]
        target_name = self.seq_target_name.get().strip()
        action = self.seq_action_var.get()
        target_dir = os.path.join(source_dir, target_name)
        if not os.path.exists(target_dir):
            try: os.makedirs(target_dir)
            except Exception as e: messagebox.showerror("Error", f"Could not create folder: {e}"); return
        self.log_seq(f"Starting processing...")
        numbers = [x.strip() for x in raw_seq.replace("\n", ",").split(",") if x.strip()]
        last_full = ""
        success = 0
        missing = 0
        for num_str in numbers:
            current_full = ""
            if not last_full: current_full = num_str
            else:
                if len(num_str) < len(last_full): prefix_len = len(last_full) - len(num_str); current_full = last_full[:prefix_len] + num_str
                else: current_full = num_str
            last_full = current_full
            for ext in exts:
                filename = f"{prefix}{current_full}.{ext}"
                src_path = os.path.join(source_dir, filename)
                dst_path = os.path.join(target_dir, filename)
                if os.path.exists(src_path):
                    try:
                        if action == "move": shutil.move(src_path, dst_path); self.log_seq(f"[MOVED] {filename}")
                        else: shutil.copy2(src_path, dst_path); self.log_seq(f"[COPIED] {filename}")
                        success += 1
                    except Exception as e: self.log_seq(f"[ERR] {filename}: {str(e)}")
                else: self.log_seq(f"[MISSING] {filename}"); missing += 1
        self.log_seq("-" * 30)
        self.log_seq(f"Done! Success: {success}, Missing: {missing}")
        messagebox.showinfo("Complete", f"Operation finished.\nSuccess: {success}\nMissing: {missing}")

    def log_seq(self, message):
        self.seq_log.config(state="normal")
        self.seq_log.insert("end", message + "\n")
        self.seq_log.see("end")
        self.seq_log.config(state="disabled")

if __name__ == "__main__":
    root = tk.Tk()
    app = PhotoOrganizerApp(root)
    root.mainloop()
