import openpyxl 
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, send_from_directory, make_response
from openpyxl import Workbook, load_workbook
from datetime import datetime
import os
from io import BytesIO
import pandas as pd
import traceback
from werkzeug.utils import secure_filename
import shutil
from openpyxl.utils.dataframe import dataframe_to_rows
import subprocess
import sys
import json
from openpyxl.styles import Alignment


app = Flask(__name__)
app.secret_key = os.urandom(24)  # Clave secreta segura

# Usuarios temporales (eliminar cuando se implemente BD)
USUARIOS_TEMPORALES = {
    'admin': {
        'password': 'admin1234',
        'roles': ['admin']  
    },
    'auxiliar': {
        'password': 'auxiliar1234',
        'roles': ['auxiliar']  
    },
    'arquitecto': {
        'password': 'arquitecto1234',
        'roles': ['arquitecto']  
    }
}
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_STORAGE_PATH = os.path.join(BASE_DIR, 'proyectos_data.json')  # Ruta del archivo JSON

# Configuración para Cupo Sombrilla
CUPO_SOMBRILLA_FOLDER = os.path.join(os.getcwd(), 'cupo_sombrilla_files')
if not os.path.exists(CUPO_SOMBRILLA_FOLDER):
    os.makedirs(CUPO_SOMBRILLA_FOLDER)

# Ruta para servir el favicon desde la raíz
@app.route('/LogoBancolombia.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'),
                               'LogoBancolombia.ico', mimetype='image/vnd.microsoft.icon')

@app.route("/")
def index():
    return redirect(url_for('login'))

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username').strip().lower()  # Normaliza el username
        password = request.form.get('password')
        role = request.form.get('role').strip().lower()  # Normaliza el rol
        
        # Validación de credenciales
        if username in USUARIOS_TEMPORALES:
            user_data = USUARIOS_TEMPORALES[username]
            
            if user_data['password'] == password:
                if role in user_data['roles']:
                    session['usuario'] = {
                        'nombre': username,
                        'rol': role
                    }
                    return jsonify({
                        'success': True,
                        'message': 'Autenticación exitosa',
                        'redirect': url_for('menu_principal')
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': f'Rol no válido. Roles permitidos: {", ".join(user_data["roles"])}'
                    }), 401
            else:
                return jsonify({
                    'success': False,
                    'message': 'Contraseña incorrecta'
                }), 401
        else:
            return jsonify({
                'success': False,
                'message': 'Usuario no encontrado'
            }), 401
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))

@app.route("/ruta_protegida")
def ruta_protegida():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
@app.route("/menu")
def menu_principal():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    # Obtener datos del usuario desde la sesión
    usuario = session.get('usuario', {})
    
    return render_template("menuApp.html",
                         usuario_rol=usuario.get('rol', ''),
                         usuario_nombre=usuario.get('nombre', ''))  # Pasar variables correctamente

@app.route("/admin/roles")
def admin_roles():
    # Verificación más flexible de roles
    roles_permitidos = ['admin']  # Puedes agregar más roles
    
    if 'usuario' not in session:
        return redirect(url_for('login', next=request.url))
    
    if session.get('usuario', {}).get('rol') not in roles_permitidos:
        # Renderiza la misma plantilla pero con mensaje de error
        return render_template("pilotosTemplates/admin_roles.html",
                            es_admin=False,
                            acceso_denegado=True,
                            usuario=session['usuario'])
    
    return render_template("pilotosTemplates/admin_roles.html",
                         es_admin=True,
                         usuario=session['usuario'])

@app.route("/pilotos")
def modulo_pilotos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    # Opcional: Verificar si el rol tiene acceso
    if session['usuario']['rol'] not in ['admin', 'auxiliar', 'arquitecto']:
        return redirect(url_for('menu_principal'))
    return render_template("pilotosTemplates/pilotosApp.html")

@app.route("/ventacierta")
def venta_cierta():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    # Opcional: Verificar si el rol tiene acceso
    if session['usuario']['rol'] not in ['admin', 'auxiliar', 'arquitecto']:
        return redirect(url_for('menu_principal'))
    return render_template("ventaCiertaTemplates/importar-datos.html")

@app.route("/crear_proyecto")
def crear_proyecto():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template("pilotosTemplates/crear_proyecto.html")

@app.route("/config")
def config_app():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    return render_template("pilotosTemplates/configApp.html")

@app.route("/seguimiento_proyecto")
def seguimiento_Proyecto():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    return render_template("pilotosTemplates/seguimientoProyecto.html")

@app.route("/historicos_proyectos")
def historicos_Proyectos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    return render_template("pilotosTemplates/historico.html")

@app.route("/validacion_condiciones")
def validacion_condiciones():
    if 'usuario' not in session:
        return redirect(url_for('login'))
        
    return render_template("pilotosTemplates/validacion_condiciones.html")

# Configuración inicial - Cambiar esta ruta según necesidad
EXCEL_PATH = r'\\servidor\carpeta_compartida\proyectos_pilotos.xlsx'

def init_excel():
    if not os.path.exists(EXCEL_PATH):
        wb = Workbook()
        ws = wb.active
        ws.append([
            'Fecha Creación', 'Nombre Proyecto', 'Titular', 'NIT/RUT', 'Ciudad',
            'Tipo Proyecto', 'Fecha Inicio', 'Monto Solicitado', 'Plazo (meses)',
            'Tasa Interés', 'Destino Recursos', 'Participantes', 'Documentos'
        ])
        wb.save(EXCEL_PATH)

