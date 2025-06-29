# login_window.py
"""
Módulo para la ventana de Inicio de Sesión (Login).

Contiene la clase LoginApplication que gestiona la interfaz gráfica y la lógica
para la autenticación del usuario.
"""

import tkinter as tk
from tkinter import ttk, messagebox

# Importamos la función de descifrado desde nuestro manejador de configuración.
from config_handler import decrypt_value


class LoginApplication:
    """
    Gestiona la ventana de inicio de sesión de la aplicación.
    """

    def __init__(self, root, config, fernet, launch_main_app_callback):
        """
        Inicializa la ventana de inicio de sesión.

        Args:
            root (tk.Tk): La ventana raíz de Tkinter para esta interfaz.
            config (ConfigParser): El objeto de configuración cargado.
            fernet (Fernet): La instancia de Fernet para descifrar.
            launch_main_app_callback (function): La función a llamar si el login es exitoso.
        """
        self.root = root
        self.config = config
        self.fernet = fernet
        # Guardamos la función 'callback' para llamarla después.
        self.launch_main_app_callback = launch_main_app_callback

        self.root.title("Inicio de Sesión")
        self.root.geometry("300x180+500+300")
        self.root.resizable(False, False)

        # --- Estilos y Widgets (sin cambios respecto a tu código original) ---
        BG_COLOR = "#0078D7"
        ACTIVE_BG_COLOR = "#005A9E"
        TEXT_COLOR = "#FFFFFF"

        frame = ttk.Frame(self.root, padding="20")
        frame.pack(expand=True, fill="both")

        ttk.Label(frame, text="Usuario:").pack()
        self.user_entry = ttk.Entry(frame, width=30)
        self.user_entry.pack(pady=5)
        self.user_entry.focus_set()

        ttk.Label(frame, text="Clave:").pack()
        self.pass_entry = ttk.Entry(frame, show="*", width=30)
        self.pass_entry.pack(pady=5)

        login_button = tk.Button(
            frame,
            text="Iniciar sesión",
            font=("Segoe UI", 10, "bold"),
            bg=BG_COLOR,
            fg=TEXT_COLOR,
            activebackground=ACTIVE_BG_COLOR,
            activeforeground=TEXT_COLOR,
            relief="flat",
            borderwidth=0,
            width=20,
            pady=5,
            command=self.check_login
        )
        login_button.pack(pady=(10, 0))

        # Asocia la tecla "Enter" a la función de login.
        self.root.bind("<Return>", lambda event: self.check_login())

    def check_login(self):
        """
        Verifica las credenciales ingresadas por el usuario.
        """
        user = self.user_entry.get()
        password = self.pass_entry.get()
        try:
            correct_user = self.config['login']['user']
            encrypted_pass = self.config['login']['password']

            # Usa la función importada para descifrar la contraseña
            correct_pass = decrypt_value(self.fernet, encrypted_pass)

            if user == correct_user and password == correct_pass:
                # Si las credenciales son correctas...
                self.root.destroy()  # 1. Cierra la ventana de login.
                # 2. Llama a la función que inicia la app principal.
                self.launch_main_app_callback(self.config)
            else:
                messagebox.showerror(
                    "Error de Acceso",
                    "Usuario o clave incorrectos.",
                    parent=self.root
                )
                self.pass_entry.delete(0, tk.END)
        except Exception as e:
            messagebox.showerror(
                "Error de Cifrado",
                f"No se pudo verificar la contraseña.\nError: {e}",
                parent=self.root
            )
