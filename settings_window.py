import tkinter as tk
from tkinter import ttk, messagebox


class SettingsWindow(tk.Toplevel):
    """
    Una ventana emergente para ver y editar la configuración de la aplicación.
    """

    def __init__(self, controller):
        super().__init__(controller.root)
        self.controller = controller

        self.title("Configuración")
        self.geometry("550x450")
        self.transient(controller.root)
        self.grab_set()

        # --- Variables de Tkinter para los campos ---
        self.settings_vars = {}

        # --- Crear la interfaz ---
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        # Crear una pestaña para cada sección del config
        self._create_tab("mysql", "Base de Datos")
        self._create_tab("smtp", "Email (SMTP)")
        self._create_tab("selenium", "WhatsApp (Selenium)")
        self._create_tab("login", "Usuario App")
        self._create_tab("test_recipient", "Destinatario de Prueba")

        self._load_settings()

        # --- Botones de Guardar y Cancelar ---
        button_frame = ttk.Frame(self)
        button_frame.pack(fill='x', padx=10, pady=10)

        # Usamos el módulo de constantes para los estilos
        import ui_constants as const
        ttk.Button(button_frame, text="Guardar y Cerrar", command=self._save_settings,
                   style="Accent.TButton").pack(side="right", padx=5)
        ttk.Button(button_frame, text="Cancelar",
                   command=self.destroy).pack(side="right")

        # Estilo para el botón de Guardar
        s = ttk.Style()
        s.configure("Accent.TButton", foreground="black",
                    background=const.BUTTON_ACTIVE_BG)

        self.controller.root.wait_window(self)

    def _create_tab(self, section_name, tab_title):
        """Crea una pestaña y la puebla con los campos de una sección del config."""
        tab = ttk.Frame(self.notebook, padding="10")
        self.notebook.add(tab, text=tab_title)

        self.settings_vars[section_name] = {}

        # Obtenemos las opciones de la sección
        if section_name in self.controller.config:
            options = self.controller.config.options(section_name)
            for option in options:
                frame = ttk.Frame(tab)
                frame.pack(fill='x', pady=5)

                ttk.Label(frame, text=f"{option.replace('_', ' ').capitalize()}:", width=25).pack(
                    side="left")

                var = tk.StringVar()
                self.settings_vars[section_name][option] = var

                # Ocultar contraseñas
                is_password = 'password' in option.lower()
                entry = ttk.Entry(frame, textvariable=var,
                                  show="*" if is_password else "")
                entry.pack(side="left", fill='x', expand=True)

    def _load_settings(self):
        """Carga los valores actuales del config en los campos de la ventana."""
        for section, options in self.settings_vars.items():
            for option, var in options.items():
                value = self.controller.config.get(
                    section, option, fallback="")
                # Si es una contraseña, la desciframos para mostrarla
                if 'password' in option.lower() and value:
                    try:
                        value = self.controller.fernet.decrypt(
                            value.encode()).decode()
                    except Exception:
                        # Si falla el descifrado, es probable que ya esté en texto plano
                        pass
                var.set(value)

    def _save_settings(self):
        """Guarda los valores de los campos en el objeto config y en el archivo .ini."""
        try:
            for section, options in self.settings_vars.items():
                for option, var in options.items():
                    new_value = var.get()
                    # Si es una contraseña, la ciframos antes de guardarla
                    if 'password' in option.lower() and new_value:
                        new_value = self.controller.fernet.encrypt(
                            new_value.encode()).decode()

                    self.controller.config.set(section, option, new_value)

            # Escribimos los cambios en el archivo config.ini
            with open('config.ini', 'w', encoding='utf-8') as configfile:
                self.controller.config.write(configfile)

            messagebox.showinfo("Configuración Guardada",
                                "Los cambios se han guardado correctamente.\n\nAlgunos cambios (como los de la base de datos) pueden requerir que reinicies la aplicación.",
                                parent=self)
            self.destroy()  # Cerramos la ventana de configuración
        except Exception as e:
            messagebox.showerror(
                "Error al Guardar", f"No se pudo guardar la configuración:\n{e}", parent=self)