@app.route('/guardar_proyecto', methods=['POST'])
def guardar_proyecto():
    try:
        data = request.json
        wb = load_workbook(EXCEL_PATH)
        ws = wb.active
        
        participantes = ", ".join([f"{p['nombre']} ({p['rol']} - {p['participacion']}%)" for p in data['participantes']])
        
        ws.append([
            datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            data['nombre_proyecto'],
            data['titular'],
            data['nit'],
            data['ciudad'],
            data['tipo_proyecto'],
            data['fecha_inicio'],
            data['monto_solicitado'],
            data['plazo'],
            data['tasa_interes'],
            data['destino_recursos'],
            participantes,
            str(data['documentos'])
        ])
        
        wb.save(EXCEL_PATH)
        return jsonify({'success': True, 'message': 'Proyecto guardado en Excel'})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Configuración inicial
EXCEL_PATH = r'\\servidor\carpeta_compartida\proyectos_pilotos.xlsx'
# USUARIOS_TEMPORALES = {
#     'admin': {'password': 'admin1234', 'roles': ['admin']}
# }

def generar_cupo_sombrilla(df_base_codigo, df_base_control, output_path):
    """Genera el archivo final de Cupo Sombrilla"""
    # Inicializar libro Excel
    wb = openpyxl.Workbook()
    
    # --- Hoja VISOR (Principal) ---
    ws_visor = wb.active
    ws_visor.title = "VISOR"
    
    # Añadir fórmulas clave
    ws_visor['D4'] = datetime.now().strftime('%Y-%m-%d')  # Fecha actualización
    ws_visor['D16'] = ""  # Cupo Sombilla Recomendado (se calculará después)
    ws_visor['H25'] = "=IFERROR(H20/(H20+H23), 0)"  # Wallet Share
    
    # --- Hoja PARAMETROS (Optimizada) ---
    ws_param = wb.create_sheet("PARAMETROS")
    # Ejemplo de estructura simplificada
    parametros_data = {
        'Variable': ['% Estrés', 'Participación Deuda Bancolombia', 'Promedio Financiación'],
        'Valor': [0.35, 0.60, 0.75]
    }
    df_param = pd.DataFrame(parametros_data)
    for r in dataframe_to_rows(df_param, index=False, header=True):
        ws_param.append(r)
    
    # --- Hoja base_codigo (Datos desde Python) ---
    ws_base_codigo = wb.create_sheet("base_codigo")
    for r in dataframe_to_rows(df_base_codigo, index=False, header=True):
        ws_base_codigo.append(r)
    
    # --- Hoja base_control (Controles) ---
    ws_base_control = wb.create_sheet("base_control")
    for r in dataframe_to_rows(df_base_control, index=False, header=True):
        ws_base_control.append(r)
    
    # --- Calcular y escribir Cupo Recomendado ---
    cupo_recomendado = calcular_cupo_recomendado(df_base_codigo, df_base_control)
    ws_visor['D16'] = cupo_recomendado
    
    # Guardar archivo final
    wb.save(output_path)

def calcular_cupo_recomendado(df_base_codigo, df_base_control):
    """Lógica compleja de cálculo (ejemplo simplificado)"""
    # Aquí implementarías la lógica real de negocio
    cupo_modelo = df_base_codigo.loc[0, 'Cupo_Modelo']
    ajustes = df_base_control.loc[0, 'Ajuste_GC']
    return cupo_modelo - ajustes

def aplicar_filtros(proyectos, filtros):
    filtered = proyectos
    
    if filtros.get('proyecto'):
        filtered = [p for p in filtered if filtros['proyecto'].lower() in p['nombre'].lower()]
    
    if filtros.get('titular'):
        filtered = [p for p in filtered if filtros['titular'].lower() in p['titular'].lower()]
    
    if filtros.get('nit'):
        filtered = [p for p in filtered if filtros['nit'] in p['nit']]
    
    if filtros.get('arquitecto'):
        filtered = [p for p in filtered if filtros['arquitecto'].lower() in p['arquitecto'].lower()]
    
    return filtered

def obtener_proyectos_desde_excel():
    try:
        wb = load_workbook(EXCEL_PATH)
        ws = wb.active
        
        proyectos = []
        for row in ws.iter_rows(min_row=2, values_only=True):
            arquitecto = next((p.split(' (')[0] for p in str(row[10]).split(', ') if 'Arquitecto' in p), '')
            
            proyecto = {
                'nombre': row[1] if len(row) > 1 else '',
                'titular': row[2] if len(row) > 2 else '',
                'nit': row[3] if len(row) > 3 else '',
                'arquitecto': arquitecto,
                'avance': 0,  # Campo temporal
                'ultimo_desembolso': row[0] if len(row) > 0 else ''
            }
            proyectos.append(proyecto)
        return proyectos
    except Exception as e:
        print(f"Error leyendo Excel: {str(e)}")
        return []

@app.route("/consulta_proyectos")
def consulta_proyectos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    proyectos = obtener_proyectos_desde_excel()
    filtros = request.args.to_dict()
    proyectos_filtrados = aplicar_filtros(proyectos, filtros)
    
    return render_template("pilotosTemplates/consulta_proyectos.html", proyectos=proyectos_filtrados)


# Configuración de rutas
EXPORTAR_RUTA = "C:\\CreditosConstructor"

# Asegurar que la ruta de exportación exista
if not os.path.exists(EXPORTAR_RUTA):
    os.makedirs(EXPORTAR_RUTA, exist_ok=True)

