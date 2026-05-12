import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import re
import os
import math

class CalibradorPivoteCAM:
    def __init__(self, root):
        self.root = root
        self.root.title("Calibrador de Pivote + Filtro de Escenarios (Diagnóstico V7)")
        self.root.geometry("1200x850")
        try:
            self.root.state('zoomed')
        except:
            pass
        self.root.configure(bg="#2b2b2b")

        self.piezas = []
        self.current_idx = 0
        self.escala = 1.0
        self.offset_x = 0
        self.offset_y = 0
        self.lector_window = None
        
        self.modo_visual = tk.StringVar(value="diag_base")
        
        # NUEVO: Diccionario para controlar la visibilidad de cada escenario
        self.escenarios_visibles = {
            "SUP-IZQ": tk.BooleanVar(value=True),
            "SUP-DER": tk.BooleanVar(value=True),
            "INF-DER": tk.BooleanVar(value=True),
            "INF-IZQ": tk.BooleanVar(value=True),
            "CENTRO":  tk.BooleanVar(value=True)
        }

        self.crear_interfaz()

    def crear_interfaz(self):
        fr_top = tk.Frame(self.root, bg="#ece9d8", pady=10, bd=2, relief="raised")
        fr_top.pack(fill="x")
        
        # Botones de archivos
        fr_files = tk.Frame(fr_top, bg="#ece9d8")
        fr_files.pack(side="left", padx=10)
        tk.Button(fr_files, text="📂 ABRIR NC", command=self.cargar_nc, font=("Arial", 10, "bold"), bg="#0055aa", fg="white", width=12).pack(pady=2)
        tk.Button(fr_files, text="📊 LECTOR", command=self.abrir_lector, font=("Arial", 10, "bold"), bg="#008040", fg="white", width=12).pack(pady=2)
        
        # Panel de Modos de Rotación (Izquierda)
        fr_modos = tk.Frame(fr_top, bg="#ece9d8", bd=1, relief="sunken", padx=10, pady=5)
        fr_modos.pack(side="left", padx=10)
        tk.Label(fr_modos, text="Modo de Rotación:", bg="#ece9d8", font=("Arial", 9, "bold")).pack(anchor="w")
        tk.Radiobutton(fr_modos, text="1. Original (NC)", variable=self.modo_visual, value="diag_base", command=self.renderizar_pieza, bg="#ece9d8", font=("Arial", 9)).pack(anchor="w")
        tk.Radiobutton(fr_modos, text="2. Desfase +90°", variable=self.modo_visual, value="diag_90", command=self.renderizar_pieza, bg="#ece9d8", font=("Arial", 9)).pack(anchor="w")
        
        fr_opt3 = tk.Frame(fr_modos, bg="#ece9d8")
        fr_opt3.pack(anchor="w")
        tk.Radiobutton(fr_opt3, text="3. Offset:", variable=self.modo_visual, value="diag_offset", command=self.renderizar_pieza, bg="#ece9d8", font=("Arial", 9)).pack(side="left")
        self.ent_offset = tk.Entry(fr_opt3, width=5, justify="center")
        self.ent_offset.insert(0, "180")
        self.ent_offset.pack(side="left", padx=2)
        self.ent_offset.bind("<Return>", lambda e: [self.modo_visual.set("diag_offset"), self.renderizar_pieza()])

        # NUEVO: Panel de Visibilidad de Escenarios (Centro)
        fr_vis = tk.Frame(fr_top, bg="#ece9d8", bd=1, relief="sunken", padx=10, pady=5)
        fr_vis.pack(side="left", padx=10)
        tk.Label(fr_vis, text="Filtrar Posiciones Visibles:", bg="#ece9d8", font=("Arial", 9, "bold")).pack(anchor="w")
        
        colores = {"SUP-IZQ": "#cc0000", "SUP-DER": "#008800", "INF-DER": "#cc7a00", "INF-IZQ": "#cc00cc", "CENTRO": "#007acc"}
        for key, var in self.escenarios_visibles.items():
            tk.Checkbutton(fr_vis, text=key, variable=var, command=self.renderizar_pieza, 
                           bg="#ece9d8", font=("Arial", 8, "bold"), fg=colores[key], activeforeground=colores[key]).pack(side="left", padx=2)

        self.lbl_file = tk.Label(fr_top, text="Sin archivo", bg="#ece9d8", font=("Arial", 9, "italic"))
        self.lbl_file.pack(side="right", padx=20)

        # Visor
        self.canvas = tk.Canvas(self.root, bg="#1a1a1a", cursor="crosshair")
        self.canvas.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.canvas.bind("<ButtonPress-2>", lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind("<B2-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        self.canvas.bind("<MouseWheel>", self.hacer_zoom)

        # Navegación
        fr_nav = tk.Frame(self.root, bg="#ece9d8", pady=10)
        fr_nav.pack(fill="x")
        tk.Button(fr_nav, text="◄◄ PRIMERO", command=self.first_piece, width=12).pack(side="left", padx=5)
        tk.Button(fr_nav, text="◄ ANT", command=self.prev_piece, width=10).pack(side="left")
        
        fr_jump = tk.Frame(fr_nav, bg="#ece9d8")
        fr_jump.pack(side="left", expand=True)
        self.ent_seq = tk.Entry(fr_jump, width=6, justify="center", font=("Arial", 11, "bold"))
        self.ent_seq.pack(side="left", padx=5)
        self.ent_seq.bind("<Return>", self.jump_to_piece)
        self.lbl_seq_total = tk.Label(fr_jump, text="/ 0", bg="#ece9d8", font=("Arial", 10))
        self.lbl_seq_total.pack(side="left", padx=10)
        tk.Button(fr_jump, text="🎯 CENTRAR", command=self.centrar_vista_inicial, bg="#e68a00", fg="white", font=("Arial", 9, "bold")).pack(side="left", padx=10)

        tk.Button(fr_nav, text="SIG ►", command=self.next_piece, width=10).pack(side="right")
        tk.Button(fr_nav, text="ÚLTIMO ►►", command=self.last_piece, width=12).pack(side="right", padx=5)

    def renderizar_pieza(self):
        self.canvas.delete("all")
        if not self.piezas: return
        pieza = self.piezas[self.current_idx]
        self.ent_seq.delete(0, tk.END); self.ent_seq.insert(0, str(self.current_idx + 1))
        self.lbl_seq_total.config(text=f"/ {len(self.piezas)}")

        # 1. Geometría
        for sp in pieza["subpaths"]:
            for i in range(len(sp)-1):
                p1, p2 = self.to_px(sp[i][0], sp[i][1]), self.to_px(sp[i+1][0], sp[i+1][1])
                self.canvas.create_line(p1[0], p1[1], p2[0], p2[1], fill="#444", width=2)

        # 2. Etiquetas Fantasmas Filtradas
        if pieza.get("labels"):
            l = pieza["labels"][0]
            ax, ay = l["x1"], l["y1"]
            dx, dy = l["x2"]-l["x1"], l["y2"]-l["y1"]
            
            real_ang_rad = math.atan2(dy, dx)
            modo = self.modo_visual.get()
            ang_rad = real_ang_rad
            
            if modo == "diag_90": ang_rad += math.radians(90)
            elif modo == "diag_offset":
                try: ang_rad += math.radians(float(self.ent_offset.get()))
                except: pass
                
            cos_a, sin_a = math.cos(ang_rad), math.sin(ang_rad)
            W, H = 500, 250
            px_a, py_a = self.to_px(ax, ay)
            self.canvas.create_oval(px_a-5, py_a-5, px_a+5, py_a+5, fill="white", outline="black")
            
            # Lista de datos de cada escenario
            escenarios_data = [
                ("SUP-IZQ", W/2, -H/2, "#ff0000"),
                ("SUP-DER", -W/2, -H/2, "#00ff00"), 
                ("INF-DER", -W/2, H/2, "#ff9900"), 
                ("INF-IZQ", W/2, H/2, "#ff00ff"), 
                ("CENTRO", 0, 0, "#00aaff")
            ]

            for nom, ox, oy, col in escenarios_data:
                # SOLO DIBUJAR SI EL CHECKBUTTON ESTÁ MARCADO
                if self.escenarios_visibles[nom].get():
                    cx, cy = ax + (ox*cos_a - oy*sin_a), ay + (ox*sin_a + oy*cos_a)
                    v = [(-W/2, H/2), (W/2, H/2), (W/2, -H/2), (-W/2, -H/2)]
                    pts = []
                    for lx, ly in v:
                        gx, gy = cx + (lx*cos_a - ly*sin_a), cy + (lx*sin_a + ly*cos_a)
                        pts.append(self.to_px(gx, gy))
                    
                    self.canvas.create_polygon(pts, fill="", outline=col, width=2, dash=(4,2))
                    self.canvas.create_oval(pts[0][0]-4, pts[0][1]-4, pts[0][0]+4, pts[0][1]+4, fill=col)
                    ccx, ccy = self.to_px(cx, cy)
                    self.canvas.create_text(ccx, ccy, text=nom, fill=col, font=("Arial", 8, "bold"))

    def to_px(self, nx, ny):
        return (nx*self.escala+self.offset_x, self.offset_y-(ny*self.escala))

    def cargar_nc(self):
        filepath = filedialog.askopenfilename(filetypes=[("NC Files", "*.NC *.nc")])
        if not filepath: return
        try:
            with open(filepath, 'r', encoding='latin-1') as f: contenido = f.read()
            raw_tokens = contenido.split('*')
            self.piezas = []
            current_piece = None
            pat_geom, pat_n = re.compile(r"^X(\d+)Y(\d+)$"), re.compile(r"^N(\d+)$")
            i = 0
            while i < len(raw_tokens):
                token = raw_tokens[i].strip()
                m_n = pat_n.fullmatch(token)
                if m_n:
                    current_piece = {"num": m_n.group(1), "subpaths": [], "labels": []}
                    self.piezas.append(current_piece)
                elif current_piece:
                    if token == "M13" or (token == "M15" and i+1 < len(raw_tokens) and raw_tokens[i+1].strip() == "M13"):
                        offset = 1 if token == "M15" else 0
                        if i + offset + 4 < len(raw_tokens):
                            pos1, txt, pos2 = raw_tokens[i+offset+2], raw_tokens[i+offset+3], raw_tokens[i+offset+4]
                            m1, m2 = re.search(r"X(\d+)Y(\d+)", pos1), re.search(r"X(\d+)Y(\d+)", pos2)
                            if m1 and m2:
                                current_piece["labels"].append({"x1": int(m1.group(1)), "y1": int(m1.group(2)), "x2": int(m2.group(1)), "y2": int(m2.group(2)), "text": txt})
                                i += offset + 5; continue
                    elif pat_geom.fullmatch(token):
                        m = pat_geom.fullmatch(token)
                        if not current_piece["subpaths"]: current_piece["subpaths"].append([])
                        current_piece["subpaths"][-1].append((int(m.group(1)), int(m.group(2))))
                i += 1
            self.piezas = [p for p in self.piezas if p["subpaths"]]
            self.lbl_file.config(text=os.path.basename(filepath))
            self.current_idx = 0
            if self.lector_window: self.actualizar_datos_lector()
            self.centrar_vista_inicial()
        except Exception as e: messagebox.showerror("Error", str(e))

    def abrir_lector(self):
        if self.lector_window and self.lector_window.winfo_exists():
            self.lector_window.lift(); return
        self.lector_window = tk.Toplevel(self.root)
        self.lector_window.title("Lector de Etiquetas")
        self.lector_window.geometry("800x500")
        columns = ("Sec", "E1", "E2", "E3", "E4")
        self.tree = ttk.Treeview(self.lector_window, columns=columns, show="headings")
        for col in columns: self.tree.heading(col, text=col); self.tree.column(col, width=100, anchor="center")
        sb = ttk.Scrollbar(self.lector_window, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=sb.set); self.tree.pack(side="left", fill="both", expand=True); sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)
        self.actualizar_datos_lector()

    def actualizar_datos_lector(self):
        if not hasattr(self, 'tree'): return
        self.tree.delete(*self.tree.get_children())
        for idx, p in enumerate(self.piezas):
            labels = [l["text"] for l in p.get("labels", [])]
            while len(labels) < 4: labels.append("-")
            self.tree.insert("", "end", values=(idx+1, labels[0], labels[1], labels[2], labels[3]), tags=(idx,))

    def on_tree_select(self, event):
        sel = self.tree.selection()
        if sel: self.current_idx = int(self.tree.item(sel[0], "tags")[0]); self.centrar_vista_inicial()

    def centrar_vista_inicial(self):
        if not self.piezas: return
        p = self.piezas[self.current_idx]
        xs = [pt[0] for sp in p["subpaths"] for pt in sp]
        ys = [pt[1] for sp in p["subpaths"] for pt in sp]
        min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
        cw, ch = self.canvas.winfo_width() or 1000, self.canvas.winfo_height() or 600
        self.escala = min((cw*0.75)/(max_x-min_x), (ch*0.75)/(max_y-min_y))
        self.offset_x, self.offset_y = (cw/2)-(((max_x+min_x)/2)*self.escala), (ch/2)+(((max_y+min_y)/2)*self.escala)
        self.renderizar_pieza()

    def hacer_zoom(self, event):
        f = 1.1 if event.delta > 0 else 0.9
        self.escala *= f; self.renderizar_pieza()

    def first_piece(self): self.current_idx = 0; self.centrar_vista_inicial()
    def last_piece(self): self.current_idx = len(self.piezas)-1; self.centrar_vista_inicial()
    def prev_piece(self): 
        if self.current_idx > 0: self.current_idx -= 1; self.centrar_vista_inicial()
    def next_piece(self):
        if self.current_idx < len(self.piezas)-1: self.current_idx += 1; self.centrar_vista_inicial()
    def jump_to_piece(self, e=None):
        try:
            v = int(self.ent_seq.get())-1
            if 0 <= v < len(self.piezas): self.current_idx = v; self.centrar_vista_inicial()
        except: pass

if __name__ == "__main__":
    root = tk.Tk(); app = CalibradorPivoteCAM(root); root.mainloop()
