import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import csv
import re
import phonenumbers
from mysql.connector import IntegrityError, Error as MySQLError
import ui_constants as const


class ContactosTab(ttk.Frame):
    """
    Clase que encapsula toda la funcionalidad de la pestaña de Contactos.
    """

    def __init__(self, parent, controller, **kwargs):
        """
        Inicializa el frame de la pestaña de Contactos.
        Args:
            master: La instancia de la clase principal App, que actúa como controlador.
        """
        super().__init__(parent, **kwargs)
        self.controller = controller  # 'master' es la instancia de la clase App

        # Variables de estado que pertenecen a esta pestaña
        self.current_page = 1
        self.contacts_per_page = 50
        self.total_contacts = 0
        self.total_pages = 1
        self.search_term = ""
        self.unchecked_emoji = "🔲"
        self.checked_emoji = "✅"
        self.all_checked = False
        self.search_job_id = None  # Para la búsqueda asíncrona

        # Referencia a la ventana de añadir/editar para validación
        self.add_edit_window = None

        # Construye la UI de la pestaña
        self.create_widgets()

        # Carga inicial de datos
        if self.controller.db_manager:
            self.controller.root.after(100, self._cargar_contactos_thread)

    def create_widgets(self):
        """Crea todos los widgets para la pestaña de contactos."""
        search_frame = ttk.LabelFrame(
            self, text="Motor de Búsqueda de Contactos")
        search_frame.pack(fill=tk.X, padx=10, pady=(10, 5))

        ttk.Label(
            search_frame, text="Buscar por Cédula/RIF:").pack(side=tk.LEFT, padx=(10, 5), pady=10)
        self.search_entry = ttk.Entry(search_frame, width=30)
        self.search_entry.pack(side=tk.LEFT, padx=5,
                               pady=10, fill=tk.X, expand=True)
        self.search_entry.bind("<KeyRelease>", self.schedule_search)

        search_button = tk.Button(
            search_frame, text="Buscar", **const.BUTTON_STYLE, command=self._perform_search)
        search_button.pack(side=tk.LEFT, padx=5, pady=10)
        clear_button = tk.Button(search_frame, text="Limpiar", **
                                 const.BUTTON_STYLE, command=self._limpiar_busqueda_thread)
        clear_button.pack(side=tk.LEFT, padx=(0, 10), pady=10)

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=0)

        columns_contactos = (
            'check', 'Cédula/RIF', 'Nombre y Apellidos', 'Email', 'Teléfono', 'Dirección')
        self.tree = ttk.Treeview(
            tree_frame, columns=columns_contactos, show='headings')

        self.tree.column('check', width=40, stretch=tk.NO, anchor='center')
        self.tree.heading('check', text=self.unchecked_emoji)
        self.tree.column('Cédula/RIF', width=120, anchor='w')
        self.tree.heading('Cédula/RIF', text='Cédula/RIF')
        self.tree.column('Nombre y Apellidos', width=200, anchor='w')
        self.tree.heading('Nombre y Apellidos', text='Nombre y Apellidos')
        self.tree.column('Email', width=200, anchor='w')
        self.tree.heading('Email', text='Email')
        self.tree.column('Teléfono', width=120, anchor='center')
        self.tree.heading('Teléfono', text='Teléfono')
        self.tree.column('Dirección', width=250, anchor='w')
        self.tree.heading('Dirección', text='Dirección')

        vsb_contactos = ttk.Scrollbar(
            tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb_contactos.set)
        vsb_contactos.pack(side='right', fill='y')
        self.tree.pack(side='left', fill='both', expand=True)
        self.tree.bind('<Button-1>', self.on_tree_click)

        pagination_frame = ttk.Frame(self)
        pagination_frame.pack(fill=tk.X, padx=10, pady=(5, 0))

        self.prev_button = tk.Button(
            pagination_frame, text="< Anterior", **const.BUTTON_STYLE, command=self.previous_page)
        self.prev_button.pack(side=tk.LEFT)
        self.page_label = ttk.Label(pagination_frame, text="Página 1 / 1",
                                    background="#FFFFFF", anchor="center", font=('Segoe UI', 9))
        self.page_label.pack(side=tk.LEFT, expand=True, fill=tk.X)
        self.next_button = tk.Button(
            pagination_frame, text="Siguiente >", **const.BUTTON_STYLE, command=self.next_page)
        self.next_button.pack(side=tk.RIGHT)

        contact_management_frame = ttk.LabelFrame(
            self, text="Gestión de Contactos")
        contact_management_frame.pack(pady=10, padx=10, fill=tk.X)

        btn_frame_contactos = ttk.Frame(contact_management_frame)
        btn_frame_contactos.pack(pady=5)
        tk.Button(btn_frame_contactos, text="Añadir", **const.BUTTON_STYLE,
                  command=self.open_add_contact_window).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame_contactos, text="Editar", **const.BUTTON_STYLE,
                  command=self.iniciar_editar_contacto_thread).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame_contactos, text="Eliminar", **const.BUTTON_STYLE,
                  command=self.delete_selected_contact).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame_contactos, text="Actualizar", **const.BUTTON_STYLE,
                  command=self._cargar_contactos_thread).pack(side=tk.LEFT, padx=5)

        ie_frame_contactos = ttk.Frame(contact_management_frame)
        ie_frame_contactos.pack(pady=5)
        tk.Button(ie_frame_contactos, text="Importar Contactos (CSV)", **
                  const.BUTTON_STYLE, command=self.import_from_csv).pack(side=tk.LEFT, padx=5)
        tk.Button(ie_frame_contactos, text="Exportar Contactos (CSV)", **
                  const.BUTTON_STYLE, command=self.export_to_csv).pack(side=tk.LEFT, padx=5)

    def schedule_search(self, event=None):
        if self.search_job_id:
            self.after_cancel(self.search_job_id)
        self.search_job_id = self.after(500, self._perform_search)

    def _perform_search(self):
        self.search_term = self.search_entry.get().strip()
        self.current_page = 1
        self._cargar_contactos_thread()
        self.controller.log_to_console(
            f"Buscando contactos con: '{self.search_term}'...")

    def _limpiar_busqueda_thread(self):
        if self.search_job_id:
            self.after_cancel(self.search_job_id)
            self.search_job_id = None
        self.search_entry.delete(0, tk.END)
        self.search_term = ""
        self.current_page = 1
        self._cargar_contactos_thread()
        self.controller.log_to_console(
            "Búsqueda limpiada. Mostrando todos los contactos.")

    def update_pagination_controls(self):
        self.page_label.config(
            text=f"Página {self.current_page} / {self.total_pages}")
        is_first_page = self.current_page == 1
        is_last_page = self.current_page == self.total_pages
        self.prev_button.config(state=tk.NORMAL if not is_first_page else tk.DISABLED, **(
            const.BUTTON_STYLE if not is_first_page else const.DISABLED_BUTTON_STYLE))
        self.next_button.config(state=tk.NORMAL if not is_last_page else tk.DISABLED, **(
            const.BUTTON_STYLE if not is_last_page else const.DISABLED_BUTTON_STYLE))

    def next_page(self):
        if self.current_page < self.total_pages:
            self.current_page += 1
            self._cargar_contactos_thread()

    def previous_page(self):
        if self.current_page > 1:
            self.current_page -= 1
            self._cargar_contactos_thread()

    def _cargar_contactos_thread(self):
        if not self.controller.db_manager:
            return
        threading.Thread(target=self._cargar_contactos_task,
                         daemon=True).start()

    def _cargar_contactos_task(self):
        try:
            contactos, total = self.controller.db_manager.get_contacts(
                self.search_term, self.current_page, self.contacts_per_page
            )
            self.total_contacts = total
            self.total_pages = (
                total + self.contacts_per_page - 1) // self.contacts_per_page or 1

            def update_gui():
                self.tree.delete(*self.tree.get_children())
                for c in contactos:
                    values = (self.unchecked_emoji, c['cedula_rif'], c['nombre'], c.get(
                        'email') or "N/A", c.get('telefono') or "N/A", c.get('direccion') or "N/A")
                    self.tree.insert(
                        "", "end", iid=c['cedula_rif'], values=values, tags=('unchecked',))
                self.update_pagination_controls()
                self._update_header_checkbox_state()
                if self.search_term and len(contactos) == 1:
                    threading.Thread(target=self.controller._check_fines_for_contact_thread, args=(
                        contactos[0]['cedula_rif'], contactos[0]['nombre']), daemon=True).start()
            self.controller.root.after(0, update_gui)
        except MySQLError as e:
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Error al cargar contactos: {e}", "error"))

    def import_from_csv(self):
        filepath = filedialog.askopenfilename(
            title="Seleccionar archivo CSV de Contactos",
            filetypes=(("Archivos CSV", "*.csv"),
                       ("Todos los archivos", "*.*")),
            parent=self.controller.root
        )
        if not filepath:
            return

        if not self.controller.db_manager:
            self.controller.log_to_console(
                "Operación cancelada: sin conexión a la BD.", "error")
            return

        try:
            with open(filepath, mode='r', newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                contacts_to_add = []
                for row in reader:
                    cedula_rif = row.get('cedula_rif', '').strip()
                    nombre = row.get('nombre', '').strip()
                    telefono = row.get('telefono', '').strip()
                    if cedula_rif and nombre and telefono:
                        email = row.get('email', '').strip() or None
                        direccion = row.get('direccion', '').strip() or None
                        contacts_to_add.append(
                            (cedula_rif, nombre, email, telefono, direccion))

            if not contacts_to_add:
                messagebox.showwarning(
                    "Importar CSV", "No se encontraron contactos válidos en el archivo.", parent=self.controller.root)
                return

            inserted_count = self.controller.db_manager.import_contacts_from_list(
                contacts_to_add)

            messagebox.showinfo(
                "Importación Exitosa",
                f"Se han importado {inserted_count} nuevos contactos.\nSe ignoraron {len(contacts_to_add) - inserted_count} duplicados.",
                parent=self.controller.root
            )
            self._cargar_contactos_thread()
        except Exception as e:
            messagebox.showerror("Error de Importación",
                                 f"Ocurrió un error: {e}", parent=self.controller.root)

    def export_to_csv(self):
        if not self.controller.db_manager:
            self.controller.log_to_console(
                "Operación cancelada: sin conexión a la BD.", "error")
            return

        filepath = filedialog.asksaveasfilename(
            title="Guardar Contactos como CSV",
            defaultextension=".csv",
            filetypes=(("Archivos CSV", "*.csv"),
                       ("Todos los archivos", "*.*")),
            parent=self.controller.root
        )
        if not filepath:
            return

        try:
            contacts = self.controller.db_manager.get_all_contacts_for_export()

            with open(filepath, mode='w', newline='', encoding='utf-8-sig') as csvfile:
                fieldnames = ['cedula_rif', 'nombre',
                              'email', 'telefono', 'direccion']
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(contacts)

            messagebox.showinfo(
                "Exportación Exitosa", f"Se han exportado {len(contacts)} contactos.", parent=self.controller.root)
        except Exception as e:
            messagebox.showerror("Error de Exportación",
                                 f"Ocurrió un error: {e}", parent=self.controller.root)

    def on_tree_click(self, event):
        region = self.tree.identify_region(event.x, event.y)
        item_id = self.tree.identify_row(event.y)
        if region == "heading" and self.tree.identify_column(event.x) == '#1':
            self.toggle_all_checkboxes()
            return
        if item_id:
            self.toggle_row_checkbox(item_id)
            self.tree.selection_set(item_id)

    def toggle_all_checkboxes(self):
        children_ids = self.tree.get_children()
        if not children_ids:
            return
        all_are_checked = all('checked' in self.tree.item(
            item_id, 'tags') for item_id in children_ids)
        target_state_is_checked = not all_are_checked
        new_emoji = self.checked_emoji if target_state_is_checked else self.unchecked_emoji
        new_tag = 'checked' if target_state_is_checked else 'unchecked'
        old_tag = 'unchecked' if target_state_is_checked else 'checked'
        for item_id in children_ids:
            current_values = list(self.tree.item(item_id, 'values'))
            current_values[0] = new_emoji
            self.tree.item(item_id, values=tuple(current_values))
            current_tags = list(self.tree.item(item_id, 'tags'))
            if old_tag in current_tags:
                current_tags.remove(old_tag)
            current_tags.append(new_tag)
            self.tree.item(item_id, tags=current_tags)
        self.all_checked = target_state_is_checked
        self.tree.heading('check', text=new_emoji)

    def toggle_row_checkbox(self, item_id):
        current_tags = list(self.tree.item(item_id, 'tags'))
        is_checked = 'checked' in current_tags
        new_emoji = self.unchecked_emoji if is_checked else self.checked_emoji
        new_tag = 'unchecked' if is_checked else 'checked'
        old_tag = 'checked' if is_checked else 'unchecked'
        current_values = list(self.tree.item(item_id, 'values'))
        current_values[0] = new_emoji
        self.tree.item(item_id, values=tuple(current_values))
        current_tags.remove(old_tag)
        current_tags.append(new_tag)
        self.tree.item(item_id, tags=current_tags)
        self._update_header_checkbox_state()

    def _update_header_checkbox_state(self):
        children_ids = self.tree.get_children()
        if not children_ids:
            self.all_checked = False
        else:
            self.all_checked = all('checked' in self.tree.item(
                cid, 'tags') for cid in children_ids)
        self.tree.heading(
            'check', text=self.checked_emoji if self.all_checked else self.unchecked_emoji)

    def _validar_datos_contacto(self, cedula_rif, nombre, email, telefono, window):
        if not cedula_rif or not re.match(r'^[VEJG]-[0-9]+$', cedula_rif.upper()):
            messagebox.showwarning(
                "Validación", "Formato de Cédula/RIF inválido. Debe ser V-12345678.", parent=window)
            return False
        if not nombre.strip():
            messagebox.showwarning(
                "Validación", "El campo 'Nombre y Apellidos' es obligatorio.", parent=window)
            return False
        if telefono:
            try:
                phonenumbers.parse(telefono, "VE")
            except phonenumbers.phonenumberutil.NumberParseException:
                messagebox.showwarning(
                    "Validación", f"El formato del teléfono '{telefono}' es incorrecto.", parent=window)
                return False
        if email and ("@" not in email or "." not in email.split('@')[-1]):
            messagebox.showwarning(
                "Validación", "Formato de Email inválido.", parent=window)
            return False
        return True

    def open_add_contact_window(self):
        self.controller.log_to_console(
            "Abriendo ventana para añadir contacto...")
        self.add_edit_window = tk.Toplevel(self.controller.root)
        self.add_edit_window.title("Añadir Nuevo Contacto")
        self.add_edit_window.geometry("450x400")
        self.add_edit_window.transient(self.controller.root)
        self.add_edit_window.grab_set()
        self.controller._center_toplevel(self.add_edit_window)

        cedula_prefix_var = tk.StringVar(value='V')
        cedula_num_var = tk.StringVar()
        name_var = tk.StringVar()
        email_var = tk.StringVar()
        phone_var = tk.StringVar()
        direccion_var = tk.StringVar()

        main_frame = ttk.Frame(self.add_edit_window, padding=20)
        main_frame.pack(expand=True, fill=tk.BOTH)

        cedula_frame = ttk.Frame(main_frame)
        cedula_frame.pack(fill='x', pady=2)
        ttk.Label(cedula_frame, text="Cédula/RIF:").pack(anchor='w')
        cedula_prefix_combo = ttk.Combobox(cedula_frame, textvariable=cedula_prefix_var, values=[
                                           'V', 'E', 'J', 'G'], state="readonly", width=4)
        cedula_prefix_combo.pack(side=tk.LEFT, pady=2)
        cedula_prefix_combo.set('V')
        cedula_num_entry = ttk.Entry(cedula_frame, textvariable=cedula_num_var)
        cedula_num_entry.pack(side=tk.LEFT, fill='x',
                              expand=True, padx=(5, 0), pady=2)

        ttk.Label(main_frame, text="Nombre y Apellidos:").pack(
            pady=(10, 0), anchor='w')
        ttk.Entry(main_frame, textvariable=name_var).pack(pady=2, fill='x')
        ttk.Label(main_frame, text="Email:").pack(pady=2, anchor='w')
        ttk.Entry(main_frame, textvariable=email_var).pack(pady=2, fill='x')
        ttk.Label(main_frame, text="Teléfono (Ej: 04121234567):").pack(
            pady=2, anchor='w')
        ttk.Entry(main_frame, textvariable=phone_var).pack(pady=2, fill='x')
        ttk.Label(main_frame, text="Dirección:").pack(pady=2, anchor='w')
        ttk.Entry(main_frame, textvariable=direccion_var).pack(
            pady=2, fill='x')

        def guardar_contacto():
            prefix = cedula_prefix_var.get()
            number = cedula_num_var.get().strip()
            if not prefix or not number:
                messagebox.showwarning(
                    "Validación", "Debe seleccionar un prefijo e ingresar un número de Cédula/RIF.", parent=self.add_edit_window)
                return

            cedula_rif = f"{prefix}-{number}"
            nombre = name_var.get()
            email = email_var.get()
            telefono = phone_var.get()
            direccion = direccion_var.get()

            if not self._validar_datos_contacto(cedula_rif, nombre, email, telefono, self.add_edit_window):
                return

            self._guardar_contacto_thread(
                cedula_rif, nombre, email, telefono, direccion)
            self.add_edit_window.destroy()

        tk.Button(main_frame, text="Guardar", **const.BUTTON_STYLE,
                  command=guardar_contacto).pack(pady=(20, 0))
        self.controller.root.wait_window(self.add_edit_window)

    def _guardar_contacto_thread(self, cedula_rif, nombre, email, telefono, direccion):
        if not self.controller.db_manager:
            return
        threading.Thread(target=self._guardar_contacto_task, args=(
            cedula_rif, nombre, email, telefono, direccion), daemon=True).start()

    def _guardar_contacto_task(self, cedula_rif, nombre, email, telefono, direccion):
        try:
            self.controller.db_manager.add_contact(
                cedula_rif, nombre, email, telefono, direccion)
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Contacto '{nombre}' guardado."))
            self.controller.root.after(0, self._cargar_contactos_thread)
        except IntegrityError:
            self.controller.root.after(0, lambda: messagebox.showerror(
                "Error de Duplicado", f"La Cédula/RIF, Email o Teléfono '{cedula_rif}' ya existe."))
        except MySQLError as e:
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Error al guardar contacto: {e}", "error"))

    def iniciar_editar_contacto_thread(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning(
                "Advertencia", "Selecciona un contacto para editar.", parent=self.controller.root)
            return
        if len(selected_items) > 1:
            messagebox.showwarning(
                "Advertencia", "Selecciona solo un contacto para editar.", parent=self.controller.root)
            return

        original_item_id = selected_items[0]
        item_values = self.tree.item(original_item_id, 'values')

        if len(item_values) < 6:
            return

        cedula_original, nombre_original, email_original, telefono_original, direccion_original = \
            item_values[1], item_values[2], item_values[3], item_values[4], item_values[5]

        # Usamos self.add_edit_window para la ventana, como en el método de añadir
        self.add_edit_window = tk.Toplevel(self.controller.root)
        self.add_edit_window.title(f"Editar Contacto: {nombre_original}")
        self.add_edit_window.geometry("450x400")
        self.add_edit_window.transient(self.controller.root)
        self.add_edit_window.grab_set()
        self.controller._center_toplevel(self.add_edit_window)

        try:
            prefix, number = cedula_original.split('-', 1)
        except ValueError:
            prefix, number = '', cedula_original

        # Variables para los widgets de la ventana de edición
        edit_contact_cedula_prefix_var = tk.StringVar(value=prefix)
        edit_contact_cedula_num_var = tk.StringVar(value=number)
        edit_contact_name_var = tk.StringVar(value=nombre_original)
        edit_contact_email_var = tk.StringVar(
            value=email_original if email_original != "N/A" else "")
        edit_contact_phone_var = tk.StringVar(
            value=telefono_original if telefono_original != "N/A" else "")
        edit_contact_direccion_var = tk.StringVar(
            value=direccion_original if direccion_original != "N/A" else "")

        main_frame = ttk.Frame(self.add_edit_window, padding=20)
        main_frame.pack(expand=True, fill=tk.BOTH)

        cedula_frame = ttk.LabelFrame(
            main_frame, text="Cédula/RIF (No editable)")
        cedula_frame.pack(fill='x', pady=5)

        cedula_prefix_combo = ttk.Combobox(
            cedula_frame, textvariable=edit_contact_cedula_prefix_var, state='disabled', width=4)
        cedula_prefix_combo.pack(side=tk.LEFT, pady=5, padx=5)

        cedula_num_entry = ttk.Entry(
            cedula_frame, textvariable=edit_contact_cedula_num_var, state='readonly')
        cedula_num_entry.pack(side=tk.LEFT, fill='x',
                              expand=True, pady=5, padx=5)

        data_frame = ttk.LabelFrame(main_frame, text="Datos del Contacto")
        data_frame.pack(fill='x', pady=5)
        ttk.Label(data_frame, text="Nombre y Apellidos:").pack(
            anchor='w', padx=5)
        ttk.Entry(data_frame, textvariable=edit_contact_name_var).pack(
            fill='x', padx=5, pady=2)
        ttk.Label(data_frame, text="Email:").pack(anchor='w', padx=5)
        ttk.Entry(data_frame, textvariable=edit_contact_email_var).pack(
            fill='x', padx=5, pady=2)
        ttk.Label(data_frame, text="Teléfono:").pack(anchor='w', padx=5)
        ttk.Entry(data_frame, textvariable=edit_contact_phone_var).pack(
            fill='x', padx=5, pady=2)
        ttk.Label(data_frame, text="Dirección:").pack(anchor='w', padx=5)
        ttk.Entry(data_frame, textvariable=edit_contact_direccion_var).pack(
            fill='x', padx=5, pady=2)

        def actualizar_contacto():
            nombre = edit_contact_name_var.get()
            email = edit_contact_email_var.get()
            telefono = edit_contact_phone_var.get()
            direccion = edit_contact_direccion_var.get()

            if not self._validar_datos_contacto(cedula_original, nombre, email, telefono, self.add_edit_window):
                return

            threading.Thread(target=self._actualizar_contacto_task, args=(
                cedula_original, nombre, email, telefono, direccion, nombre_original), daemon=True).start()
            self.add_edit_window.destroy()

        tk.Button(main_frame, text="Actualizar", **const.BUTTON_STYLE,
                  command=actualizar_contacto).pack(pady=20)
        self.controller.root.wait_window(self.add_edit_window)

    def _actualizar_contacto_task(self, cedula_rif, nombre, email, telefono, direccion, nombre_original):
        if not self.controller.db_manager:
            return
        try:
            self.controller.db_manager.update_contact(
                cedula_rif, nombre, email, telefono, direccion)

            def update_gui():
                current_values = list(self.tree.item(cedula_rif, 'values'))
                new_values = (current_values[0], cedula_rif, nombre,
                              email or "N/A", telefono or "N/A", direccion or "N/A")
                self.tree.item(cedula_rif, values=new_values)
                self.controller.log_to_console(
                    f"Contacto '{nombre_original}' actualizado a '{nombre}'.")

            self.controller.root.after(0, update_gui)
        except IntegrityError:
            self.controller.root.after(0, lambda: messagebox.showerror(
                "Error de Duplicado", "El Email o Teléfono ya está en uso por otro contacto."))
        except MySQLError as e:
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Error al actualizar contacto: {e}", "error"))

    def delete_selected_contact(self):
        selected_items = self.tree.selection()
        if not selected_items:
            messagebox.showwarning(
                "Advertencia", "Selecciona al menos un contacto para eliminar.", parent=self.controller.root)
            return
        if messagebox.askyesno("Confirmar Eliminación", f"¿Seguro que quieres eliminar {len(selected_items)} contacto(s)?", parent=self.controller.root):
            cedulas = [self.tree.item(item)['values'][1]
                       for item in selected_items]
            names = [self.tree.item(item)['values'][2]
                     for item in selected_items]
            if not self.controller.db_manager:
                return
            threading.Thread(target=self._delete_contacts_task,
                             args=(cedulas, names), daemon=True).start()

    def _delete_contacts_task(self, contact_cedulas, names_to_log):
        try:
            self.controller.db_manager.delete_contacts(contact_cedulas)

            def update_gui():
                for cid in contact_cedulas:
                    if self.tree.exists(cid):
                        self.tree.delete(cid)
                self.controller.log_to_console(
                    f"Contactos eliminados: {', '.join(names_to_log)}.")
                self._update_header_checkbox_state()
            self.controller.root.after(0, update_gui)
        except MySQLError as e:
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Error al eliminar contactos: {e}", "error"))

    def get_selected_contacts(self):
        """
        Devuelve una lista de diccionarios de los contactos seleccionados (checkbox marcado).
        """
        selected_items = [item_id for item_id in self.tree.get_children(
        ) if 'checked' in self.tree.item(item_id, 'tags')]

        if not selected_items:
            return []

        contacts_to_send = []
        for item_id in selected_items:
            values = self.tree.item(item_id)['values']
            contact_dict = {
                'id': values[1],
                'nombre': values[2],
                'email': values[3],
                'telefono': values[4]
            }
            contacts_to_send.append(contact_dict)

        return contacts_to_send
