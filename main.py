# main.py
"""
Punto de entrada principal para la aplicación Gestor de Contactos.

Este script se encarga de:
1. Leer la configuración inicial.
2. Gestionar el primer arranque de la aplicación, creando un config.ini de ejemplo si no existe.
3. Cifrar automáticamente las contraseñas en texto plano dentro de config.ini.
4. Lanzar la ventana de inicio de sesión (Login) o la aplicación principal directamente si el modo DEV está activado.
"""

import os
import tkinter as tk
from tkinter import messagebox
import configparser
from cryptography.fernet import Fernet

# --- Nuestros Módulos (que crearemos a continuación) ---
# Se importan las funciones y clases que hemos separado en otros archivos.
from config_handler import (leer_configuracion, generate_key, load_key,
                            encrypt_value, decrypt_value, crear_config_inicial)
from login_window import LoginApplication
from app_gui import App  # Importamos la clase principal de la aplicación

# --- Constantes Globales ---
KEY_FILE = "secret.key"
# Cambiar a False para el uso en producción normal.
# Al estar en True, se salta la pantalla de login.
DEV_MODE = False


def launch_main_app(config):
    """
    Inicializa y ejecuta la ventana principal de la aplicación.
    """
    main_root = tk.Tk()
    # Se crea una instancia de la clase App, que contiene toda la lógica de la GUI principal.
    app = App(main_root, config)
    # Se asigna el método on_closing al evento de cierre de la ventana.
    main_root.protocol("WM_DELETE_WINDOW", app.on_closing)
    main_root.mainloop()


def main():
    """
    Función principal que orquesta el arranque de la aplicación.
    """
    # 1. Intenta leer el archivo de configuración.
    print("--- PASO 1: Ejecutando main() ---")
    config = leer_configuracion()
    print(
        f"--- PASO 2: leer_configuracion() devolvió: {'Config OK' if config else 'None'} ---")

    # 2. Si config.ini no existe, entra en el modo de configuración inicial.
    if not os.path.exists('config.ini'):
        temp_root = tk.Tk()
        temp_root.withdraw()  # Oculta la ventana raíz temporal

        try:
            # Genera la llave y el archivo de configuración por defecto.
            fernet = Fernet(generate_key())
            messagebox.showinfo(
                "Configuración Inicial",
                f"Se ha generado una nueva llave de seguridad ('{KEY_FILE}'). No la borres ni la compartas.",
                parent=temp_root
            )
            crear_config_inicial(fernet)
            messagebox.showinfo(
                "Configuración Creada",
                "Se creó 'config.ini' con valores de ejemplo cifrados. "
                "Por favor, edítalo con tus datos reales (en texto plano) y la aplicación los cifrará al reiniciar.",
                parent=temp_root
            )
        finally:
            temp_root.destroy()

        # Termina la ejecución para que el usuario pueda editar el archivo.
        return

    # 3. Si no se pudo leer la configuración por otra razón, termina.
    if not config:
        print("--- ERROR: No se pudo leer la configuración. Saliendo. ---")
        return

    # 4. Modo de Desarrollo: Saltar el login e ir directo a la app.
    if DEV_MODE:
        print("--- INFO: Entrando en MODO DESARROLLO (Login omitido) ---")
        launch_main_app(config)
        return

    # 5. Modo de Producción: Procesar contraseñas y mostrar login.
    print("--- PASO 3: Entrando en flujo de producción (cifrado y login) ---")
    key = load_key()
    fernet = Fernet(key)
    needs_saving = False

    # Revisa si las contraseñas en config.ini necesitan ser cifradas.
    print("--- PASO 4: Iniciando bucle para revisar contraseñas... ---")
    for section, option in [('mysql', 'password'), ('smtp', 'password'), ('login', 'password')]:
        if config.has_option(section, option):
            try:
                # Intenta desencriptar. Si falla, es que está en texto plano.
                decrypt_value(fernet, config.get(section, option))
            except Exception:
                plain_password = config.get(section, option).strip()
                if plain_password:
                    encrypted_password = encrypt_value(fernet, plain_password)
                    config.set(section, option, encrypted_password)
                    needs_saving = True

    # Si se cifró alguna contraseña, se guarda el archivo config.ini actualizado.
    print(
        f"--- PASO 5: Bucle terminado. ¿Necesita guardarse? {needs_saving} ---")
    if needs_saving:
        with open('config.ini', 'w', encoding='utf-8') as configfile:
            config.write(configfile)
            print(
                "--- PASO 6: ¡ÉXITO! config.ini actualizado con contraseñas cifradas. ---")
        messagebox.showinfo(
            "Seguridad", "Se han cifrado las contraseñas en tu 'config.ini'."
        )

    # Lanza la ventana de inicio de sesión.
    print("--- PASO 7: Lanzando la ventana de Login... ---")
    login_root = tk.Tk()
    login_app = LoginApplication(login_root, config, fernet, launch_main_app)
    login_root.mainloop()


if __name__ == "__main__":
    print("--- INICIO DEL PROGRAMA ---")
    main()
    print("--- FIN DEL PROGRAMA ---")
