# services.py
"""
Módulo para gestionar servicios externos como el envío de emails (SMTP)
y la automatización de WhatsApp (Selenium).
"""
import sys
from fpdf import FPDF
from datetime import datetime

import smtplib
import ssl
import urllib.parse
import time
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (TimeoutException, WebDriverException,
                                        NoSuchElementException, ElementClickInterceptedException)

from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager


import sys  # Añade este import


def resource_path(relative_path):
    """ Obtiene la ruta absoluta al recurso, funciona para desarrollo y para PyInstaller """
    try:
        # PyInstaller crea una carpeta temporal y guarda la ruta en _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


class ServicesManager:
    def __init__(self, config, fernet):
        self.config = config
        self.fernet = fernet

    def send_email(self, recipient_email, subject, body):
        """
        Envía un correo electrónico usando la configuración SMTP.
        """
        # Descifra la contraseña justo antes de usarla
        smtp_password = self.fernet.decrypt(
            self.config.get('smtp', 'password').encode()).decode()

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.config['smtp']['sender_email']
        msg["To"] = recipient_email
        msg.attach(MIMEText(body, "plain"))

        with smtplib.SMTP_SSL(self.config['smtp']['server'], int(self.config['smtp']['port'])) as server:
            server.login(self.config['smtp']['sender_email'], smtp_password)
            server.sendmail(msg["From"], msg["To"], msg.as_string())

    def init_selenium_driver(self):
        """
        Inicializa y devuelve un driver de Selenium según la configuración.
        """
        browser = self.config['selenium']['browser'].lower()
        if browser == 'none':
            return None

        try:
            if browser == 'firefox':
                options = FirefoxOptions()
                if self.config['selenium'].get('firefox_profile_path'):
                    options.add_argument(
                        f"-profile {self.config['selenium']['firefox_profile_path']}")
                if self.config['selenium'].get('browser_binary_location'):
                    options.binary_location = self.config['selenium']['browser_binary_location']
                service = FirefoxService(GeckoDriverManager().install())
                return webdriver.Firefox(service=service, options=options)
            elif browser in ('chrome', 'brave'):
                options = ChromeOptions()
                if self.config['selenium'].get('chrome_user_data_dir'):
                    options.add_argument(
                        f"--user-data-dir={self.config['selenium']['chrome_user_data_dir']}")
                    options.add_argument(
                        f"--profile-directory={self.config['selenium'].get('chrome_profile_directory', 'Default')}")
                if self.config['selenium'].get('browser_binary_location'):
                    options.binary_location = self.config['selenium']['browser_binary_location']
                service = ChromeService(ChromeDriverManager().install())
                return webdriver.Chrome(service=service, options=options)
            else:
                raise WebDriverException(
                    f"Navegador '{browser}' no soportado.")
        except Exception as e:
            raise WebDriverException(f"Error al iniciar {browser}: {e}")

    def send_whatsapp_message(self, driver, phone_number, message):
        """
        Usa un driver de Selenium existente para enviar un mensaje de WhatsApp.
        """
        phone_number_str = str(phone_number)
        phone_number_digits = ''.join(filter(str.isdigit, phone_number_str))

        encoded_message = urllib.parse.quote(message)
        whatsapp_url = f"https://web.whatsapp.com/send?phone={phone_number_digits}&text={encoded_message}"
        driver.get(whatsapp_url)

        wait_time = float(self.config['selenium']['element_wait_time'])
        send_button_xpath = '//button[@aria-label="Send"] | //button[@aria-label="Enviar"] | //span[@data-icon="send"]'

        send_button = WebDriverWait(driver, wait_time).until(
            EC.element_to_be_clickable((By.XPATH, send_button_xpath))
        )
        # Pequeña pausa para asegurar que el botón es realmente interactuable
        time.sleep(1)

        try:
            send_button.click()
        except ElementClickInterceptedException:
            print("Clic normal interceptado. Usando clic de respaldo (JavaScript)...")
            driver.execute_script("arguments[0].click();", send_button)

        # Al inicio de services.py, junto a los otros imports

