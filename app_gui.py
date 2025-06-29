import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext, filedialog
import threading
import time
import os
import ui_constants as const
import sys
import subprocess
# --- LIBRERÍAS DE TERCEROS ---
from PIL import Image, ImageTk
from cryptography.fernet import Fernet
from mysql.connector import Error as MySQLError
from datetime import datetime

# --- NUESTROS MÓDULOS ---
from db_manager import DatabaseManager
from services import ServicesManager
from config_handler import load_key
from contactos_tab import ContactosTab
from multas_tab import MultasTab
from mensajes_tab import MensajesTab
from settings_window import SettingsWindow

# Añade este import


def resource_path(relative_path):
    """ Obtiene la ruta absoluta al recurso, funciona para desarrollo y para PyInstaller """
    try:
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_mysql_tool_path(tool_name):
    """ Devuelve la ruta completa a la herramienta de MySQL (dump o client) """
    # Primero, busca la herramienta dentro de nuestra carpeta empaquetada
    bundled_path = resource_path(os.path.join('mysql_deps', tool_name))
    if os.path.exists(bundled_path):
        return bundled_path
    # Si no la encuentra, devuelve solo el nombre para que el sistema la busque en el PATH
    return tool_name


class App:
    """
    Clase principal de la aplicación. Actúa como el orquestador o "cerebro"
    que inicializa y coordina los diferentes componentes.
    """

    def __init__(self, root, config):
        self.root = root
        self.config = config
        self.root.title("SAR-PM")
        self.root.geometry("1200x850")

        try:
            key = load_key()
            self.fernet = Fernet(key)
        except Exception as e:
            messagebox.showerror(
                "Error crítico", f"No se pudo cargar la clave de cifrado: {e}")
            self.root.destroy()
            return

        try:
            self.db_manager = DatabaseManager(self.config, self.fernet)
            log_message = "Pool de DB conectado"
        except MySQLError as e:
            messagebox.showerror(
                "Error Crítico de BD", f"No se pudo crear el pool de conexiones a MySQL: {e}")
            self.db_manager = None
            log_message = f"Error de BD: {e}"

        self.services_manager = ServicesManager(self.config, self.fernet)

        # Variables de estado que pertenecen a la App principal
        self.stats_total_contacts = tk.StringVar(value="--")
        self.stats_pending_fines = tk.StringVar(value="--")
        self.stats_monthly_revenue = tk.StringVar(value="--")
        self.multa_descripciones = []  # Usado por MultasTab, pero cargado centralmente
        self.driver = None  # Driver de Selenium, gestionado centralmente
        self.console_visible = True

        self.menubar = tk.Menu(self.root)
        self.root.config(menu=self.menubar)

        sistema_menu = tk.Menu(self.menubar, tearoff=0)
        self.menubar.add_cascade(label="Sistema", menu=sistema_menu)
        sistema_menu.add_command(
            label="Configuración...", command=self.open_settings_window)
        sistema_menu.add_separator()
        sistema_menu.add_command(
            label="Crear Backup...", command=self.crear_backup)
        sistema_menu.add_command(
            label="Restaurar desde Backup...", command=self.restaurar_backup)
        sistema_menu.add_separator()
        sistema_menu.add_command(label="Salir", command=self.on_closing)

        self.create_widgets()
        self.log_to_console("¡Aplicación Iniciada!")
        self.log_to_console(log_message)

        # Cargas iniciales que gestiona la App
        if self.db_manager:
            self.db_manager.init_db()
            self._cargar_dashboard_stats_thread()
            # La carga de descripciones se gestiona aquí porque es un recurso compartido
            self.root.after(250, self._cargar_descripciones_thread)

    def create_widgets(self):

        self.root.configure(bg=const.MAIN_BG)
        sidebar_frame = tk.Frame(self.root, bg=const.SIDEBAR_BG, width=200)
        sidebar_frame.pack(side="left", fill="y")
        sidebar_frame.pack_propagate(False)

        main_frame = tk.Frame(self.root, bg=const.MAIN_BG)
        main_frame.pack(side="right", fill="both", expand=True)

        self.content_area = tk.Frame(main_frame, bg=const.MAIN_BG)
        self.content_area.pack(fill="both", expand=True, padx=10, pady=(10, 0))
        self.content_area.grid_rowconfigure(0, weight=1)
        self.content_area.grid_columnconfigure(0, weight=1)

        # Creación de Frames y Botones de Barra Lateral
        self.content_frames = {}
        self.sidebar_buttons = {}
        tab_names = ["Inicio", "Contactos", "Multas", "Mensajes y Envío"]

        # Creamos el Dashboard
        self.content_frames["Inicio"] = tk.Frame(
            self.content_area, bg=const.ACTIVE_TAB_BG)
        self.populate_dashboard_frame()

        # Instanciamos nuestras clases personalizadas para cada pestaña
        self.contactos_tab = ContactosTab(self.content_area, controller=self)
        self.content_frames["Contactos"] = self.contactos_tab

        self.multas_tab = MultasTab(self.content_area, controller=self)
        self.content_frames["Multas"] = self.multas_tab

        self.mensajes_tab = MensajesTab(self.content_area, controller=self)
        self.content_frames["Mensajes y Envío"] = self.mensajes_tab

        for name in tab_names:
            button = tk.Button(sidebar_frame, text=name, font=("Segoe UI", 11, "bold"), bg=const.BUTTON_NORMAL_BG, fg=const.BUTTON_FG,
                               activebackground=const.BUTTON_ACTIVE_BG, activeforeground=const.BUTTON_FG, relief="flat", borderwidth=0, anchor="w", padx=20, pady=10)
            button.pack(fill="x", pady=2)
            self.sidebar_buttons[name] = button
            self.content_frames[name].grid(row=0, column=0, sticky="nsew")

        # Logo
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            logo_path = resource_path(
                os.path.join('assets', 'logo_sidebar.png'))
            logo_image_original = Image.open(logo_path)
            logo_image_resized = logo_image_original.resize(
                (150, 150), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo_image_resized)
            logo_label = tk.Label(
                sidebar_frame, image=self.logo_photo, bg=const.SIDEBAR_BG)
            logo_label.pack(side=tk.BOTTOM, pady=20, padx=10)
        except Exception as e:
            self.log_to_console(
                f"Advertencia: No se pudo cargar el logo: {e}", "warning")

        # Lógica para mostrar pestañas
        def show_content(name):
            for btn in self.sidebar_buttons.values():
                btn.config(bg=const.BUTTON_NORMAL_BG)
            self.sidebar_buttons[name].config(bg=const.BUTTON_ACTIVE_BG)
            self.content_frames[name].tkraise()

        for name in tab_names:
            self.sidebar_buttons[name].config(
                command=lambda n=name: show_content(n))

        # Consola
        self.console_container = tk.Frame(main_frame, bg=const.MAIN_BG)
        self.console_container.pack(side="bottom", fill="x", padx=10, pady=10)
        self.log_area = scrolledtext.ScrolledText(
            self.console_container, state='disabled', height=8, bg="#34495E", fg="#ECF0F1", relief="flat")
        self.log_area.pack(fill="both", expand=True)
        console_button_style = const.BUTTON_STYLE.copy()
        console_button_style['bg'] = const.SIDEBAR_BG
        self.toggle_console_button = tk.Button(
            self.console_container, text="Ocultar Consola", **console_button_style, command=self.toggle_console_visibility)
        self.toggle_console_button.pack(fill='x', pady=(5, 0))

        show_content("Inicio")

    def open_settings_window(self):
        """Abre la ventana de configuración."""
        # Al pasar 'self', le damos a la ventana acceso a la app principal
        SettingsWindow(self)

    def _center_toplevel(self, toplevel_window):
        toplevel_window.update_idletasks()
        root_x = self.root.winfo_x()
        root_y = self.root.winfo_y()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()
        win_width = toplevel_window.winfo_width()
        win_height = toplevel_window.winfo_height()
        x = root_x + (root_width // 2) - (win_width // 2)
        y = root_y + (root_height // 2) - (win_height // 2)
        toplevel_window.geometry(f'+{x}+{y}')

    def log_to_console(self, message, level="info"):
        if not hasattr(self, 'log_area'):
            return
        timestamp = time.strftime("[%H:%M:%S]")
        formatted_message = f"{timestamp} {message}\n"
        self.log_area.config(state='normal')
        self.log_area.insert(tk.END, formatted_message)
        self.log_area.see(tk.END)
        self.log_area.config(state='disabled')
        print(f"[{level.upper()}] {message}")

    def _cargar_descripciones_thread(self):
        threading.Thread(
            target=self._cargar_descripciones_task, daemon=True).start()

    def _cargar_descripciones_task(self):
        if not self.db_manager:
            return
        try:
            self.multa_descripciones = self.db_manager.get_fine_descriptions()
            self.log_to_console(
                f"Cargadas {len(self.multa_descripciones)} descripciones de multas.")
        except MySQLError as e:
            self.log_to_console(
                f"Error al cargar descripciones de multas: {e}", "error")

    def populate_dashboard_frame(self):
        frame = self.content_frames["Inicio"]
        frame.config(padx=20, pady=20)
        stat_card_style = {"bg": "#FFFFFF", "bd": 1,
                           "relief": "solid", "padx": 15, "pady": 15}
        title_font = ("Segoe UI", 12, "bold")
        value_font = ("Segoe UI", 28, "bold")
        frame.grid_rowconfigure(0, weight=1)
        frame.grid_columnconfigure((0, 1, 2), weight=1)
        card1 = tk.Frame(frame, **stat_card_style)
        card1.grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        tk.Label(card1, text="Total de Contactos",
                 font=title_font, bg="#FFFFFF").pack()
        tk.Label(card1, textvariable=self.stats_total_contacts,
                 font=value_font, bg="#FFFFFF", fg="#0078D7").pack(pady=10)
        card2 = tk.Frame(frame, **stat_card_style)
        card2.grid(row=0, column=1, padx=10, pady=10, sticky="ew")
        tk.Label(card2, text="Multas Pendientes",
                 font=title_font, bg="#FFFFFF").pack()
        tk.Label(card2, textvariable=self.stats_pending_fines,
                 font=value_font, bg="#FFFFFF", fg="#E74C3C").pack(pady=10)
        card3 = tk.Frame(frame, **stat_card_style)
        card3.grid(row=0, column=2, padx=10, pady=10, sticky="ew")
        tk.Label(card3, text="Recaudado este Mes (Bs.)",
                 font=title_font, bg="#FFFFFF").pack()
        tk.Label(card3, textvariable=self.stats_monthly_revenue,
                 font=value_font, bg="#FFFFFF", fg="#2ECC71").pack(pady=10)

    def toggle_console_visibility(self):
        if self.console_visible:
            self.log_area.pack_forget()
            self.toggle_console_button.config(text="Mostrar Consola")
            self.console_visible = False
        else:
            self.log_area.pack(fill="both", expand=True,
                               before=self.toggle_console_button)
            self.toggle_console_button.config(text="Ocultar Consola")
            self.console_visible = True

    def _cargar_dashboard_stats_thread(self):
        if not self.db_manager:
            return
        threading.Thread(
            target=self._cargar_dashboard_stats_task, daemon=True).start()

    def _cargar_dashboard_stats_task(self):
        try:
            stats = self.db_manager.get_dashboard_stats()

            def update_gui():
                self.stats_total_contacts.set(str(stats['total_contacts']))
                self.stats_pending_fines.set(str(stats['pending_fines_count']))
                revenue_str = f"{stats['revenue_current_month']:,.2f}".replace(
                    ",", "X").replace(".", ",").replace("X", ".")
                self.stats_monthly_revenue.set(revenue_str)
                self.log_to_console("Estadísticas del dashboard actualizadas.")
            self.root.after(0, update_gui)
        except MySQLError as e:
            self.root.after(0, lambda: self.log_to_console(
                f"Error al cargar estadísticas del dashboard: {e}", "error"))

    def _check_fines_for_contact_thread(self, cedula_rif, nombre):
        if not self.db_manager:
            return
        try:
            todas_las_multas = self.db_manager.get_fines_by_contact(cedula_rif)
            if not todas_las_multas:
                self.root.after(0, lambda: messagebox.showinfo(
                    "Sin Multas", f"El contacto '{nombre}' ({cedula_rif}) no tiene multas registradas.", parent=self.root))
            else:
                self.root.after(0, self._show_multas_popup,
                                todas_las_multas, nombre)
        except MySQLError as e:
            self.root.after(
                0, self.log_to_console, f"Error al verificar multas para {cedula_rif}: {e}", "error")

    def _show_multas_popup(self, multas_data, nombre_contacto):
        popup = tk.Toplevel(self.root)
        popup.title(f"Historial de Multas - {nombre_contacto}")
        popup.geometry("600x300")
        popup.transient(self.root)
        popup.grab_set()
        self._center_toplevel(popup)
        tree_frame = ttk.Frame(popup, padding=10)
        tree_frame.pack(fill=tk.BOTH, expand=True)
        columns = ('expediente', 'fecha', 'uc', 'estado')
        multas_popup_tree = ttk.Treeview(
            tree_frame, columns=columns, show='headings')
        multas_popup_tree.pack(fill=tk.BOTH, expand=True)
        multas_popup_tree.heading('expediente', text='N° Expediente')
        multas_popup_tree.heading('fecha', text='Fecha')
        multas_popup_tree.heading('uc', text='U/C')
        multas_popup_tree.heading('estado', text='Estado')
        multas_popup_tree.column('expediente', width=150)
        multas_popup_tree.column('fecha', width=100, anchor='center')
        multas_popup_tree.column('uc', width=80, anchor='center')
        multas_popup_tree.column('estado', width=120, anchor='center')
        multas_popup_tree.tag_configure('pendiente', foreground='red')
        multas_popup_tree.tag_configure('pagada', foreground='green')
        for multa in multas_data:
            estado_texto = "Pendiente" if multa['multa_pendiente'] else "Pagada"
            tag_color = 'pendiente' if multa['multa_pendiente'] else 'pagada'
            fecha = multa.get('fecha_multa').strftime(
                '%Y-%m-%d') if multa.get('fecha_multa') else "N/A"
            uc = multa.get('uc') or 0
            values = (multa['expediente_nro'], fecha, uc, estado_texto)
            multas_popup_tree.insert(
                "", "end", values=values, tags=(tag_color,))
        close_button = ttk.Button(popup, text="Cerrar", command=popup.destroy)
        close_button.pack(pady=10)

    # En app_gui.py, añade estos nuevos métodos a la clase App

    def crear_backup(self):
        """Pide al usuario una ubicación y lanza el hilo para crear el backup."""
        filepath = filedialog.asksaveasfilename(
            title="Guardar Backup de la Base de Datos",
            defaultextension=".sql",
            filetypes=(("Archivos SQL", "*.sql"),
                       ("Todos los archivos", "*.*")),
            initialfile=f"backup_sar-pm_{datetime.now().strftime('%Y-%m-%d')}.sql",
            parent=self.root
        )
        if not filepath:
            self.log_to_console("Creación de backup cancelada.")
            return

        self.log_to_console("Iniciando proceso de backup...")
        threading.Thread(target=self._crear_backup_task,
                         args=(filepath,), daemon=True).start()

    def _crear_backup_task(self, filepath):
        """Ejecuta mysqldump para crear un archivo .sql con los datos de la BD."""
        import subprocess  # Importamos aquí para no cargarlo si no se usa

        try:
            # Obtenemos los datos de la configuración
            host = self.config['mysql']['host']
            user = self.config['mysql']['user']
            db_name = self.config['mysql']['database']
            # Desciframos la contraseña para usarla
            password = self.fernet.decrypt(
                self.config['mysql']['password'].encode()).decode()

            # Construimos el comando. Nota: no hay espacio entre -p y la contraseña.
            command = [
                get_mysql_tool_path('mysqldump.exe'),  # Usa la nueva función
                '-h', host,
                '-u', user,
                f'-p{password}',
                db_name
            ]

            with open(filepath, 'w', encoding='utf-8') as f:
                # Ejecutamos el comando y redirigimos la salida al archivo
                process = subprocess.run(command, stdout=f, stderr=subprocess.PIPE,
                                         text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)

            self.root.after(0, lambda: messagebox.showinfo(
                "Backup Exitoso", f"La base de datos se ha guardado correctamente en:\n{filepath}", parent=self.root))
            self.root.after(
                0, lambda: self.log_to_console("Backup completado con éxito."))

        except FileNotFoundError:
            self.root.after(0, lambda: messagebox.showerror(
                "Error de Comando", "El comando 'mysqldump' no se encontró.\nAsegúrate de que MySQL esté instalado y en el PATH del sistema.", parent=self.root))
        except subprocess.CalledProcessError as e:
            # Si mysqldump falla (ej. contraseña incorrecta), el error estará en stderr
            self.root.after(0, lambda: messagebox.showerror(
                "Error en Backup", f"Ocurrió un error al ejecutar mysqldump:\n{e.stderr}", parent=self.root))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                "Error Inesperado", f"Ocurrió un error inesperado durante el backup:\n{e}", parent=self.root))

    def restaurar_backup(self):
        """Pide confirmación y un archivo .sql para restaurar la BD."""
        # --- ¡ADVERTENCIA CRÍTICA! ---
        if not messagebox.askyesno("Confirmación Crítica",
                                   "ADVERTENCIA:\n\nEsto reemplazará TODOS los datos actuales en la base de datos con los del archivo de backup.\n\n¿Estás absolutamente seguro de que quieres continuar?",
                                   icon='warning', parent=self.root):
            self.log_to_console(
                "Restauración de backup cancelada por el usuario.")
            return

        filepath = filedialog.askopenfilename(
            title="Seleccionar archivo de Backup (.sql) para Restaurar",
            filetypes=(("Archivos SQL", "*.sql"),
                       ("Todos los archivos", "*.*")),
            parent=self.root
        )
        if not filepath:
            self.log_to_console(
                "Selección de archivo para restaurar cancelada.")
            return

        self.log_to_console("Iniciando proceso de restauración...")
        threading.Thread(target=self._restaurar_backup_task,
                         args=(filepath,), daemon=True).start()

    def _restaurar_backup_task(self, filepath):
        """Ejecuta el cliente mysql para importar los datos desde un archivo .sql."""
        import subprocess  # Importamos aquí para no cargarlo si no se usa

        try:
            host = self.config['mysql']['host']
            user = self.config['mysql']['user']
            db_name = self.config['mysql']['database']
            password = self.fernet.decrypt(
                self.config['mysql']['password'].encode()).decode()

            command = [
                get_mysql_tool_path('mysql.exe'),  # Usa la nueva función
                '-h', host,
                '-u', user,
                f'-p{password}',
                db_name
            ]

            with open(filepath, 'r', encoding='utf-8') as f:
                # Ejecutamos el comando y le pasamos el contenido del archivo como entrada
                process = subprocess.run(command, stdin=f, stderr=subprocess.PIPE,
                                         text=True, check=True, creationflags=subprocess.CREATE_NO_WINDOW)

            self.root.after(0, lambda: messagebox.showinfo(
                "Restauración Exitosa", "La base de datos se ha restaurado correctamente.", parent=self.root))
            self.root.after(0, lambda: self.log_to_console(
                "Restauración completada. Recargando datos..."))

            # Recargamos los datos en todas las pestañas para reflejar los cambios
            self.root.after(
                100, self._cargar_dashboard_stats_thread)
            self.root.after(
                200, self.contactos_tab._cargar_contactos_thread)
            self.root.after(
                300, self.multas_tab._cargar_multas_thread)
            self.root.after(
                400, self.mensajes_tab._cargar_mensajes_thread)

        except FileNotFoundError:
            self.root.after(0, lambda: messagebox.showerror(
                "Error de Comando", "El comando 'mysql' no se encontró.\nAsegúrate de que MySQL esté instalado y en el PATH del sistema.", parent=self.root))
        except subprocess.CalledProcessError as e:
            self.root.after(0, lambda: messagebox.showerror(
                "Error en Restauración", f"Ocurrió un error al ejecutar mysql:\n{e.stderr}", parent=self.root))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror(
                "Error Inesperado", f"Ocurrió un error inesperado durante la restauración:\n{e}", parent=self.root))

    def on_closing(self):
        if messagebox.askyesno("Confirmar Salida", "¿Estás seguro de que quieres cerrar el programa?"):
            if self.driver:
                self.driver.quit()
            # Aquí podríamos cerrar el pool de la BD si lo implementamos
            self.root.destroy()
