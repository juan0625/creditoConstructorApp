import openpyxl 
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file, send_from_directory
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
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'message': 'Datos inválidos'}), 400

        proyectos = data.get('proyectos', [])
        if not proyectos:
            return jsonify({'success': False, 'message': 'No hay proyectos para exportar'}), 400

        # Validar campos obligatorios
        campos_obligatorios = ['id_proyecto', 'nombre_proyecto', 'fecha_creacion']
        for proyecto in proyectos:
            if not all(key in proyecto for key in campos_obligatorios):
                return jsonify({'success': False, 'message': f'Falta campo obligatorio en proyecto {proyecto.get("id_proyecto")}'}), 400

            # Convertir condiciones a lista
            if 'condiciones_aprobacion' in proyecto and isinstance(proyecto['condiciones_aprobacion'], str):
                proyecto['condiciones_aprobacion'] = proyecto['condiciones_aprobacion'].split('; ')

        # Crear DataFrame dinámico
        df = pd.DataFrame(proyectos).fillna('')

        # Crear directorio si no existe
        if not os.path.exists(EXPORTAR_RUTA):
            os.makedirs(EXPORTAR_RUTA)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Proyectos')
            worksheet = writer.sheets['Proyectos']
            for idx, col in enumerate(df.columns):
                max_len = max(df[col].astype(str).map(len).max(), len(col)) + 2
                worksheet.set_column(idx, idx, max_len)

        server_path = os.path.join(EXPORTAR_RUTA, 'Base_principal_proyectos.xlsx')
        with open(server_path, 'wb') as f:
            f.write(output.getvalue())

        return jsonify({'success': True, 'message': 'Archivo exportado correctamente'}), 200

    except Exception as e:
        print(f"Error en exportar_excel: {str(e)}\n{traceback.format_exc()}")
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
