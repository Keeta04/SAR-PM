# ui_constants.py
"""
Módulo para almacenar constantes de la interfaz de usuario (UI),
como colores y estilos, para facilitar el mantenimiento y el theming.
"""

# --- PALETA DE COLORES ---
SIDEBAR_BG = "#2C3E50"
MAIN_BG = "#ECF0F1"
BUTTON_NORMAL_BG = "#34495E"
BUTTON_ACTIVE_BG = "#0078D7"
BUTTON_FG = "#FFFFFF"
DISABLED_BUTTON_BG = "#A0A0A0"
DISABLED_BUTTON_FG = "#E0E0E0"
CONSOLE_BG = "#34495E"
CONSOLE_FG = "#ECF0F1"
ACTIVE_TAB_BG = "#FFFFFF"


# --- DICCIONARIOS DE ESTILOS ---
BUTTON_STYLE = {
    "font": ("Segoe UI", 9, "bold"),
    "bg": BUTTON_NORMAL_BG,
    "fg": BUTTON_FG,
    "activebackground": BUTTON_ACTIVE_BG,
    "activeforeground": BUTTON_FG,
    "relief": "flat",
    "borderwidth": 0,
    "pady": 5,
    "padx": 10
}

DISABLED_BUTTON_STYLE = {
    "font": ("Segoe UI", 9, "bold"),
    "bg": DISABLED_BUTTON_BG,
    "fg": DISABLED_BUTTON_FG,
    "activebackground": DISABLED_BUTTON_BG,
    "activeforeground": DISABLED_BUTTON_FG,
    "relief": "flat",
    "borderwidth": 0,
    "pady": 5,
    "padx": 10
}
