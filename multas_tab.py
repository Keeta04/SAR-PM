import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import csv
from datetime import datetime
from tkcalendar import DateEntry
from mysql.connector import IntegrityError, Error as MySQLError
import ui_constants as const


class MultasTab(ttk.Frame):
    """
    Clase que encapsula toda la funcionalidad de la pestaña de Multas.
    """

    def __init__(self, parent, controller, **kwargs):
        super().__init__(parent, **kwargs)
        self.controller = controller

        # Variables de estado de esta pestaña
        self.filtro_ano = None
        self.filtro_mes = None

        self.create_widgets()

        # Carga inicial de datos
        if self.controller.db_manager:
            # Aseguramos que las descripciones de multas se carguen primero
            self.controller.root.after(
                100, self.controller._cargar_descripciones_thread)
            self.controller.root.after(150, self._cargar_multas_thread)

    def create_widgets(self):
        """Crea todos los widgets para la pestaña de multas."""
        frame = self

        multas_tree_frame = ttk.Frame(frame)
        multas_tree_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        columns_multas = ('expediente', 'cedula', 'uc', 'bs',
                          'fecha_multa', 'fecha_pago', 'estado')
        self.multas_tree = ttk.Treeview(
            multas_tree_frame, columns=columns_multas, show='headings')

        self.multas_tree.heading('expediente', text='N° Expediente')
        self.multas_tree.heading('cedula', text='Cédula/RIF')
        self.multas_tree.heading('uc', text='U/C')
        self.multas_tree.heading('bs', text='Monto (Bs)')
        self.multas_tree.heading('fecha_multa', text='Fecha Multa')
        self.multas_tree.heading('fecha_pago', text='Fecha Pago')
        self.multas_tree.heading('estado', text='Estado')

        self.multas_tree.column('expediente', width=120)
        self.multas_tree.column('cedula', width=100)
        self.multas_tree.column('uc', width=60, anchor='center')
        self.multas_tree.column('bs', width=120, anchor='e')
        self.multas_tree.column('fecha_multa', width=100, anchor='center')
        self.multas_tree.column('fecha_pago', width=100, anchor='center')
        self.multas_tree.column('estado', width=100, anchor='center')

        vsb_multas = ttk.Scrollbar(
            multas_tree_frame, orient="vertical", command=self.multas_tree.yview)
        self.multas_tree.configure(yscrollcommand=vsb_multas.set)
        vsb_multas.pack(side='right', fill='y')
        self.multas_tree.pack(side='left', fill='both', expand=True)

        multas_controls_frame = ttk.LabelFrame(frame, text="Controles")
        multas_controls_frame.pack(fill=tk.X, padx=10, pady=10)

        btn_frame_1 = ttk.Frame(multas_controls_frame)
        btn_frame_1.pack(pady=5, fill=tk.X)
        tk.Button(btn_frame_1, text="Añadir Multa", **const.BUTTON_STYLE,
                  command=self.open_add_multa_window).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame_1, text="Editar Multa", **const.BUTTON_STYLE,
                  command=self.open_edit_multa_window).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame_1, text="Eliminar Multa", **const.BUTTON_STYLE,
                  command=self.delete_selected_multa).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame_1, text="Marcar Pagada/Pendiente", **const.BUTTON_STYLE,
                  command=self.toggle_multa_status).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame_1, text="Actualizar Lista", **const.BUTTON_STYLE,
                  command=self._cargar_multas_thread).pack(side=tk.LEFT, padx=5)

        btn_frame_2 = ttk.Frame(multas_controls_frame)
        btn_frame_2.pack(pady=5, fill=tk.X)
        tk.Button(btn_frame_2, text="Generar Reporte Avanzado...", **const.BUTTON_STYLE,
                  command=self.open_report_filter_window).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame_2, text="Limpiar Filtro de Vista", **const.BUTTON_STYLE,
                  command=self._limpiar_filtro_multas).pack(side=tk.LEFT, padx=5)

        ie_frame = ttk.Frame(btn_frame_2)
        ie_frame.pack(side=tk.RIGHT, padx=5)
        tk.Button(ie_frame, text="Importar Multas (CSV)", **const.BUTTON_STYLE,
                  command=self.import_multas_from_csv).pack(side=tk.LEFT, padx=5)
        tk.Button(ie_frame, text="Exportar Multas (CSV)", **const.BUTTON_STYLE,
                  command=self.export_multas_to_csv).pack(side=tk.LEFT, padx=5)

    def _cargar_multas_thread(self):
        if not self.controller.db_manager:
            return
        threading.Thread(target=self._cargar_multas_task, daemon=True).start()

    def _cargar_multas_task(self):
        try:
            multas = self.controller.db_manager.get_all_fines(
                self.filtro_ano, self.filtro_mes)

            def update_gui():
                self.multas_tree.delete(*self.multas_tree.get_children())
                for m in multas:
                    estado = "Pendiente" if m.get(
                        'multa_pendiente') else "Pagada"
                    fecha_m = m.get('fecha_multa').strftime(
                        '%Y-%m-%d') if m.get('fecha_multa') else "N/A"
                    fecha_p = m.get('fecha_pago').strftime(
                        '%Y-%m-%d') if m.get('fecha_pago') else "---"
                    monto_bs = f"{m.get('bs', 0.00):,.2f}".replace(
                        ",", "X").replace(".", ",").replace("X", ".")
                    uc = m.get('uc') or 0
                    values = (m['expediente_nro'], m['cedula_rif'],
                              uc, monto_bs, fecha_m, fecha_p, estado)
                    self.multas_tree.insert("", "end", values=values)
            self.controller.root.after(0, update_gui)
        except MySQLError as e:
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Error al cargar multas: {e}", "error"))

    def _limpiar_filtro_multas(self):
        if self.filtro_ano is None and self.filtro_mes is None:
            return
        self.filtro_ano = None
        self.filtro_mes = None
        self.controller.log_to_console("Filtro de vista de multas limpiado.")
        self._cargar_multas_thread()

    def open_add_multa_window(self):
        self.multa_window = tk.Toplevel(self.controller.root)
        self.multa_window.title("Añadir Nueva Multa")
        self.multa_window.geometry("400x450")
        self.multa_window.transient(self.controller.root)
        self.multa_window.grab_set()
        self.controller._center_toplevel(self.multa_window)

        cedula_prefix_var = tk.StringVar(value='V')
        cedula_num_var = tk.StringVar()
        expediente_num_var = tk.StringVar()
        descripcion_var = tk.StringVar()
        uc_var = tk.IntVar(value=0)
        fecha_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))

        main_frame = ttk.Frame(self.multa_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        cedula_frame = ttk.LabelFrame(
            main_frame, text="Cédula/RIF del Contacto")
        cedula_frame.pack(fill='x', pady=5)
        cedula_prefix_combo = ttk.Combobox(cedula_frame, textvariable=cedula_prefix_var, values=[
                                           'V', 'E', 'J', 'G'], state="readonly", width=4)
        cedula_prefix_combo.pack(side=tk.LEFT, pady=5, padx=5)
        cedula_num_entry = ttk.Entry(cedula_frame, textvariable=cedula_num_var)
        cedula_num_entry.pack(side=tk.LEFT, fill='x',
                              expand=True, pady=5, padx=5)

        expediente_frame = ttk.LabelFrame(
            main_frame, text="Datos del Expediente")
        expediente_frame.pack(fill='x', pady=5)
        ttk.Label(expediente_frame,
                  text="N° de Expediente (ej: EXP-001):").pack(anchor='w', padx=5)
        ttk.Entry(expediente_frame, textvariable=expediente_num_var).pack(
            fill='x', padx=5, pady=2)
        ttk.Label(expediente_frame,
                  text="Descripción / Tipo (Opcional):").pack(anchor='w', padx=5)
        desc_combo = ttk.Combobox(
            expediente_frame, textvariable=descripcion_var, values=self.controller.multa_descripciones)
        desc_combo.pack(fill='x', padx=5, pady=2)

        data_frame = ttk.LabelFrame(main_frame, text="Datos Adicionales")
        data_frame.pack(fill='x', pady=5)
        ttk.Label(
            data_frame, text="Unidades de Crédito (U/C):").pack(anchor='w', padx=5)
        ttk.Entry(data_frame, textvariable=uc_var).pack(
            fill='x', padx=5, pady=2)
        ttk.Label(data_frame, text="Fecha de la Multa:").pack(
            anchor='w', padx=5)
        DateEntry(data_frame, textvariable=fecha_var, date_pattern='y-mm-dd',
                  width=12, drop_down_grab=True).pack(fill='x', padx=5, pady=2)

        def on_save():
            cedula_num = cedula_num_var.get().strip()
            cedula = f"{cedula_prefix_var.get()}-{cedula_num}"
            numero_exp = expediente_num_var.get().strip()
            descripcion = descripcion_var.get().strip()
            expediente_completo = f"{numero_exp} {descripcion}" if descripcion else numero_exp
            fecha_multa = fecha_var.get()

            if not cedula_num or not numero_exp:
                messagebox.showerror(
                    "Error de Validación", "La Cédula/RIF y el N° de Expediente son obligatorios.", parent=self.multa_window)
                return
            try:
                uc = uc_var.get()
            except tk.TclError:
                messagebox.showerror(
                    "Error de Validación", "El valor de U/C debe ser un número entero.", parent=self.multa_window)
                return

            if messagebox.askyesno("Estado de la Multa", "¿Desea registrar esta multa como PAGADA?", parent=self.multa_window):
                monto_bs, fecha_pago = self._get_payment_details_from_popup()
                if monto_bs is None:
                    self.controller.log_to_console(
                        "Registro de pago cancelado.")
                    return
                es_pagada = True
            else:
                es_pagada = False
                monto_bs = 0.00
                fecha_pago = None

            self._guardar_multa_thread(
                expediente_completo, cedula, uc, fecha_multa, es_pagada, monto_bs, fecha_pago)
            self.multa_window.destroy()

        tk.Button(main_frame, text="Guardar Multa", **
                  const.BUTTON_STYLE, command=on_save).pack(pady=20)

    def _guardar_multa_thread(self, expediente, cedula, uc, fecha_multa, es_pagada, monto_bs, fecha_pago):
        if not self.controller.db_manager:
            return
        threading.Thread(target=self._guardar_multa_task, args=(
            expediente, cedula, uc, fecha_multa, es_pagada, monto_bs, fecha_pago), daemon=True).start()

    def _guardar_multa_task(self, expediente, cedula, uc, fecha_multa, es_pagada, monto_bs, fecha_pago):
        try:
            self.controller.db_manager.add_fine(
                expediente, cedula, uc, fecha_multa, es_pagada, monto_bs, fecha_pago)
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Multa {expediente} guardada para {cedula}."))
            self.controller.root.after(0, self._cargar_multas_thread)
            self.controller.root.after(
                100, self.controller._cargar_descripciones_thread)
        except IntegrityError:
            self.controller.root.after(0, lambda: messagebox.showerror(
                "Error de Duplicado", f"El N° de Expediente '{expediente}' ya existe.", parent=self.controller.root))
        except ValueError as e:
            self.controller.root.after(0, lambda: messagebox.showerror(
                "Error de Contacto", str(e), parent=self.controller.root))
        except MySQLError as e:
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Error al guardar multa: {e}", "error"))

    def open_edit_multa_window(self):
        selected_multa_items = self.multas_tree.selection()
        if not selected_multa_items:
            messagebox.showwarning(
                "Selección Requerida", "Por favor, selecciona una multa de la lista para editar.", parent=self.controller.root)
            return
        if len(selected_multa_items) > 1:
            messagebox.showwarning(
                "Selección Múltiple", "Por favor, edita las multas de una en una.", parent=self.controller.root)
            return

        values = self.multas_tree.item(selected_multa_items[0])['values']
        expediente, cedula, uc_str, _, fecha_multa, _, _ = values

        edit_multa_window = tk.Toplevel(self.controller.root)
        edit_multa_window.title(f"Editar Multa {expediente}")
        edit_multa_window.geometry("400x300")
        edit_multa_window.transient(self.controller.root)
        edit_multa_window.grab_set()
        self.controller._center_toplevel(edit_multa_window)

        uc_var = tk.IntVar(value=int(float(uc_str)))
        fecha_var = tk.StringVar(value=fecha_multa)

        main_frame = ttk.Frame(edit_multa_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text=f"N° Expediente: {expediente} (No editable)").pack(
            anchor='w', pady=5)
        ttk.Label(
            main_frame, text=f"Cédula/RIF: {cedula} (No editable)").pack(anchor='w', pady=5)
        ttk.Label(
            main_frame, text="Unidades de Cuenta (U/C):").pack(anchor='w', pady=5)
        ttk.Entry(main_frame, textvariable=uc_var).pack(fill='x')
        ttk.Label(main_frame, text="Fecha de la Multa:").pack(
            anchor='w', pady=5)
        DateEntry(main_frame, textvariable=fecha_var, date_pattern='y-mm-dd',
                  width=12, drop_down_grab=True).pack(fill='x')

        def on_update():
            try:
                uc_nuevo = uc_var.get()
            except tk.TclError:
                messagebox.showerror(
                    "Error de Validación", "U/C debe ser un número entero.", parent=edit_multa_window)
                return
            fecha_nueva = fecha_var.get()
            threading.Thread(target=self._actualizar_multa_task, args=(
                expediente, uc_nuevo, fecha_nueva), daemon=True).start()
            edit_multa_window.destroy()

        tk.Button(main_frame, text="Guardar Cambios", **
                  const.BUTTON_STYLE, command=on_update).pack(pady=20)

    def _actualizar_multa_task(self, expediente, uc, fecha):
        if not self.controller.db_manager:
            return
        try:
            self.controller.db_manager.update_fine_details(
                expediente, uc, fecha)
            self.controller.root.after(
                0, self.controller.log_to_console, f"Multa {expediente} actualizada correctamente.")
            self.controller.root.after(0, self._cargar_multas_thread)
        except MySQLError as e:
            self.controller.root.after(0, self.controller.log_to_console,
                                       f"Error al actualizar la multa {expediente}: {e}", "error")

    def delete_selected_multa(self):
        selected_items = self.multas_tree.selection()
        if not selected_items:
            messagebox.showwarning(
                "Selección Requerida", "Por favor, selecciona una o más multas para eliminar.", parent=self.controller.root)
            return

        if messagebox.askyesno("Confirmar Eliminación", f"¿Seguro que quieres eliminar {len(selected_items)} multa(s)? Esta acción es irreversible.", parent=self.controller.root):
            expedientes = [self.multas_tree.item(
                item)['values'][0] for item in selected_items]
            if not self.controller.db_manager:
                return
            threading.Thread(target=self._delete_multa_task,
                             args=(expedientes,), daemon=True).start()

    def _delete_multa_task(self, expedientes):
        try:
            self.controller.db_manager.delete_fines(expedientes)
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"{len(expedientes)} multa(s) eliminada(s)."))
            self.controller.root.after(0, self._cargar_multas_thread)
        except MySQLError as e:
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Error al eliminar multas: {e}", "error"))

    def toggle_multa_status(self):
        selected_items = self.multas_tree.selection()
        if not selected_items:
            messagebox.showwarning(
                "Selección Requerida", "Por favor, selecciona una multa para cambiar su estado.", parent=self.controller.root)
            return
        if len(selected_items) > 1:
            messagebox.showwarning(
                "Selección Múltiple", "Por favor, cambia el estado de una multa a la vez.", parent=self.controller.root)
            return

        item = self.multas_tree.item(selected_items[0])
        expediente = item['values'][0]
        estado_actual = item['values'][-1]

        if estado_actual == "Pendiente":
            monto_bs, fecha_pago = self._get_payment_details_from_popup()
            if monto_bs is not None:
                if not self.controller.db_manager:
                    return
                threading.Thread(target=self._mark_as_paid_task, args=(
                    expediente, monto_bs, fecha_pago), daemon=True).start()
        else:
            if messagebox.askyesno("Confirmar Acción", f"La multa {expediente} ya está pagada.\n¿Deseas revertirla a PENDIENTE?", parent=self.controller.root):
                if not self.controller.db_manager:
                    return
                threading.Thread(target=self._revert_to_pending_task, args=(
                    expediente,), daemon=True).start()

    def _get_payment_details_from_popup(self):
        details_window = tk.Toplevel(self.controller.root)
        details_window.title("Registrar Detalles del Pago")
        details_window.geometry("350x250")
        self.controller._center_toplevel(details_window)
        details_window.transient(self.controller.root)
        details_window.grab_set()

        monto_bs_var = tk.DoubleVar()
        fecha_pago_var = tk.StringVar(
            value=datetime.now().strftime('%Y-%m-%d'))
        result = {"monto": None, "fecha": None}

        main_frame = ttk.Frame(details_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(main_frame, text="Monto Pagado (Bs.):").pack()
        ttk.Entry(main_frame, textvariable=monto_bs_var,
                  justify='right').pack(pady=5)
        ttk.Label(main_frame, text="Fecha de Pago:").pack()
        DateEntry(main_frame, textvariable=fecha_pago_var,
                  date_pattern='y-mm-dd', drop_down_grab=True).pack(pady=5)

        def on_confirm():
            try:
                monto = monto_bs_var.get()
                if monto <= 0:
                    messagebox.showerror(
                        "Error", "El monto debe ser un número positivo.", parent=details_window)
                    return
                result["monto"] = monto
                result["fecha"] = fecha_pago_var.get()
                details_window.destroy()
            except tk.TclError:
                messagebox.showerror(
                    "Error", "El monto debe ser un número válido.", parent=details_window)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=20)
        ttk.Button(btn_frame, text="Confirmar Pago",
                   command=on_confirm).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancelar",
                   command=details_window.destroy).pack(side=tk.LEFT, padx=5)

        self.controller.root.wait_window(details_window)
        return result["monto"], result["fecha"]

    def _mark_as_paid_task(self, expediente, monto, fecha):
        try:
            self.controller.db_manager.mark_fine_as_paid(
                expediente, monto, fecha)
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Pago de la multa {expediente} registrado."))
            self.controller.root.after(0, self._cargar_multas_thread)
        except MySQLError as e:
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Error al registrar pago: {e}", "error"))

    def _revert_to_pending_task(self, expediente):
        try:
            self.controller.db_manager.revert_fine_to_pending(expediente)
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Multa {expediente} revertida a pendiente."))
            self.controller.root.after(0, self._cargar_multas_thread)
        except MySQLError as e:
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Error al revertir multa: {e}", "error"))

    def import_multas_from_csv(self):
        """Abre el diálogo para seleccionar un CSV e inicia el hilo de importación."""
        if not self.controller.db_manager:
            self.controller.log_to_console(
                "Operación cancelada: sin conexión a la BD.", "error")
            return

        filepath = filedialog.askopenfilename(
            title="Importar Multas desde CSV",
            filetypes=(("Archivos CSV", "*.csv"),
                       ("Todos los archivos", "*.*")),
            parent=self.controller.root
        )
        if not filepath:
            self.controller.log_to_console(
                "Importación de multas cancelada por el usuario.")
            return

        threading.Thread(target=self._import_multas_task,
                         args=(filepath,), daemon=True).start()

    def _import_multas_task(self, filepath):
        """Lee el CSV y delega la inserción de multas a la BD."""
        multas_a_insertar = []
        multas_omitidas = 0
        try:
            contactos_validos = self.controller.db_manager.get_all_contact_cedulas()

            with open(filepath, mode='r', newline='', encoding='utf-8-sig') as csvfile:
                reader = csv.DictReader(csvfile)
                for i, row in enumerate(reader, start=2):
                    cedula = row.get('cedula_rif', '').strip()
                    expediente = row.get('expediente_nro', '').strip()

                    if not expediente or not cedula or cedula not in contactos_validos:
                        multas_omitidas += 1
                        continue

                    try:
                        uc = int(row.get('uc', '0').strip())
                        bs = float(row.get('bs', '0.00').strip())
                        fecha_multa = datetime.strptime(
                            row.get('fecha_multa', ''), '%Y-%m-%d').date()
                        fecha_pago_str = row.get('fecha_pago', '').strip()
                        fecha_pago = datetime.strptime(
                            fecha_pago_str, '%Y-%m-%d').date() if fecha_pago_str else None
                        pendiente = row.get('multa_pendiente', 'true').strip().lower() in [
                            'true', '1', 't', 'y', 'yes', 'pendiente']
                    except (ValueError, TypeError):
                        multas_omitidas += 1
                        continue

                    multas_a_insertar.append(
                        (expediente, cedula, uc, bs, fecha_multa, fecha_pago, pendiente))

            if not multas_a_insertar:
                self.controller.root.after(0, lambda: messagebox.showwarning(
                    "Importación", "No se encontraron multas válidas para importar.", parent=self.controller.root))
                return

            insertadas_count = self.controller.db_manager.import_fines_from_list(
                multas_a_insertar)
            total_omitidas = len(multas_a_insertar) - \
                insertadas_count + multas_omitidas

            self.controller.root.after(0, lambda: messagebox.showinfo("Importación Completada",
                                                                      f"Proceso finalizado.\n\n"
                                                                      f"Multas nuevas insertadas: {insertadas_count}\n"
                                                                      f"Multas omitidas (duplicadas o con errores): {total_omitidas}",
                                                                      parent=self.controller.root))
            self.controller.root.after(0, self._cargar_multas_thread)

        except Exception as e:
            self.controller.root.after(0, lambda: messagebox.showerror(
                "Error de Importación", f"Ocurrió un error inesperado.\nError: {e}", parent=self.controller.root))

    def export_multas_to_csv(self):
        """Abre el diálogo para guardar el CSV e inicia el hilo de exportación."""
        if not self.controller.db_manager:
            self.controller.log_to_console(
                "Operación cancelada: sin conexión a la BD.", "error")
            return

        filepath = filedialog.asksaveasfilename(
            title="Exportar Multas a CSV",
            defaultextension=".csv",
            filetypes=(("Archivos CSV", "*.csv"),
                       ("Todos los archivos", "*.*")),
            initialfile="Reporte_Multas.csv",
            parent=self.controller.root
        )
        if not filepath:
            self.controller.log_to_console(
                "Exportación de multas cancelada por el usuario.")
            return

        threading.Thread(target=self._export_multas_task,
                         args=(filepath,), daemon=True).start()

    def _export_multas_task(self, filepath):
        """Obtiene las multas del manager y las escribe en un archivo CSV."""
        try:
            # Obtiene las multas respetando el filtro de vista actual
            multas_a_exportar = self.controller.db_manager.get_all_fines(
                self.filtro_ano, self.filtro_mes)

            if not multas_a_exportar:
                self.controller.root.after(0, lambda: messagebox.showinfo(
                    "Sin Datos", "No hay multas para exportar con el filtro de vista actual.", parent=self.controller.root))
                return

            fieldnames = ['expediente_nro', 'cedula_rif', 'uc',
                          'bs', 'fecha_multa', 'fecha_pago', 'multa_pendiente']

            with open(filepath, mode='w', newline='', encoding='utf-8-sig') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(multas_a_exportar)

            self.controller.root.after(0, lambda: messagebox.showinfo(
                "Exportación Exitosa", f"Se han exportado {len(multas_a_exportar)} multas a:\n{filepath}", parent=self.controller.root
            ))

        except Exception as e:
            self.controller.root.after(0, lambda: messagebox.showerror(
                "Error de Exportación", f"No se pudo guardar el archivo CSV.\nError: {e}", parent=self.controller.root))

    def open_report_filter_window(self):
        self.report_window = tk.Toplevel(self.controller.root)
        self.report_window.title("Generar Reporte Avanzado de Multas")
        self.report_window.geometry("450x400")
        self.report_window.transient(self.controller.root)
        self.report_window.grab_set()
        self.controller._center_toplevel(self.report_window)

        main_frame = ttk.Frame(self.report_window, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)

        start_date_var = tk.StringVar()
        end_date_var = tk.StringVar()
        status_var = tk.StringVar(value="Todas")
        cedula_var = tk.StringVar()

        dates_frame = ttk.LabelFrame(
            main_frame, text="Filtrar por Rango de Fechas (Opcional)")
        dates_frame.pack(fill=tk.X, pady=5)
        ttk.Label(dates_frame, text="Desde:").pack(
            side=tk.LEFT, padx=5, pady=5)
        DateEntry(dates_frame, textvariable=start_date_var, date_pattern='y-mm-dd',
                  width=12, drop_down_grab=True).pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Label(dates_frame, text="Hasta:").pack(
            side=tk.LEFT, padx=5, pady=5)
        DateEntry(dates_frame, textvariable=end_date_var, date_pattern='y-mm-dd',
                  width=12, drop_down_grab=True).pack(side=tk.LEFT, padx=5, pady=5)

        status_frame = ttk.LabelFrame(
            main_frame, text="Filtrar por Estado (Opcional)")
        status_frame.pack(fill=tk.X, pady=10)
        status_combo = ttk.Combobox(status_frame, textvariable=status_var, values=[
                                    "Todas", "Pagadas", "Pendientes"], state="readonly")
        status_combo.pack(pady=5, padx=5)

        contact_frame = ttk.LabelFrame(
            main_frame, text="Filtrar por Contacto (Opcional)")
        contact_frame.pack(fill=tk.X, pady=5)
        ttk.Label(contact_frame,
                  text="Cédula/RIF del Contacto:").pack(anchor='w', padx=5)
        ttk.Entry(contact_frame, textvariable=cedula_var).pack(
            fill='x', padx=5, pady=5)

        def on_generate():
            start_date = start_date_var.get() if start_date_var.get() else None
            end_date = end_date_var.get() if end_date_var.get() else None
            status_map = {"Todas": "all", "Pagadas": "pagada",
                          "Pendientes": "pendiente"}
            status = status_map[status_var.get()]
            cedula = cedula_var.get()

            self._ask_and_generate_advanced_report(
                start_date, end_date, status, cedula)
            self.report_window.destroy()

        tk.Button(main_frame, text="Generar Reporte PDF", **
                  const.BUTTON_STYLE, command=on_generate).pack(pady=20)

    def _ask_and_generate_advanced_report(self, start_date, end_date, status, cedula):
        filepath = filedialog.asksaveasfilename(
            title="Guardar Reporte de Multas",
            defaultextension=".pdf",
            filetypes=(("Archivos PDF", "*.pdf"),),
            initialfile="Reporte_Avanzado_Multas.pdf",
            parent=self.controller.root
        )
        if not filepath:
            self.controller.log_to_console("Generación de reporte cancelada.")
            return

        self.controller.log_to_console(
            "Iniciando generación de reporte avanzado...")
        threading.Thread(target=self._generate_advanced_pdf_report_task,
                         args=(filepath, start_date, end_date, status, cedula),
                         daemon=True).start()

    def _generate_advanced_pdf_report_task(self, filepath, start_date, end_date, status, cedula):
        if not self.controller.db_manager:
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                "Generación de PDF cancelada: sin conexión a la BD.", "error"))
            return
        try:
            multas = self.controller.db_manager.get_fines_for_report(
                start_date, end_date, status, cedula)
            if not multas:
                self.controller.root.after(0, lambda: messagebox.showinfo(
                    "Sin Datos", "No se encontraron multas que coincidan con los filtros seleccionados.", parent=self.controller.root))
                return

            title = "Reporte Avanzado de Multas"
            subtitle_parts = []
            if start_date:
                subtitle_parts.append(f"Desde: {start_date}")
            if end_date:
                subtitle_parts.append(f"Hasta: {end_date}")
            if status != 'all':
                subtitle_parts.append(f"Estado: {status.capitalize()}")
            if cedula:
                subtitle_parts.append(f"Contacto: {cedula}")
            if subtitle_parts:
                title += f" ({', '.join(subtitle_parts)})"

            self.controller.services_manager.generate_pdf_report(
                multas, title, filepath)
            self.controller.root.after(0, lambda: messagebox.showinfo(
                "Éxito", f"Reporte PDF guardado en:\n{filepath}", parent=self.controller.root))
        except Exception as e:
            self.controller.root.after(0, lambda: self.controller.log_to_console(
                f"Error al generar reporte PDF avanzado: {e}", "error"))