# Dentro de la clase ServicesManager
    def generate_pdf_report(self, multas_data, report_title, filepath):
        """Genera un reporte en PDF a partir de una lista de datos de multas."""
        pdf = FPDF(orientation='L', unit='mm', format='A4')
        pdf.add_page()

        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            header_path = resource_path(
                os.path.join('assets', 'header_inea.png'))
            ancho_pagina = pdf.w - pdf.l_margin - pdf.r_margin
            pdf.image(header_path, x=pdf.l_margin,
                      y=pdf.t_margin, w=ancho_pagina)
            pdf.ln(25)
        except FileNotFoundError:
            # Si no encuentra la imagen, simplemente escribe un texto en el PDF
            pdf.set_font("Arial", 'B', 12)
            pdf.cell(
                0, 10, "Encabezado no disponible (header_inea.png no encontrado)", 0, 1, 'C')
            pdf.ln(10)

        pdf.set_font("Arial", 'B', 16)

        pdf.cell(0, 10, report_title, 0, 1, 'C')
        pdf.ln(10)

        ancho_cols = {'exp': 60, 'ced': 35, 'f_m': 30,
                      'f_p': 30, 'uc': 20, 'bs': 40, 'est': 30}
        total_ancho_tabla = sum(ancho_cols.values())
        posicion_x_inicio = (pdf.w - total_ancho_tabla) / 2

        pdf.set_font("Arial", 'B', 10)
        pdf.set_x(posicion_x_inicio)
        headers = ['Nro. Expediente', 'Cedula/RIF', 'Fecha Multa',
                   'Fecha Pago', 'U/C', 'Monto (Bs)', 'Estado']
        widths = [ancho_cols['exp'], ancho_cols['ced'], ancho_cols['f_m'],
                  ancho_cols['f_p'], ancho_cols['uc'], ancho_cols['bs'], ancho_cols['est']]
        for i, header in enumerate(headers):
            pdf.cell(widths[i], 10, header, 1, 0, 'C')
        pdf.ln()

        pdf.set_font("Arial", '', 8)
        total_bs_pagado = 0
        for multa in multas_data:
            pdf.set_x(posicion_x_inicio)
            estado = "Pendiente" if multa['multa_pendiente'] else "Pagada"
            monto_bs_num = multa.get('bs') or 0.00
            if not multa['multa_pendiente']:
                total_bs_pagado += monto_bs_num

            pdf.cell(ancho_cols['exp'], 10, str(
                multa['expediente_nro'])[:35], 1, 0, 'L')
            pdf.cell(ancho_cols['ced'], 10, str(
                multa['cedula_rif']), 1, 0, 'L')
            pdf.cell(ancho_cols['f_m'], 10, multa['fecha_multa'].strftime(
                '%Y-%m-%d') if multa.get('fecha_multa') else "-", 1, 0, 'C')
            pdf.cell(ancho_cols['f_p'], 10, multa['fecha_pago'].strftime(
                '%Y-%m-%d') if multa.get('fecha_pago') else "---", 1, 0, 'C')
            pdf.cell(ancho_cols['uc'], 10, str(multa['uc']), 1, 0, 'C')
            pdf.cell(ancho_cols['bs'], 10, f"{monto_bs_num:,.2f}", 1, 0, 'R')

            if multa['multa_pendiente']:
                pdf.set_text_color(255, 0, 0)
            else:
                pdf.set_text_color(0, 128, 0)

            pdf.cell(ancho_cols['est'], 10, estado, 1, 0, 'C')
            pdf.set_text_color(0, 0, 0)
            pdf.ln()

        pdf.ln(10)
        pdf.set_x(posicion_x_inicio)
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(
            0, 10, f"Multas totales del mes: {len(multas_data)}", 0, 1, 'L')
        pdf.set_x(posicion_x_inicio)
        pdf.cell(
            0, 10, f"Monto total pagado en el mes: {total_bs_pagado:,.2f} Bs.", 0, 1, 'L')

        pdf.output(filepath)
