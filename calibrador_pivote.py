import tkinter as tk
from tkinter import filedialog, messagebox
import re
import os
import math

class CalibradorPivoteCAM:
    def __init__(self, root):
        self.root = root
        self.root.title("Calibrador de Punto de Pivote (Diagnóstico Gerber)")
        self.root.geometry("1000x700")
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

        self.crear_interfaz()

    def crear_interfaz(self):
        fr_top = tk.Frame(self.root, bg="#ece9d8", pady=10)
        fr_top.pack(fill="x")
        
        tk.Button(fr_top, text="📂 ABRIR ARCHIVO .NC", command=self.cargar_nc, font=("Arial", 12, "bold"), bg="#0055aa", fg="white").pack(side="left", padx=20)
        self.lbl_file = tk.Label(fr_top, text="Ningún archivo cargado", bg="#ece9d8", font=("Arial", 11, "italic"))
        self.lbl_file.pack(side="left", padx=20)

        # Visor Principal
        self.canvas = tk.Canvas(self.root, bg="#1a1a1a", cursor="crosshair")
        self.canvas.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Pan y Zoom
        self.canvas.bind("<ButtonPress-2>", lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind("<B2-Motion>", lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        self.canvas.bind("<MouseWheel>", self.hacer_zoom)

        # Navegación Avanzada
        fr_bottom = tk.Frame(self.root, bg="#ece9d8", pady=10)
        fr_bottom.pack(fill="x")
        
        tk.Button(fr_bottom, text="◄◄ PRIMERO", command=self.first_piece, font=("Arial", 10, "bold"), width=12).pack(side="left", padx=10)
        tk.Button(fr_bottom, text="◄ ANTERIOR", command=self.prev_piece, font=("Arial", 10, "bold"), width=12).pack(side="left", padx=5)
        
        # Centro: Salto a pieza específica
        fr_seq = tk.Frame(fr_bottom, bg="#ece9d8")
        fr_seq.pack(side="left", expand=True)
        
        tk.Label(fr_seq, text="Pieza:", bg="#ece9d8", font=("Arial", 12, "bold")).pack(side="left")
        self.ent_seq = tk.Entry(fr_seq, width=5, font=("Arial", 12, "bold"), justify="center")
        self.ent_seq.pack(side="left", padx=5)
        self.ent_seq.bind("<Return>", self.jump_to_piece) # Permite saltar apretando Enter
        self.lbl_seq_total = tk.Label(fr_seq, text="/ 0", bg="#ece9d8", font=("Arial", 12, "bold"), fg="#990000")
        self.lbl_seq_total.pack(side="left")

        tk.Button(fr_bottom, text="ÚLTIMO ►►", command=self.last_piece, font=("Arial", 10, "bold"), width=12).pack(side="right", padx=10)
        tk.Button(fr_bottom, text="SIGUIENTE ►", command=self.next_piece, font=("Arial", 10, "bold"), width=12).pack(side="right", padx=5)

        # Atajos de teclado
        self.root.bind("<Left>", lambda e: self.prev_piece())
        self.root.bind("<Right>", lambda e: self.next_piece())
        self.root.bind("<Home>", lambda e: self.first_piece())
        self.root.bind("<End>", lambda e: self.last_piece())

    def hacer_zoom(self, event):
        factor = 1.1 if event.delta > 0 else 0.9 
        self.escala *= factor
        cw, ch = self.canvas.canvasx(event.x), self.canvas.canvasy(event.y)
        self.offset_x = (self.offset_x - cw) * factor + cw
        self.offset_y = (self.offset_y - ch) * factor + ch
        self.renderizar_pieza()

    def cargar_nc(self):
        filepath = filedialog.askopenfilename(title="Seleccionar Archivo NC", filetypes=[("NC Files", "*.NC *.nc")])
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
                    i += 1; continue

                is_label = False
                if current_piece:
                    if token == "M13": is_label = True; offset = 0
                    elif token == "M15" and i+1 < len(raw_tokens) and raw_tokens[i+1].strip() == "M13": is_label = True; offset = 1
                    
                    if is_label and i + offset + 4 < len(raw_tokens):
                        pos1, pos2 = raw_tokens[i + offset + 2], raw_tokens[i + offset + 4]
                        if "M31" in pos1 and "M31" in pos2:
                            m1, m2 = re.match(r"^X(\d+)Y(\d+)M31$", pos1.strip()), re.match(r"^X(\d+)Y(\d+)M31$", pos2.strip())
                            if m1 and m2:
                                current_piece["labels"].append({
                                    "x1": int(m1.group(1)), "y1": int(m1.group(2)),
                                    "x2": int(m2.group(1)), "y2": int(m2.group(2)),
                                    "text": raw_tokens[i + offset + 3]
                                })
                                i += offset + 6; continue

                if current_piece:
                    if token == "M15": current_piece["subpaths"].append([]); i += 1; continue
                    elif token == "M14": i += 1; continue
                    elif pat_geom.fullmatch(token):
                        m_geom = pat_geom.fullmatch(token)
                        if current_piece["subpaths"]: current_piece["subpaths"][-1].append((int(m_geom.group(1)), int(m_geom.group(2))))
                        i += 1; continue
                i += 1

            for p in self.piezas: p["subpaths"] = [sp for sp in p["subpaths"] if len(sp) > 0]
            self.lbl_file.config(text=os.path.basename(filepath))
            
            if not self.piezas: return messagebox.showwarning("Aviso", "No se encontraron piezas.")
            
            self.current_idx = 0
            self.centrar_vista_inicial()
            
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def centrar_vista_inicial(self):
        pieza = self.piezas[self.current_idx]
        min_x = min((pt[0] for sp in pieza.get("subpaths", []) for pt in sp), default=float('inf'))
        max_x = max((pt[0] for sp in pieza.get("subpaths", []) for pt in sp), default=float('-inf'))
        min_y = min((pt[1] for sp in pieza.get("subpaths", []) for pt in sp), default=float('inf'))
        max_y = max((pt[1] for sp in pieza.get("subpaths", []) for pt in sp), default=float('-inf'))

        if min_x == float('inf'): return

        w_pieza, h_pieza = max_x - min_x, max_y - min_y
        cw, ch = self.canvas.winfo_width(), self.canvas.winfo_height()
        if cw < 10: cw, ch = 1000, 600

        self.escala = min((cw * 0.8) / w_pieza, (ch * 0.8) / h_pieza)
        self.offset_x = (cw - (w_pieza * self.escala)) / 2 - (min_x * self.escala)
        self.offset_y = (ch - (h_pieza * self.escala)) / 2 + (max_y * self.escala)
        
        self.renderizar_pieza()

    def actualizar_indicador_seq(self):
        self.ent_seq.delete(0, tk.END)
        self.ent_seq.insert(0, str(self.current_idx + 1))
        self.lbl_seq_total.config(text=f"/ {len(self.piezas)}")

    def renderizar_pieza(self):
        self.canvas.delete("all")
        if not self.piezas: return
        
        pieza = self.piezas[self.current_idx]
        self.actualizar_indicador_seq()

        # 1. Dibujar la geometría de la pieza en color gris
        for sp in pieza.get("subpaths", []):
            for i in range(len(sp) - 1):
                x1, y1 = sp[i][0] * self.escala + self.offset_x, self.offset_y - (sp[i][1] * self.escala)
                x2, y2 = sp[i+1][0] * self.escala + self.offset_x, self.offset_y - (sp[i+1][1] * self.escala)
                self.canvas.create_line(x1, y1, x2, y2, fill="#555555", width=2.0)

        # 2. Lógica de las 5 Etiquetas Fantasmas
        if pieza.get("labels"):
            l_ref = pieza["labels"][0]
            
            # PUNTO ANCLA (X1, Y1) original del archivo
            ax = l_ref["x1"]
            ay = l_ref["y1"]
            
            # CALCULAR EL ÁNGULO REAL DE LA ETIQUETA EN EL ARCHIVO NC
            dx = l_ref["x2"] - l_ref["x1"]
            dy = l_ref["y2"] - l_ref["y1"]
            ang_rad = math.atan2(dy, dx)
            
            cos_a = math.cos(ang_rad)
            sin_a = math.sin(ang_rad)
            
            W, H = 500, 250 # Tamaño simulado del bloque de etiquetas
            
            def to_px(nx, ny): 
                return (nx * self.escala + self.offset_x, self.offset_y - (ny * self.escala))

            # Dibujamos el ANCLA (Punto Blanco)
            px_a, py_a = to_px(ax, ay)
            self.canvas.create_oval(px_a-6, py_a-6, px_a+6, py_a+6, fill="white")
            self.canvas.create_text(px_a, py_a-20, text="📍 ANCLA ORIGINAL", fill="white", font=("Arial", 10, "bold"))

            # Escenarios (Nombre, offset_X_centro, offset_Y_centro, color)
            escenarios = [
                ("SUP-IZQ",  W/2, -H/2, "#ff0000"), # Rojo
                ("SUP-DER", -W/2, -H/2, "#00ff00"), # Verde
                ("INF-DER", -W/2,  H/2, "#ff9900"), # Naranja
                ("INF-IZQ",  W/2,  H/2, "#ff00ff"), # Magenta
                ("CENTRO",     0,    0, "#00aaff")  # Azul
            ]

            for nombre, off_cx, off_cy, color in escenarios:
                # 1. Rotamos el CENTRO de la caja para que orbite el ancla
                cx = ax + (off_cx * cos_a - off_cy * sin_a)
                cy = ay + (off_cx * sin_a + off_cy * cos_a)
                
                # 2. Definimos los 4 vértices (El primero es la esquina Superior-Izquierda, punto de inicio de lectura)
                locales = [
                    (-W/2,  H/2), # [0] Sup-Izq
                    ( W/2,  H/2), # [1] Sup-Der
                    ( W/2, -H/2), # [2] Inf-Der
                    (-W/2, -H/2)  # [3] Inf-Izq
                ]
                
                puntos_globales = []
                for lx, ly in locales:
                    gx = cx + (lx * cos_a - ly * sin_a)
                    gy = cy + (lx * sin_a + ly * cos_a)
                    puntos_globales.append(to_px(gx, gy))
                
                # Dibujamos la caja rotada
                self.canvas.create_polygon(
                    puntos_globales[0][0], puntos_globales[0][1],
                    puntos_globales[1][0], puntos_globales[1][1],
                    puntos_globales[2][0], puntos_globales[2][1],
                    puntos_globales[3][0], puntos_globales[3][1],
                    fill="", outline=color, width=2, dash=(4,4)
                )
                
                # CÍRCULO INDICADOR DE ROTACIÓN: Se clava en el vértice [0] (Superior-Izquierdo local)
                px_ini, py_ini = puntos_globales[0]
                self.canvas.create_oval(px_ini-5, py_ini-5, px_ini+5, py_ini+5, fill=color, outline="white", width=1)
                
                # Texto adentro de la caja
                ccx, ccy = to_px(cx, cy)
                self.canvas.create_text(ccx, ccy, text=f"Si Ancla =\n{nombre}", fill=color, font=("Arial", 9, "bold"), justify="center")

    # ================= MÉTODOS DE NAVEGACIÓN =================
    def prev_piece(self):
        if self.current_idx > 0:
            self.current_idx -= 1
            self.centrar_vista_inicial()

    def next_piece(self):
        if self.current_idx < len(self.piezas) - 1:
            self.current_idx += 1
            self.centrar_vista_inicial()

    def first_piece(self):
        if self.piezas:
            self.current_idx = 0
            self.centrar_vista_inicial()

    def last_piece(self):
        if self.piezas:
            self.current_idx = len(self.piezas) - 1
            self.centrar_vista_inicial()

    def jump_to_piece(self, event=None):
        if not self.piezas: return
        try:
            val = int(self.ent_seq.get()) - 1
            if 0 <= val < len(self.piezas):
                self.current_idx = val
                self.centrar_vista_inicial()
            else:
                messagebox.showwarning("Aviso", "Número de pieza fuera de rango.")
                self.actualizar_indicador_seq()
        except ValueError:
            self.actualizar_indicador_seq()

if __name__ == "__main__":
    root = tk.Tk()
    app = CalibradorPivoteCAM(root)
    root.mainloop()
