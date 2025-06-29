import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import time
from mysql.connector import IntegrityError, Error as MySQLError
from selenium.common.exceptions import WebDriverException
import ui_constants as const


class MensajesTab(ttk.Frame):
    """
    Clase que encapsula toda la funcionalidad de la pestaña de Mensajes y Envío.
    """

    def __init__(self, parent, controller, **kwargs):
        super().__init__(parent, **kwargs)
        self.controller = controller

        # Variables de estado
        self.editing_message_id = None
        self.messages_data = {}
        self.preset_message_options = []

        self.create_widgets()

        if self.controller.db_manager:
            self.controller.root.after(200, self._cargar_mensajes_thread)

    def create_widgets(self):
        frame = self
        top_message_frame = ttk.Frame(frame)
        top_message_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        preset_messages_frame = ttk.LabelFrame(
            top_message_frame, text="Gestión de Mensajes Predefinidos")
        preset_messages_frame.pack(
            side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        ttk.Label(preset_messages_frame, text="Nombre del Mensaje:").pack(
            padx=5, pady=2, anchor='w')
        self.message_name_entry = ttk.Entry(preset_messages_frame)
        self.message_name_entry.pack(padx=5, pady=2, fill='x')
        ttk.Label(preset_messages_frame, text="Asunto del Email:").pack(
            padx=5, pady=2, anchor='w')
        self.subject_entry = ttk.Entry(preset_messages_frame)
        self.subject_entry.pack(padx=5, pady=2, fill='x')
        ttk.Label(preset_messages_frame, text="Cuerpo del Email:").pack(
            padx=5, pady=2, anchor='w')
        self.email_body_text = scrolledtext.ScrolledText(
            preset_messages_frame, wrap=tk.WORD, height=6)
        self.email_body_text.pack(padx=5, pady=2, fill='both', expand=True)
        ttk.Label(preset_messages_frame, text="Mensaje de WhatsApp:").pack(
            padx=5, pady=2, anchor='w')
        self.whatsapp_msg_text = scrolledtext.ScrolledText(
            preset_messages_frame, wrap=tk.WORD, height=4)
        self.whatsapp_msg_text.pack(padx=5, pady=2, fill='both', expand=True)

        placeholder_info = (
            "Placeholders disponibles:\n"
            "{nombre_contacto}, {cedula_rif}, {cantidad_multas_pendientes}"
        )
        ttk.Label(preset_messages_frame, text=placeholder_info, justify=tk.LEFT,
                  relief="solid", padding=5).pack(fill='x', padx=5, pady=10)

        message_buttons_frame = ttk.Frame(preset_messages_frame)
        message_buttons_frame.pack(pady=10)
        self.btn_save_message = tk.Button(
            message_buttons_frame, text="Guardar", **const.BUTTON_STYLE, command=self.save_message)
        self.btn_save_message.pack(side=tk.LEFT, padx=5)
        self.btn_update_message = tk.Button(
            message_buttons_frame, text="Actualizar", **const.BUTTON_STYLE, command=self.update_message)
        self.btn_update_message.pack(side=tk.LEFT, padx=5)
        self.btn_delete_message = tk.Button(
            message_buttons_frame, text="Eliminar", **const.BUTTON_STYLE, command=self.delete_message)
        self.btn_delete_message.pack(side=tk.LEFT, padx=5)
        self.btn_clear_message_fields = tk.Button(
            message_buttons_frame, text="Limpiar", **const.BUTTON_STYLE, command=self.clear_message_fields)
        self.btn_clear_message_fields.pack(side=tk.LEFT, padx=5)

        load_message_frame = ttk.LabelFrame(
            top_message_frame, text="Cargar Mensaje Predefinido")
        load_message_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        self.preset_message_combobox = ttk.Combobox(
            load_message_frame, state="readonly", width=30)
        self.preset_message_combobox.set("Selecciona un mensaje...")
        self.preset_message_combobox.pack(
            side=tk.TOP, padx=5, pady=5, fill='x')
        self.preset_message_combobox.bind(
            "<<ComboboxSelected>>", self.load_selected_message)

        action_frame = ttk.LabelFrame(frame, text="Acciones de Envío")
        action_frame.pack(pady=10, padx=10, fill=tk.X)

        send_options_frame = ttk.Frame(action_frame)
        send_options_frame.pack(pady=5)
        self.send_email_var = tk.BooleanVar(value=True)
        self.send_whatsapp_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(send_options_frame, text="Enviar Email",
                        variable=self.send_email_var).pack(side=tk.LEFT, padx=10)
        ttk.Checkbutton(send_options_frame, text="Enviar WhatsApp",
                        variable=self.send_whatsapp_var).pack(side=tk.LEFT, padx=10)

        progress_frame = ttk.Frame(action_frame)
        progress_frame.pack(pady=5, fill=tk.X, padx=10)
        self.progress_label = ttk.Label(progress_frame, text="Progreso: 0/0")
        self.progress_label.pack(side=tk.TOP, pady=2)
        self.progress_bar = ttk.Progressbar(
            progress_frame, orient="horizontal", mode="determinate")
        self.progress_bar.pack(side=tk.TOP, fill=tk.X, ipady=2)

        send_buttons_frame = ttk.Frame(action_frame)
        send_buttons_frame.pack(pady=10)
        self.btn_send = tk.Button(send_buttons_frame, text="Enviar a Seleccionados",
                                  **const.BUTTON_STYLE, command=self.iniciar_envio_thread)
        self.btn_send.pack(side=tk.LEFT, padx=10)
        self.btn_test_send = tk.Button(
            send_buttons_frame, text="Probar Envío", **const.BUTTON_STYLE, command=self.test_send)
        self.btn_test_send.pack(side=tk.LEFT, padx=10)

        self.clear_message_fields()

    def _cargar_mensajes_thread(self):
        if not self.controller.db_manager:
            return
        threading.Thread(target=self._cargar_mensajes_task,
                         daemon=True).start()

    def _cargar_mensajes_task(self):
        try:
            messages = self.controller.db_manager.get_preset_messages()

            def update_gui():
                self.preset_message_options = [
                    msg['nombre'] for msg in messages]
                self.messages_data = {msg['nombre']                                      : msg['id'] for msg in messages}
                self.preset_message_combobox.config(
                    values=self.preset_message_options)
                self.controller.log_to_console(
                    f"Mensajes predefinidos cargados: {len(messages)}.")
            self.controller.root.after(0, update_gui)
        except MySQLError as e:
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Error al cargar mensajes: {e}", "error"))

    def load_selected_message(self, event=None):
        if not self.controller.db_manager:
            return
        name = self.preset_message_combobox.get()
        msg_id = self.messages_data.get(name)
        if not msg_id:
            return
        try:
            msg = self.controller.db_manager.get_message_details(msg_id)
            if msg:
                self.message_name_entry.delete(0, tk.END)
                self.message_name_entry.insert(0, msg['nombre'])
                self.subject_entry.delete(0, tk.END)
                self.subject_entry.insert(0, msg.get('asunto_email', ''))
                self.email_body_text.delete("1.0", tk.END)
                self.email_body_text.insert("1.0", msg.get('cuerpo_email', ''))
                self.whatsapp_msg_text.delete("1.0", tk.END)
                self.whatsapp_msg_text.insert(
                    "1.0", msg.get('mensaje_whatsapp', ''))
                self.editing_message_id = msg['id']
                self.btn_update_message.config(
                    state=tk.NORMAL, **const.BUTTON_STYLE)
                self.btn_delete_message.config(
                    state=tk.NORMAL, **const.BUTTON_STYLE)
                self.btn_save_message.config(
                    state=tk.DISABLED, **const.DISABLED_BUTTON_STYLE)
                self.controller.log_to_console(
                    f"Mensaje '{msg['nombre']}' cargado.")
        except MySQLError as e:
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Error al cargar mensaje '{name}': {e}", "error"))

    def save_message(self):
        if not self.controller.db_manager:
            return
        name = self.message_name_entry.get().strip()
        if not name:
            messagebox.showwarning(
                "Advertencia", "El nombre del mensaje es obligatorio.", parent=self.controller.root)
            return
        subject = self.subject_entry.get()
        email_body = self.email_body_text.get("1.0", tk.END)
        whatsapp_msg = self.whatsapp_msg_text.get("1.0", tk.END)
        try:
            self.controller.db_manager.save_message(
                name, subject, email_body, whatsapp_msg)
            self.controller.log_to_console(f"Mensaje '{name}' guardado.")
            self.clear_message_fields()
            self._cargar_mensajes_thread()
        except IntegrityError:
            messagebox.showerror(
                "Error", f"Ya existe un mensaje con el nombre '{name}'.", parent=self.controller.root)
        except MySQLError as e:
            self.controller.log_to_console(
                f"Error al guardar mensaje: {e}", "error")

    def update_message(self):
        if not self.editing_message_id:
            return
        if not self.controller.db_manager:
            return
        name = self.message_name_entry.get().strip()
        if not name:
            messagebox.showwarning(
                "Advertencia", "El nombre del mensaje no puede estar vacío.", parent=self.controller.root)
            return
        subject = self.subject_entry.get()
        email_body = self.email_body_text.get("1.0", tk.END)
        whatsapp_msg = self.whatsapp_msg_text.get("1.0", tk.END)
        try:
            self.controller.db_manager.update_message(
                self.editing_message_id, name, subject, email_body, whatsapp_msg)
            self.controller.log_to_console(
                f"Mensaje '{name}' actualizado correctamente.")
            self.clear_message_fields()
            self._cargar_mensajes_thread()
        except IntegrityError:
            messagebox.showerror(
                "Error de Duplicado", f"Ya existe otro mensaje con el nombre '{name}'.", parent=self.controller.root)
        except MySQLError as e:
            self.controller.log_to_console(
                f"Error al actualizar mensaje: {e}", "error")

    def delete_message(self):
        if not self.editing_message_id:
            return
        if not self.controller.db_manager:
            return
        message_name = self.message_name_entry.get()
        if messagebox.askyesno("Confirmar Eliminación", f"¿Seguro que quieres eliminar el mensaje '{message_name}'?", parent=self.controller.root):
            try:
                self.controller.db_manager.delete_message(
                    self.editing_message_id)
                self.controller.log_to_console(
                    f"Mensaje '{message_name}' eliminado.")
                self.clear_message_fields()
                self._cargar_mensajes_thread()
            except MySQLError as e:
                self.controller.log_to_console(
                    f"Error al eliminar mensaje: {e}", "error")

    def clear_message_fields(self):
        self.message_name_entry.delete(0, tk.END)
        self.subject_entry.delete(0, tk.END)
        self.email_body_text.delete("1.0", tk.END)
        self.whatsapp_msg_text.delete("1.0", tk.END)
        self.preset_message_combobox.set("Selecciona un mensaje...")
        self.editing_message_id = None
        self.btn_save_message.config(
            state=tk.NORMAL, **const.BUTTON_STYLE)
        self.btn_update_message.config(
            state=tk.DISABLED, **const.DISABLED_BUTTON_STYLE)
        self.btn_delete_message.config(
            state=tk.DISABLED, **const.DISABLED_BUTTON_STYLE)
        self.controller.log_to_console("Campos de mensaje limpiados.")

    def iniciar_envio_thread(self):
        contactos_a_enviar = self.controller.contactos_tab.get_selected_contacts()
        if not contactos_a_enviar:
            messagebox.showwarning(
                "Advertencia", "Por favor, selecciona al menos un contacto.", parent=self.controller.root)
            return

        enviar_email = self.send_email_var.get()
        enviar_whatsapp = self.send_whatsapp_var.get()
        if not enviar_email and not enviar_whatsapp:
            messagebox.showwarning(
                "Advertencia", "Debes seleccionar al menos un canal de envío.", parent=self.controller.root)
            return

        subject = self.subject_entry.get().strip()
        email_body = self.email_body_text.get("1.0", tk.END).strip()
        whatsapp_msg = self.whatsapp_msg_text.get("1.0", tk.END).strip()
        if enviar_email and not (subject or email_body):
            messagebox.showwarning(
                "Advertencia", "Para enviar emails, se necesita asunto o cuerpo.", parent=self.controller.root)
            return
        if enviar_whatsapp and not whatsapp_msg:
            messagebox.showwarning(
                "Advertencia", "Para enviar por WhatsApp, el mensaje no puede estar vacío.", parent=self.controller.root)
            return

        self.progress_bar['value'] = 0
        self.progress_label.config(
            text=f"Progreso: 0/{len(contactos_a_enviar)}")
        self.controller.log_to_console(
            f"Iniciando envío a {len(contactos_a_enviar)} contactos...")
        threading.Thread(target=self._enviar_mensajes_task, args=(contactos_a_enviar, subject,
                         email_body, whatsapp_msg, enviar_email, enviar_whatsapp), daemon=True).start()

    # En mensajes_tab.py, reemplaza el método _enviar_mensajes_task por este:

    def _enviar_mensajes_task(self, contactos_a_enviar, subject_template, email_body_template, whatsapp_msg_template, enviar_email, enviar_whatsapp):
        self.controller.driver = None
        if enviar_whatsapp:
            try:
                self.controller.driver = self.controller.services_manager.init_selenium_driver()
                if self.controller.driver:
                    self.controller.root.after(0, lambda: self.controller.log_to_console(
                        "Driver de Selenium inicializado. Cargando WhatsApp Web..."))
                    self.controller.driver.get("https://web.whatsapp.com/")
                    timeout = float(
                        self.controller.config['selenium']['page_load_timeout'])
                    from selenium.webdriver.support.ui import WebDriverWait
                    from selenium.webdriver.support import expected_conditions as EC
                    from selenium.webdriver.common.by import By
                    WebDriverWait(self.controller.driver, timeout).until(
                        EC.presence_of_element_located((By.XPATH, '//*[@id="side"]')))
                    self.controller.root.after(0, lambda: self.controller.log_to_console(
                        "WhatsApp Web cargado. Asegúrate de tener la sesión iniciada."))
            except Exception as e:
                self.controller.root.after(0, lambda: messagebox.showerror(
                    "Error de Selenium", f"No se pudo iniciar el navegador o cargar WhatsApp Web:\n{e}", parent=self.controller.root))
                self.controller.driver = None

        total_contacts = len(contactos_a_enviar)
        for i, contacto in enumerate(contactos_a_enviar):
            # --- INICIO DE LA LÓGICA DE PERSONALIZACIÓN ---

            # 1. Obtener datos de multas pendientes para este contacto específico
            cantidad_multas = self.controller.db_manager.get_pending_fines_count_for_contact(
                contacto['id'])
            # 4. Crear el diccionario de placeholders y sus valores
            placeholders = {
                "{nombre_contacto}": contacto.get('nombre', ''),
                "{cedula_rif}": contacto.get('id', ''),
                "{cantidad_multas_pendientes}": str(cantidad_multas),
            }

            # 5. Reemplazar los placeholders en las plantillas de mensajes
            personalized_subject = subject_template
            personalized_email_body = email_body_template
            personalized_whatsapp_msg = whatsapp_msg_template

            for key, value in placeholders.items():
                personalized_subject = personalized_subject.replace(
                    key, str(value))
                personalized_email_body = personalized_email_body.replace(
                    key, str(value))
                personalized_whatsapp_msg = personalized_whatsapp_msg.replace(
                    key, str(value))

            # --- FIN DE LA LÓGICA DE PERSONALIZACIÓN ---

            # Actualizamos la GUI
            progress_value = ((i + 1) / total_contacts) * 100
            self.controller.root.after(
                0, lambda p=progress_value: self.progress_bar.config(value=p))
            self.controller.root.after(
                0, lambda c=i+1, t=total_contacts: self.progress_label.config(text=f"Progreso: {c}/{t}"))
            self.controller.root.after(
                0, self.controller.log_to_console, f"Procesando a {contacto['nombre']}...")

            # Enviamos los mensajes ya personalizados
            if enviar_email and contacto.get('email') and contacto.get('email') != "N/A":
                try:
                    self.controller.services_manager.send_email(
                        contacto['email'], personalized_subject, personalized_email_body)
                    self.controller.root.after(
                        0, lambda n=contacto['nombre']: self.controller.log_to_console(f"Email enviado a {n}."))
                except Exception as e:
                    self.controller.root.after(0, lambda n=contacto['nombre'], err=e: self.controller.log_to_console(
                        f"Error al enviar email a {n}: {err}", "error"))

            if enviar_whatsapp and contacto.get('telefono') and contacto.get('telefono') != "N/A" and self.controller.driver:
                try:
                    self.controller.services_manager.send_whatsapp_message(
                        self.controller.driver, contacto['telefono'], personalized_whatsapp_msg)
                    self.controller.root.after(0, lambda n=contacto['nombre']: self.controller.log_to_console(
                        f"Mensaje WhatsApp enviado a {n}."))
                except Exception as e:
                    self.controller.root.after(0, lambda n=contacto['nombre'], err=e: self.controller.log_to_console(
                        f"Error al enviar WhatsApp a {n}: {err}", "error"))

            time.sleep(
                float(self.controller.config['selenium']['inter_message_delay']))

        if self.controller.driver:
            self.controller.driver.quit()
            self.controller.driver = None

        self.controller.root.after(
            0, lambda: self.controller.log_to_console("Proceso de envío finalizado."))
        self.controller.root.after(
            0, lambda: self.progress_bar.config(value=0))
        self.controller.root.after(
            0, lambda: self.progress_label.config(text="Progreso: 0/0"))

    def test_send(self):
        try:
            test_email = self.controller.config.get(
                'test_recipient', 'email', fallback='').strip()
            test_phone = self.controller.config.get(
                'test_recipient', 'telefono', fallback='').strip()

            if not test_email and not test_phone:
                messagebox.showerror(
                    "Error", "No se ha configurado [test_recipient] en config.ini.", parent=self.controller.root)
                return

            test_contact = [{'nombre': 'Prueba',
                             'email': test_email, 'telefono': test_phone}]
            subject = self.subject_entry.get().strip()
            email_body = self.email_body_text.get("1.0", tk.END).strip()
            whatsapp_msg = self.whatsapp_msg_text.get("1.0", tk.END).strip()
            enviar_email = self.send_email_var.get()
            enviar_whatsapp = self.send_whatsapp_var.get()

            if not enviar_email and not enviar_whatsapp:
                messagebox.showwarning(
                    "Advertencia", "Selecciona un canal para la prueba.", parent=self.controller.root)
                return

            self.controller.log_to_console("Iniciando envío de prueba...")
            threading.Thread(target=self._enviar_mensajes_task, args=(
                test_contact, subject, email_body, whatsapp_msg, enviar_email, enviar_whatsapp), daemon=True).start()
        except Exception as e:
            messagebox.showerror(
                "Error", f"No se pudo realizar el envío de prueba.\nError: {e}", parent=self.controller.root)