@app.route('/exportar_excel', methods=['POST'])
def exportar_excel():
    try:
        data = request.get_json(force=True)  # Usar force=True para asegurar la lectura
        if not data:
            return jsonify({'success': False, 'message': 'Datos invalidos'}), 400

        proyectos = data.get('proyectos', [])
        if not proyectos:
            return jsonify({'success': False, 'message': 'No hay proyectos para exportar'}), 400

        # Validar campos obligatorios y preparar datos
        campos_obligatorios = ['id_proyecto', 'nombre_proyecto', 'fecha_creacion']
        for proyecto in proyectos:
            # Validar campos obligatorios
            if not all(key in proyecto for key in campos_obligatorios):
                return jsonify({'success': False, 'message': f'Falta campo obligatorio en proyecto {proyecto.get("id_proyecto", "")}'}), 400
            
            # Manejar condiciones_aprobacion
            if 'condiciones_aprobacion' in proyecto:
                if isinstance(proyecto['condiciones_aprobacion'], str):
                    proyecto['condiciones_aprobacion'] = proyecto['condiciones_aprobacion'].split('; ')
                elif not isinstance(proyecto['condiciones_aprobacion'], list):
                    proyecto['condiciones_aprobacion'] = []
            
            # Manejar observacion_control (comentarios)
            if 'observacion_control' in proyecto and proyecto['observacion_control']:
                # Reemplazar saltos de línea por " | "
                proyecto['observacion_control'] = proyecto['observacion_control'].replace('\n', ' | ')
            
            # Asegurar que desembolsos_diarios sea string
            if 'desembolsos_diarios' in proyecto:
                if not isinstance(proyecto['desembolsos_diarios'], str):
                    proyecto['desembolsos_diarios'] = str(proyecto['desembolsos_diarios'])
            else:
                proyecto['desembolsos_diarios'] = 'Sin desembolsos diarios'

        # DataFrame desde payload
        df_nuevo = pd.DataFrame(proyectos).fillna('')

        # Asegurar carpeta de exportes
        if not os.path.exists(EXPORTAR_RUTA):
            os.makedirs(EXPORTAR_RUTA)

        base_path = os.path.join(EXPORTAR_RUTA, 'Base_principal_proyectos.xlsx')

        # ===== Combinar con base existente =====
        if os.path.exists(base_path):
            try:
                df_existente = pd.read_excel(base_path, sheet_name='Proyectos', dtype={'id_proyecto': str})
                df_existente['id_proyecto'] = df_existente['id_proyecto'].astype(str).str.strip()
                
                # Conservar observaciones existentes para proyectos no modificados
                for _, row in df_existente.iterrows():
                    pid = str(row['id_proyecto']).strip()
                    if pid and pid not in df_nuevo['id_proyecto'].astype(str).str.strip().values:
                        proyectos.append(row.to_dict())
                
                df_combinado = pd.concat([df_existente, df_nuevo], ignore_index=True, sort=False)
            except Exception as e:
                print(f"Error leyendo base existente: {e}")
                df_combinado = df_nuevo.copy()
        else:
            df_combinado = df_nuevo.copy()

        # Procesamiento adicional del DataFrame
        df_combinado['id_proyecto'] = df_combinado['id_proyecto'].astype(str).str.strip()
        df_combinado = df_combinado[df_combinado['id_proyecto'] != '']
        
        # Eliminar duplicados manteniendo los más recientes
        df_combinado = df_combinado.drop_duplicates(subset=['id_proyecto'], keep='last')

        # === Forzar inclusión de columnas esperadas, incluso si están vacías ===
        columnas_esperadas = [
            'id_proyecto',
            'nombre_proyecto',
            'fecha_creacion',
            'condiciones_aprobacion',
            'observacion_control',
            'desembolsos_diarios'
        ]

        for col in columnas_esperadas:
            if col not in df_combinado.columns:
                df_combinado[col] = 'Sin datos' if col == 'observacion_control' else ''

        # ===== Guardar Excel =====
        try:
            with pd.ExcelWriter(base_path, engine='openpyxl') as writer:
                df_combinado.to_excel(writer, index=False, sheet_name='Proyectos')
                
                # Configurar protección
                worksheet = writer.sheets['Proyectos']
                try:
                    worksheet.protection.sheet = True
                    worksheet.protection.set_password('Riesgos2025*')
                    worksheet.protection.autoFilter = True
                    worksheet.protection.sort = True
                    worksheet.protection.insertRows = False
                    worksheet.protection.deleteRows = False
                except Exception as e:
                    print(f"No fue posible aplicar proteccion: {e}")

                for column in worksheet.columns:
                    max_length = max(
                        worksheet.cell(row=row, column=column[0].column).value
                        and len(str(worksheet.cell(row=row, column=column[0].column).value))
                        or 0
                        for row in range(1, worksheet.max_row + 1)
                    )
                    worksheet.column_dimensions[column[0].column_letter].width = min(max_length + 2, 150)


        except Exception as e:
            return jsonify({'success': False, 'message': f'Error guardando Excel: {str(e)}'}), 500

        # ===== Actualizar localStorage =====
        # ===== Actualizar LOCAL_STORAGE_PATH (mismo enfoque que en subir_base_principal) =====
        nuevos_cont = 0
        actualizados_cont = 0
        proyectos_guardar = []
        try:
            proyectos_existentes = []
            if os.path.exists(LOCAL_STORAGE_PATH):
                with open(LOCAL_STORAGE_PATH, 'r', encoding='utf-8') as f:
                    try:
                        proyectos_existentes = json.load(f)
                    except json.JSONDecodeError:
                        proyectos_existentes = []

            # Normalizar lista nueva desde df_nuevo (solo registros con id_proyecto no vacio)
            proyectos_nuevos_lista = []
            for proyecto in df_nuevo.to_dict(orient='records'):
                p = dict(proyecto)
                p['id_proyecto'] = str(p.get('id_proyecto', '')).strip()
                if p['id_proyecto'] != '':
                    proyectos_nuevos_lista.append(p)

            existentes_por_id = {}
            for p in proyectos_existentes:
                pid = str(p.get('id_proyecto', '')).strip()
                if pid:
                    existentes_por_id[pid] = p

            nuevos_por_id = {}
            for p in proyectos_nuevos_lista:
                pid = p.get('id_proyecto', '')
                nuevos_por_id[pid] = p

            nuevos_cont = sum(1 for pid in nuevos_por_id if pid not in existentes_por_id)
            actualizados_cont = sum(1 for pid in nuevos_por_id if pid in existentes_por_id)

            # Merge: los nuevos sobreescriben a los existentes
            existentes_por_id.update(nuevos_por_id)
            proyectos_guardar = list(existentes_por_id.values())

            with open(LOCAL_STORAGE_PATH, 'w', encoding='utf-8') as f:
                json.dump(proyectos_guardar, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"Error actualizando localStorage: {str(e)}")
            traceback.print_exc()
            # No abortamos la operacion completa: solo notificamos el problema

        # ===== Preparar conteos tipo 'subir_base_principal' =====
        try:
            if 'df_existente' in locals():
                ids_existentes_previos_excel = set(str(x).strip() for x in df_existente['id_proyecto'].dropna().astype(str))
                ids_nuevos_excel = set(str(x).strip() for x in df_nuevo['id_proyecto'].dropna().astype(str))
                nuevos_excel = len(ids_nuevos_excel - ids_existentes_previos_excel)
                actualizados_excel = len(ids_nuevos_excel & ids_existentes_previos_excel)
            else:
                nuevos_excel = len(df_nuevo['id_proyecto'].dropna().astype(str).str.strip().unique())
                actualizados_excel = 0
        except Exception:
            nuevos_excel = 0
            actualizados_excel = 0

        response = {
            'success': True,
            'message': 'Base principal actualizada',
            'nuevos': nuevos_cont,
            'actualizados': actualizados_cont,
            'nuevos_excel': nuevos_excel,
            'actualizados_excel': actualizados_excel,
            'archivo_base': os.path.basename(base_path),
            'proyectos': proyectos_guardar
        }
        return jsonify(response), 200

    except Exception as e:
        print(f"Error en exportar_excel: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500

    
@app.route('/subir_base_principal', methods=['POST'])
def subir_base_principal():
    import traceback

    try:
        # ===== Lista completa de columnas requeridas (sin cambios de nombres) =====
        COLUMNAS_COMPLETAS = [
            "id_proyecto", "fecha_creacion", "tipo_producto", "rango_proyecto", "grupoPrincipal",
            "subgrupo_1", "subgrupo_2", "subgrupo_3", "nit_grupo_riesgo", "nit_titular",
            "titular_credito", "nombre_proyecto", "tipo_inmuebles", "segmento", "ciudad",
            "tipo_fiducia", "fiduciaria", "gerente", "arquitecto", "auxiliar", "perito",
            "monto_solicitado_1_desembolso", "monto_solicitado_cpi", "monto_solicitado_lote",
            "total_valor_aprobado", "calificacion_it", "costos_financiables", "valor_lote",
            "valor_total_proyecto", "meses_programacion", "total_inmuebles", "meses_para_venta",
            "tipo_credito", "departamento", "caso_pcp_bizagi", "visitas_a_cobrar",
            "cobrar_estudio_tecnico", "fecha_aprobacion", "alerta_fecha_aprobacion",
            "vigencia_en_meses", "instancia_aprobacion", "condiciones_aprobacion",
            "porcentaje_solicitado_financiables", "validacion_licencia", "fecha_radicacion",
            "poliza_decenal", "caso_bizagi_juridico", "control_cruzado", "fecha_confirmacion",
            "fecha_primera_visita", "id_garantia", "meses_avanzados", "plazo_ajustado",
            "fecha_ultimo_informe_de_ventas", "fecha_inicio_de_ventas", "total_esperado_ventas",
            "inmuebles_vendidos_(unidades)", "valor_inmuebles_vendidos", 
            "%_porcentaje_de_ventas_(unidades)", "%_porcentaje_de_ventas_(valor)",
            "valor_por_vender", "valor_canjes", "cartera_recaudada", "cartera_por_recaudar",
            "promedio_mensual", "promedio_trimestral", "validacion_fecha_infventas", "regional",
            "numero_visita", "fecha_visita", "valor_anticipos", "valor_anticipos_almacen",
            "programacion_inicial", "mes_inicio_obra", "avance_obra_meses",
            "avance_esperado_porcentaje", "avance_obra", "inversion_del_proyecto",
            "tipo_inmueble", "numero_de_inmuebles", "valor_garantia", "promedio_spi_trimestre",
            "spi_al_corte", "alerta_en_programación", "estado_ejecución_obra", "cpi_al_corte",
            "imprevistos_usados_a_la_fecha", "alerta_imprevistos_usados_a_la_fecha",
            "alerta_imprevistos_usados_vs_programación", "alerta_ejecutado_vs_invertido",
            "resumen_alerta_del_proyecto", "estado_ejecución_obra_mensual", "consumido_a_la_fecha",
            "imprevistos_y_reajustes_usados", "indirectos_invertidos_a_la_fecha",
            "indirectos_invertidos_en_%", "honorarios_invertidos_a_la_fecha",
            "honorarios_invertidos_en_%", "alerta_consumo_indirectos_vs_programacion",
            "alerta_consumo_honorarios_vs_programacion", "alerta_indirectos_vs_presupuesto",
            "alerta_honorarios_vs_presupuesto", "avance_obra_vs_avance_ci_honorarios_(cd)",
            "avance_obra_vs_avance_ci_honorarios_(ci+h)", "programacion_actual",
            "mes_terminacion_actual", "valla", "valor_entregado", "valor_por_entregar",
            "formula_a", "formula_b", "superavit", "cobertura", "maximo_desembolsar",
            "requiere_visto_bueno", "responsable_carga_desembolso", "fecha_carga_desembolso",
            "responsable_carga_venta", "responsable_carga_visita", "fecha_carga_venta",
            "fecha_carga_visita", "desembolsos_diarios", "valor_entregado_total",
            # Nuevas columnas
            "fecha_ultima_visita", "validacion_estado_ventas", "validacion_fecha_visita",
            "valor_desembolsar_preoperativo", "valor_desembolsar_constructor",
            "maximo_desembolsar_constructor", "maximo_desembolsar_superavit",
            "condiciones_especiales", "fecha_observacion_control", "valor_ampliacion",
            "observacion_control"
        ]

        # ===== Mapeo desde nombres del Excel hacia nombres internos (no normalizar luego) =====
        MAPEO_COLUMNAS = {
            "ID PROYECTO": "id_proyecto",
            "TIPO CRED": "tipo_producto",
            "NUEVO TIPO DE PRODUCTO": "rango_proyecto",
            "NIT": "nit_titular",
            "TITULAR CREDITO": "titular_credito",
            "PROYECTO": "nombre_proyecto",
            "GERENTE": "gerente",
            "APROBADO 1° DESEMBOLSO": "monto_solicitado_1_desembolso",
            "APROBADO CPI": "monto_solicitado_cpi",
            "APROBADO LOTE": "monto_solicitado_lote",
            "VALOR APROBADO": "total_valor_aprobado",
            "COSTOS FINANCIABLES": "costos_financiables",
            "FECHA APROBACION (DD-MM-YY)": "fecha_aprobacion",
            "OBSERVACION (SE DEBE TENER EN CUENTA PARA PRIMER DESEMBOLSO)": "condiciones_aprobacion",
            "VISITAS A COBRAR": "visitas_a_cobrar",
            "COBRAR ESTUDIO TECNICO Y AVALUO": "cobrar_estudio_tecnico",
            "VALOR LOTE": "valor_lote",
            "VALOR GARANTIA": "valor_garantia",
            "VALOR TOTAL PROYECTO": "valor_total_proyecto",
            "FECHA VISITA AVANCE DE OBRA (DD-MM-YY)": "fecha_visita",
            "MESES PROGRAMACION DE OBRA": "meses_programacion",
            "MESES AVANZADOS DE OBRA": "meses_avanzados",
            "MESES PARA VENTA": "meses_para_venta",
            "PLAZO (ajustado según fecha visita)": "plazo_ajustado",
            "VALIDACION LICENCIA DE CONSTRUCCION": "validacion_licencia",
            "FECHA RADICACION LICENCIA ANTE CURADURIA": "fecha_radicacion",
            "REQUIERE POLIZA DECENAL (SI/NO)": "poliza_decenal",
            "FECHA ULTIMO INFORME DE VENTAS (DD-MM-YY)": "fecha_ultimo_informe_de_ventas",
            "TOTAL INMUEBLES": "total_inmuebles",
            "INMUEBLES VENDIDOS": "inmuebles_vendidos_(unidades)",
            "% PORCENTAJE DE VENTAS": "%_porcentaje_de_ventas_(unidades)",
            "VALIDACION ESTADO DE VENTAS": "validacion_estado_ventas",
            "FECHA ULTIMA VISITA AVANCE DE OBRA (DD-MM-YY)": "fecha_ultima_visita",
            "% ULTIMO AVANCE DE OBRA": "avance_obra",
            "VALOR INVERTIDO SEGÚN % AVANCE DE OBRA": "inversion_del_proyecto",
            "VALIDACION FECHA VISITA DE OBRA": "validacion_fecha_visita",
            "PERITO VISITAS": "perito",
            "VALOR ENTREGADO (Preoperativo y Constructor)": "valor_entregado",
            "VALOR X ENTREGAR": "valor_por_entregar",
            "DESEMBOLSO AUTORIZADO CON REGIMEN DE EXCEPCION (VR EN PESOS $)": "desembolsos_diarios",
            "VALOR A DESEMBOLSAR PREOPERATIVO": "valor_desembolsar_preoperativo",
            "VALOR A DESEMBOLSAR CREDITO LOTE": "monto_solicitado_lote",
            "VALOR MAXIMO A DESEMBOLSAR CONSTRUCTOR SEGUN % SOLICITADO": "maximo_desembolsar_constructor",
            "VALOR A DESEMBOLSAR CONSTRUCTOR SEGÚN % MAXIMO": "valor_desembolsar_constructor",
            "VALOR MÁXIMO A DESEMBOLSAR SEGÚN POLITICA DE SUPERÁVIT": "maximo_desembolsar_superavit",
            "VISTO BUENO": "requiere_visto_bueno",
            "RECOMENDACIÓN DESEMBOLSO SEGÚN POLÍTICA PARA DE SUPERÁVIT (COMENTARIO PARA AGREGAR EN BIZAGI) APLICA PARA PROYECTOS APROBADOS DESDE 23/05/2022": "superavit",
            "COBERTURA": "cobertura",
            "SUPERÁVIT": "superavit",
            "PCP BIZAGI": "caso_pcp_bizagi",
            "CONDICIONES ESPECIALES PARA DESEMBOLSAR, VALIDACION VISITAS, OTROS": "condiciones_especiales",
            "AQUITECTO GCC": "arquitecto",
            "AUXILIAR GCC": "auxiliar",
            "CIUDAD PROYECTO": "ciudad",
            "ID - NIT GRUPO DE RIESGO (GERENCIADOR)": "nit_grupo_riesgo",
            "GRUPO DE RIESGO - (GERENCIADOR CARPETA DE CLIENTES PYMES NACIONAL)": "grupoPrincipal",
            "ID GARANTIA (INICIAL Y/O DEFINITIVO)": "id_garantia",
            "INFORMACIÓN INICIAL Y/O DEFINITIVA HIPOTECA": "control_cruzado",
            "CASO BIZAGI JURÍDICO DE CONFIRMACIÓN": "caso_bizagi_juridico",
            "FECHA DE CONFIRMACIÓN ARCHIVO O BIZAGI": "fecha_confirmacion",
            "ESCRIBIR palabra LOTE PARA ESE TIPO DE CREDITO": "tipo_credito",
            "VALOR DESISTIDO": "valor_canjes",
            "VALOR AMPLIACION": "valor_ampliacion",
            "VALOR RECAUDADO": "cartera_recaudada",
            "VALOR POR RECAUDAR": "cartera_por_recaudar",
            "VALOR POR INVERTIR": "valor_por_entregar",
            "VALOR X VENDER": "valor_por_vender",
            "ANTICIPOS Y ALMACEN": "valor_anticipos_almacen",
            "ANÁLISIS INVERSIÓN": "inversion_del_proyecto",
            "FECHA INICIAL TERMINACIÓN": "fecha_inicio_de_ventas",
            "FECHA ACTUAL TERMINACIÓN": "fecha_ultimo_informe_de_ventas",
            "OBSERVACION CONTROL": "observacion_control",
            "FECHA OBSERVACION CONTROL": "fecha_observacion_control",
            "VIGENCIA APROBACIÓN (EN MESES)": "vigencia_en_meses"
        }
        if 'archivo' not in request.files:
            return jsonify({'success': False, 'message': 'No se encontro archivo'}), 400

        archivo = request.files['archivo']
        if archivo.filename == '':
            return jsonify({'success': False, 'message': 'Nombre de archivo invalido'}), 400

        # ===== Backup =====
        crear_backup = request.form.get('backup', 'true') == 'true'
        base_path = os.path.join(EXPORTAR_RUTA, 'Base_principal_proyectos.xlsx')

        if crear_backup and os.path.exists(base_path):
            fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(EXPORTAR_RUTA, f'Backup_{fecha}.xlsx')
            shutil.copyfile(base_path, backup_path)

        # ===== Leer Excel subido =====
        try:
            xls = pd.ExcelFile(archivo)
            if 'Hoja1' not in xls.sheet_names:
                return jsonify({'success': False, 'message': 'El archivo no contiene una hoja llamada "Hoja1"'}), 400

            archivo.seek(0)
            df_nuevo = pd.read_excel(archivo, sheet_name='Hoja1', header=1, dtype={'ID PROYECTO': str})

            if 'ID PROYECTO' not in df_nuevo.columns:
                return jsonify({'success': False, 'message': 'El archivo no contiene la columna "ID PROYECTO"'}), 400

            df_nuevo = df_nuevo.rename(columns=MAPEO_COLUMNAS)

            if 'id_proyecto' in df_nuevo.columns:
                df_nuevo['id_proyecto'] = df_nuevo['id_proyecto'].astype(str).str.strip()
                df_nuevo['id_proyecto'] = df_nuevo['id_proyecto'].replace('nan', '', regex=False)

            df_nuevo = df_nuevo[df_nuevo['id_proyecto'].astype(str).str.strip() != '']

            columnas_disponibles = [col for col in COLUMNAS_COMPLETAS if col in df_nuevo.columns]
            df_nuevo = df_nuevo[columnas_disponibles]

            columnas_fecha = [
                'fecha_creacion', 'fecha_aprobacion', 'fecha_radicacion',
                'fecha_confirmacion', 'fecha_visita', 'fecha_ultimo_informe_de_ventas',
                'fecha_inicio_de_ventas', 'fecha_primera_visita', 'fecha_ultima_visita',
                'fecha_observacion_control'
            ]
            for col in columnas_fecha:
                if col in df_nuevo.columns:
                    valores_originales = df_nuevo[col].copy()
                    try:
                        tmp = pd.to_datetime(df_nuevo[col], errors='coerce', dayfirst=True)
                        mascara_valida = tmp.notna()
                        df_nuevo[col] = valores_originales.astype(str)
                        df_nuevo.loc[mascara_valida, col] = tmp.loc[mascara_valida].dt.strftime('%d/%m/%Y')
                    except Exception:
                        df_nuevo[col] = valores_originales

        except Exception as e:
            return jsonify({'success': False, 'message': f'Error procesando archivo: {str(e)}'}), 400

        # ===== Combinar con base existente (y deduplicar por id_proyecto) =====
        if os.path.exists(base_path):
            try:
                df_existente = pd.read_excel(base_path, sheet_name='Proyectos', dtype={'id_proyecto': str})
                df_existente['id_proyecto'] = df_existente['id_proyecto'].astype(str).str.strip()
                df_combinado = pd.concat([df_existente, df_nuevo], ignore_index=True)
            except Exception as e:
                print(f"Error combinando datos: {str(e)}")
                df_combinado = df_nuevo
        else:
            df_combinado = df_nuevo

        # Asegurarse que todas las columnas existan
        for col in COLUMNAS_COMPLETAS:
            if col not in df_combinado.columns:
                df_combinado[col] = None

        df_combinado = df_combinado[COLUMNAS_COMPLETAS]

        # Eliminar duplicados por id_proyecto dejando el ultimo (los nuevos reemplazan)
        if 'id_proyecto' in df_combinado.columns:
            df_combinado = df_combinado.drop_duplicates(subset=['id_proyecto'], keep='last')

        # ===== Guardar Excel =====
        try:
            with pd.ExcelWriter(base_path, engine='openpyxl') as writer:
                df_combinado.to_excel(writer, index=False, sheet_name='Proyectos')
                worksheet = writer.sheets['Proyectos']
                try:
                    worksheet.protection.sheet = True
                    worksheet.protection.set_password('Riesgos2025*')
                    worksheet.protection.autoFilter = True
                    worksheet.protection.sort = True
                    worksheet.protection.insertRows = False
                    worksheet.protection.deleteRows = False
                except Exception as e:
                    print(f"No fue posible aplicar proteccion: {e}")

                for column in worksheet.columns:
                    max_length = 0
                    column_letter = column[0].column_letter
                    for cell in column:
                        try:
                            val = '' if cell.value is None else str(cell.value)
                            if len(val) > max_length:
                                max_length = len(val)
                        except Exception:
                            pass
                    worksheet.column_dimensions[column_letter].width = min(max_length + 2, 80)

        except Exception as e:
            return jsonify({'success': False, 'message': f'Error guardando archivo: {str(e)}'}), 500

        # ===== Actualizar LOCAL_STORAGE_PATH sin duplicados =====
        try:
            proyectos_existentes = []
            if os.path.exists(LOCAL_STORAGE_PATH):
                with open(LOCAL_STORAGE_PATH, 'r', encoding='utf-8') as f:
                    try:
                        proyectos_existentes = json.load(f)
                    except json.JSONDecodeError:
                        proyectos_existentes = []

            # Normalizar lista nueva desde df_nuevo (solo registros con id_proyecto no vacio)
            proyectos_nuevos_lista = []
            for proyecto in df_nuevo.to_dict(orient='records'):
                p = dict(proyecto)
                p['id_proyecto'] = str(p.get('id_proyecto', '')).strip()
                if p['id_proyecto'] != '':
                    proyectos_nuevos_lista.append(p)

            # Construir diccionarios por id para deduplicar: los nuevos reemplazan a los existentes
            existentes_por_id = {}
            for p in proyectos_existentes:
                pid = str(p.get('id_proyecto', '')).strip()
                if pid:
                    existentes_por_id[pid] = p

            nuevos_por_id = {}
            for p in proyectos_nuevos_lista:
                pid = p.get('id_proyecto', '')
                nuevos_por_id[pid] = p

            # Conteos
            nuevos_cont = sum(1 for pid in nuevos_por_id if pid not in existentes_por_id)
            actualizados_cont = sum(1 for pid in nuevos_por_id if pid in existentes_por_id)

            # Merge: los nuevos sobreescriben a los existentes
            existentes_por_id.update(nuevos_por_id)

            # Lista final para guardar en local storage (solo ids no vacios)
            proyectos_guardar = list(existentes_por_id.values())

            with open(LOCAL_STORAGE_PATH, 'w', encoding='utf-8') as f:
                json.dump(proyectos_guardar, f, ensure_ascii=False, indent=2)

        except Exception as e:
            print(f"Error actualizando localStorage: {str(e)}")
            traceback.print_exc()
            # No abortamos la operacion completa: solo notificamos el problema

        # ===== Preparar respuesta =====
        if 'df_existente' in locals():
            ids_existentes_previos_excel = set(str(x).strip() for x in df_existente['id_proyecto'].dropna().astype(str))
            ids_nuevos_excel = set(str(x).strip() for x in df_nuevo['id_proyecto'].dropna().astype(str))
            nuevos_excel = len(ids_nuevos_excel - ids_existentes_previos_excel)
            actualizados_excel = len(ids_nuevos_excel & ids_existentes_previos_excel)
        else:
            nuevos_excel = len(df_nuevo['id_proyecto'].dropna().astype(str).str.strip().unique())
            actualizados_excel = 0

        return jsonify({
            'success': True,
            'message': 'Base principal actualizada',
            'nuevos': nuevos_cont,
            'actualizados': actualizados_cont,
            'nuevos_excel': nuevos_excel,
            'actualizados_excel': actualizados_excel,
            'proyectos': proyectos_guardar  # lista deduplicada lista para localStorage
        })

    except Exception as e:
        print(f"Error en subir_base_principal: {str(e)}\n{traceback.format_exc()}")
        return jsonify({'success': False, 'message': f'Error interno: {str(e)}'}), 500


@app.route('/importar_excel', methods=['POST'])
def importar_excel():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No se subió archivo'}), 400
            
        file = request.files['file']
        if file.filename.endswith('.xlsx'):
            file.save(EXCEL_PATH)
            return jsonify({'success': True, 'message': 'Datos actualizados desde Excel'})
            
        return jsonify({'success': False, 'error': 'Formato no válido'}), 400
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    
@app.route("/cupo_sombrilla")
def modulo_cupo_sombrilla():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template("cupoSombrillaTemplates/cupoSombrilla.html")


CUPO_SOMBRILLA_FOLDER = r"C:\CreditosConstructor\cupo_sombrilla_files"

@app.route('/cupo_sombrilla/run_script', methods=['POST'])
def run_cupo_sombrilla_script():
    try:
        # Ruta directa según tu estructura real
        script_path = r"C:\CreditosConstructor\Script_Cupo_Sombrilla_V1.py"
        
        # Verificar existencia del script
        if not os.path.exists(script_path):
            return jsonify({
                'success': False,
                'error': f'Script no encontrado en: {script_path}'
            }), 404

        # Crear carpeta de destino si no existe
        os.makedirs(CUPO_SOMBRILLA_FOLDER, exist_ok=True)

        # Ejecutar script
        python_exec = sys.executable
        app.logger.info(f"Ejecutando script: {script_path}")
        
        result = subprocess.run(
            [python_exec, script_path],
            cwd=os.path.dirname(script_path),
            capture_output=True,
            text=True,
            timeout=300
        )

        # Verificar resultados
        if result.returncode != 0:
            error_details = {
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr
            }
            return jsonify({
                'success': False,
                'error': 'Error en ejecución del script',
                'details': error_details
            }), 500

        # Buscar archivos generados
        generated_files = []
        expected_files = [
            'BASE_Sombrilla.xlsx',
            'creditlean.xlsx',
            'cenegar_Saldos.xlsx'
        ]
        
        for filename in expected_files:
            src = os.path.join(os.path.dirname(script_path), filename)
            if os.path.exists(src):
                dest = os.path.join(CUPO_SOMBRILLA_FOLDER, filename)
                shutil.move(src, dest)
                generated_files.append(filename)
            else:
                app.logger.warning(f"Archivo esperado no generado: {filename}")

        if not generated_files:
            return jsonify({
                'success': False,
                'error': 'No se generaron archivos de salida'
            }), 500

        return jsonify({
            'success': True,
            'message': 'Script ejecutado correctamente',
            'files': generated_files
        })

    except subprocess.TimeoutExpired:
        return jsonify({
            'success': False,
            'error': 'Tiempo de ejecución excedido (5 minutos)'
        }), 500
        
    except Exception as e:
        error_trace = traceback.format_exc()
        app.logger.error(f"Error inesperado: {str(e)}\n{error_trace}")
        return jsonify({
            'success': False,
            'error': f'Error interno: {str(e)}',
            'trace': error_trace
        }), 500
    
@app.route('/cupo_sombrilla/process_step2', methods=['POST'])
def process_step2():
    try:
        cenegar_file = request.files['cenegar_file']
        if not cenegar_file:
            return jsonify({'success': False, 'error': 'No se subió archivo cenegar_saldos'}), 400
        
        # Guardar archivo
        cenegar_path = os.path.join(CUPO_SOMBRILLA_FOLDER, 'cenegar_saldos_processed.xlsx')
        cenegar_file.save(cenegar_path)
        
        # Procesamiento adicional (ejemplo)
        df = pd.read_excel(cenegar_path)
        
        # 1. Convertir columna C a numérico
        df['Columna_C'] = pd.to_numeric(df['Columna_C'], errors='coerce')
        
        # 2. Insertar columna para identificar crédito constructor
        df.insert(loc=3, column='Tipo_Credito', value='')
        
        # 3. Cruzar con archivo de saldos (simulado)
        # En producción esto sería una operación real con otro archivo
        df['Es_Constructor'] = df.apply(lambda row: 'ND' 
                                        if row['Columna_C'] > 1000000 
                                        else 'Constructor', axis=1)
        
        # 4. Filtrar solo ND (deuda corporativa)
        df = df[df['Es_Constructor'] == 'ND']
        
        # Guardar resultado
        df.to_excel(cenegar_path, index=False)
        
        return jsonify({'success': True, 'message': 'Paso 2 procesado correctamente'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

# Ruta para procesar el Paso 3 (ahora incluye la generación completa)
@app.route('/cupo_sombrilla/process_step3', methods=['POST'])
def process_step3():
    try:
        # Obtener archivos subidos en pasos anteriores
        base_path = os.path.join(CUPO_SOMBRILLA_FOLDER, 'BASE_Sombrilla_processed.xlsx')
        control_path = os.path.join(CUPO_SOMBRILLA_FOLDER, 'cenegar_saldos_processed.xlsx')
        
        if not os.path.exists(base_path) or not os.path.exists(control_path):
            return jsonify({
                'success': False, 
                'error': 'Faltan archivos procesados de pasos anteriores'
            }), 400
        
        # Cargar datos procesados
        df_base_codigo = pd.read_excel(base_path)
        df_base_control = pd.read_excel(control_path)
        
        # Generar archivo final
        result_path = os.path.join(CUPO_SOMBRILLA_FOLDER, 'CUPO_SOMBRILLA_AUTOMATIZADO_V2.xlsx')
        generar_cupo_sombrilla(df_base_codigo, df_base_control, result_path)
        
        return jsonify({
            'success': True, 
            'message': 'Archivo de Cupo Sombrilla generado correctamente',
            'file': 'CUPO_SOMBRILLA_AUTOMATIZADO_V2.xlsx'
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/cupo_sombrilla/download/<filename>', methods=['GET'])
def download_cupo_file(filename):
    try:
        return send_from_directory(
            directory=CUPO_SOMBRILLA_FOLDER,
            path=filename,
            as_attachment=True
        )
    except Exception as e:
        return str(e), 404    

if __name__ == "__main__":
     app.run(host="0.0.0.0", port=5000)
