# config_handler.py
"""
Módulo para gestionar la configuración y el cifrado de la aplicación.

Contiene todas las funciones relacionadas con:
- La lectura y validación del archivo 'config.ini'.
- La generación y carga de la clave de cifrado.
- El cifrado y descifrado de valores sensibles (contraseñas).
- La creación de un archivo de configuración inicial para el primer uso.
"""

import os
import configparser
import tkinter as tk
from tkinter import messagebox
from cryptography.fernet import Fernet

KEY_FILE = "secret.key"


def generate_key():
    """
    Genera una nueva clave de cifrado y la guarda en el archivo 'secret.key'.
    """
    key = Fernet.generate_key()
    with open(KEY_FILE, "wb") as key_file:
        key_file.write(key)
    return key


def load_key():
    """
    Carga la clave de cifrado desde 'secret.key'. 
    Si el archivo no existe, lo genera.
    """
    if not os.path.exists(KEY_FILE):
        return generate_key()
    with open(KEY_FILE, "rb") as key_file:
        return key_file.read()


def encrypt_value(fernet, value):
    """
    Cifra un valor usando la instancia de Fernet proporcionada.
    """
    return fernet.encrypt(value.encode()).decode()


def decrypt_value(fernet, encrypted_value):
    """
    Descifra un valor usando la instancia de Fernet proporcionada.
    """
    return fernet.decrypt(encrypted_value.encode()).decode()


def leer_configuracion():
    """
    Lee la configuración desde config.ini y la devuelve como un objeto ConfigParser.
    Muestra errores si el archivo o la sección [login] no se encuentran.
    """
    config = configparser.ConfigParser()
    if not os.path.exists('config.ini'):
        # No mostramos error aquí, main.py se encargará del flujo de primer arranque.
        return None

    try:
        config.read('config.ini', encoding='utf-8')
        if 'login' not in config:
            temp_root = tk.Tk()
            temp_root.withdraw()
            messagebox.showerror(
                "Error de Configuración",
                "La sección '[login]' no se encuentra en 'config.ini'.",
                parent=temp_root
            )
            temp_root.destroy()
            return None
        return config
    except Exception as e:
        temp_root = tk.Tk()
        temp_root.withdraw()
        messagebox.showerror(
            "Error de Configuración",
            f"Error al leer 'config.ini': {e}.",
            parent=temp_root
        )
        temp_root.destroy()
        return None


def crear_config_inicial(fernet):
    """
    Crea un archivo config.ini con valores de ejemplo y contraseñas cifradas.
    Esta función se llama solo durante el primer arranque de la aplicación.

    Args:
        fernet: Una instancia de Fernet para cifrar los valores iniciales.
    """
    sample_config = configparser.ConfigParser()
    sample_config['mysql'] = {
        'host': 'localhost',
        'user': 'root',
        'password': encrypt_value(fernet, 'tu_clave_mysql'),
        'database': 'automatizacion_db'
    }
    sample_config['smtp'] = {
        'server': 'smtp.gmail.com',
        'port': '465',
        'sender_email': 'tu_email@gmail.com',
        'password': encrypt_value(fernet, 'tu_clave_de_app')
    }
    sample_config['selenium'] = {
        'browser': 'firefox',
        'browser_binary_location': '',
        'firefox_profile_path': '',
        'implicit_wait_time': '10',
        'page_load_timeout': '30',
        'element_wait_time': '20',
        'inter_message_delay': '3'
    }
    sample_config['login'] = {
        'user': 'admin',
        'password': encrypt_value(fernet, 'admin')
    }
    sample_config['test_recipient'] = {
        'email': 'tu_email_de_prueba@ejemplo.com',
        'telefono': '+1234567890'
    }

    with open('config.ini', 'w', encoding='utf-8') as configfile:
        sample_config.write(configfile)
