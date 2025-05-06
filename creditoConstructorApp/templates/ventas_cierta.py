import os
import pandas as pd
from flask import Flask, request, jsonify, render_template, send_file
from werkzeug.utils import secure_filename
import pyodbc
import socket
from sqlalchemy import create_engine, text
from datetime import datetime
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.worksheet.datavalidation import DataValidation
import xlwings as xw
import time

# Configuración de la base de datos
UPLOAD_FOLDER = os.path.join(os.getcwd(), "uploads")  # Ruta absoluta desde el directorio actual
ALLOWED_EXTENSIONS = {'xlsx'}

# Configuración de Flask
app = Flask(__name__)
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Crea la carpeta si no existe
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Verificar si la carpeta 'uploads' existe o se creó correctamente
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
    print(f"Carpeta {UPLOAD_FOLDER} creada exitosamente.")
else:
    print(f"Carpeta {UPLOAD_FOLDER} ya existe.")

# Función para determinar el ambiente (P o C) en base al servidor
def capturar_ambiente():
    # Obtener el nombre del servidor
    server_name = socket.gethostname()
    # Determinar el ambiente (P para Producción, C para Cualquiera que no sea producción)
    ambiente = 'P' if 'bancolombia' in server_name else 'C'
    return server_name, ambiente

# Capturar servidor y ambiente
SERVIDOR, AMBIENTE = capturar_ambiente()
print(f"Conexión al servidor: {SERVIDOR} en ambiente: {AMBIENTE}")    

# def as_pandas(cursor):
#     names = [metadata[0] for metadata in cursor.description]
#     return pd.DataFrame([dict(zip(names, row)) for row in cursor], columns=names)

# Extensiones permitidas para el archivo
ALLOWED_EXTENSIONS = {'xlsx', 'xls'}

# Función para verificar si el archivo tiene una extensión permitida
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Función para obtener la conexión a la base de datos
def obtener_conexion():
    try:
        # Cadena de conexión con parámetros en un solo string
        conn_str = (
            "DSN=IMPALA-PROD;"
            "MemoryLimit=20G"
        )
        
        # Establecer conexión
        conn = pyodbc.connect(conn_str, autocommit=True)
        print("Conexión exitosa.")
        return conn
        
    except Exception as e:
        print(f"Error al conectar con la base de datos: {str(e)}")
        raise


# Función para ejecutar consultas SQL y devolver resultados como DataFrame
def obtener_datos_bd(consulta):
    try:
        cn = obtener_conexion()  # Conectar a la base de datos
        df = pd.read_sql(consulta, cn)  # Ejecutar la consulta y cargar los datos en un DataFrame
        cn.close()  # Cerrar la conexión
        return df
    except Exception as e:
        print(f"Error al obtener datos: {str(e)}")
        raise  # Relanzamos el error para que pueda ser capturado en otro nivel si es necesario


# Función para verificar las extensiones permitidas de los archivos
def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'xls', 'xlsx'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Función para procesar el archivo Excel y generar las tablas dinámicas    
def procesar_excel(filepath, output_path):
    try:

        # 1. Leer archivo Excel
        hoja_df = pd.read_excel(filepath, sheet_name='Hoja1')
        hoja_df.columns = hoja_df.columns.str.strip().str.lower()
        
        # 2. Validar y limpiar datos
        hoja_df = hoja_df.dropna(subset=['num_doc', 'tid'])
        hoja_df['num_doc'] = hoja_df['num_doc'].astype('int64')
        hoja_df['tid'] = hoja_df['tid'].astype('int16')
        hoja_df['nombre_del_proyecto'] = hoja_df['nombre_del_proyecto'].fillna('SIN_PROYECTO').str.replace("'", "''")

        # 3. Conexión a Impala
        conn = obtener_conexion()
        cursor = conn.cursor()

        # 4. Crear tabla temporal
        cursor.execute("DROP TABLE IF EXISTS proceso.clientes_ventas_ciertas_vt_tmp PURGE")
        cursor.execute("""
            CREATE TABLE proceso.clientes_ventas_ciertas_vt_tmp (
                num_doc BIGINT,
                tipo_doc SMALLINT,
                nombre_del_proyecto STRING
            ) STORED AS PARQUET
        """)

        # 5. Insertar datos con formato correcto
        for row in hoja_df.itertuples():
            try:
                insert_sql = f"""
                    INSERT INTO proceso.clientes_ventas_ciertas_vt_tmp 
                    VALUES (
                        {row.num_doc},  -- BIGINT
                        {row.tid},      -- SMALLINT
                        '{row.nombre_del_proyecto}'  -- STRING escapado
                    )
                """
                cursor.execute(insert_sql)
            except Exception as e:
                print(f"Error insertando fila {row.Index}: {str(e)}")
                continue
        
        conn.commit()

        # Leer datos de Excel en formato de lista
        values = hoja_df[['num_doc', 'tid', 'nombre_del_proyecto']].values.tolist()

        # Construir consulta principal según lógica SAS
        query = f"""
        WITH valores_temp AS (
            SELECT 
                CAST({values[0][0]} AS BIGINT) AS num_doc, 
                CAST({values[0][1]} AS SMALLINT) AS tipo_doc, 
                '{values[0][2]}' AS nombre_del_proyecto
            UNION ALL
            {" UNION ALL ".join([f"SELECT CAST({v[0]} AS BIGINT), CAST({v[1]} AS SMALLINT), '{v[2]}'" for v in values[1:]])}
        ),

        -- 1. Obtener última partición de Segmentación Afectación
        ultima_particion_sa AS (
            SELECT 
                MAX(ingestion_year) AS max_year,
                MAX(ingestion_month) AS max_month,
                MAX(ingestion_day) AS max_day
            FROM resultados_cap_analit_y_gob_de_inf.co19_segmentacion_afectacion
        ),

        seg_af AS (
            SELECT 
                CAST(num_doc AS BIGINT) AS num_doc,
                CAST(tipo_doc AS SMALLINT) AS tipo_doc,
                COALESCE(segmento_afectacion, 'DESCONOCIDO') AS segmento_afectacion
            FROM resultados_cap_analit_y_gob_de_inf.co19_segmentacion_afectacion
            WHERE 
                ingestion_year = (SELECT max_year FROM ultima_particion_sa)
                AND ingestion_month = (SELECT max_month FROM ultima_particion_sa)
                AND ingestion_day = (SELECT max_day FROM ultima_particion_sa)
        ),

        -- 2. Obtener última partición de Ocupación
        ultima_particion_ocup AS (
            SELECT 
                MAX(ingestion_year) AS max_year,
                MAX(ingestion_month) AS max_month,
                MAX(ingestion_day) AS max_day
            FROM resultados_clientes_personas_y_pymes.perfilacion_preaprobados
        ),

        ocup AS (
            SELECT 
                CAST(id AS BIGINT) AS num_doc,
                CAST(tipo_id AS SMALLINT) AS tipo_doc,
                CASE 
                    WHEN UPPER(TRIM(ocupacion)) IN ('EMPLEADO', 'ESTUDIANTE', 'JUBILADO') THEN 'Asalariado'
                    WHEN UPPER(TRIM(ocupacion)) IN ('AGRICULTOR', 'AMA DE CASA', 'COMERCIANTE') THEN 'Independientes'
                    ELSE 'DESCONOCIDO'
                END AS ocupacion_personas
            FROM resultados_clientes_personas_y_pymes.perfilacion_preaprobados
            WHERE 
                ingestion_year = (SELECT max_year FROM ultima_particion_ocup)
                AND ingestion_month = (SELECT max_month FROM ultima_particion_ocup)
                AND ingestion_day = (SELECT max_day FROM ultima_particion_ocup)
        ),

        -- 3. Obtener datos de Afectación PN
        ultima_particion_afectacion AS (
            SELECT 
                MAX(ingestion_year) AS max_year,
                MAX(ingestion_month) AS max_month,
                MAX(ingestion_day) AS max_day
            FROM resultados_riesgos.modelo_afectacion_pn
        ),

        afectacion_pn AS (
            SELECT 
                CAST(num_doc AS BIGINT) AS num_doc,
                CAST(tipo_doc AS SMALLINT) AS tipo_doc,
                ctrl_terc,
                fecha_corte,
                CASE
                    WHEN cluster_final BETWEEN 1 AND 9 THEN 
                        CASE cluster_final
                            WHEN 1 THEN 'Muy Baja'
                            WHEN 2 THEN 'Baja'
                            WHEN 3 THEN 'Media Baja'
                            WHEN 4 THEN 'Media'
                            WHEN 5 THEN 'Media Alta'
                            WHEN 6 THEN 'Alta'
                            WHEN 7 THEN 'Muy Alta'
                            WHEN 8 THEN 'Extrema Alta'
                            WHEN 9 THEN 'Indeterminados'
                        END
                    ELSE 'DESCONOCIDO'
                END AS nivel_afectacion
            FROM resultados_riesgos.modelo_afectacion_pn
            WHERE 
                ingestion_year = (SELECT max_year FROM ultima_particion_afectacion)
                AND ingestion_month = (SELECT max_month FROM ultima_particion_afectacion)
                AND ingestion_day = (SELECT max_day FROM ultima_particion_afectacion)
        ),

        -- 4. Generar fecha de referencia (Versión Corregida)
         fecha_referencia AS (
            SELECT 
                CONCAT(
                    CAST(YEAR(ADD_MONTHS(CURRENT_DATE(), -1)) AS STRING),
                    LPAD(CAST(MONTH(ADD_MONTHS(CURRENT_DATE(), -1)) AS STRING), 2, '0')
                ) AS fecha_corte_formato
        )

        -- 5. Consulta final
        SELECT 
            vt.num_doc,
            vt.tipo_doc,
            vt.nombre_del_proyecto,
            COALESCE(sa.segmento_afectacion, 'NO_ENCONTRADO') AS segmento_afectacion,
            COALESCE(oc.ocupacion_personas, 'NO_ENCONTRADO') AS ocupacion,
            COALESCE(ap.ctrl_terc, 'NO_REGISTRA') AS tipo_cliente,
            COALESCE(ap.nivel_afectacion, 'NO_DISPONIBLE') AS nivel_afectacion,
            CASE
                WHEN ap.ctrl_terc IN ('CLIENTE', 'CLIENTE SOCIAL', 'NEQUI') 
                    THEN 'Cliente Bancolombia'
                ELSE 'No Cliente'
            END AS caracteristica,
            COALESCE(fr.fecha_corte_formato, '0') AS fecha_corte
        FROM valores_temp vt
        LEFT JOIN seg_af sa ON vt.num_doc = sa.num_doc AND vt.tipo_doc = sa.tipo_doc
        LEFT JOIN ocup oc ON vt.num_doc = oc.num_doc AND vt.tipo_doc = oc.tipo_doc
        LEFT JOIN afectacion_pn ap ON vt.num_doc = ap.num_doc AND vt.tipo_doc = ap.tipo_doc
        CROSS JOIN fecha_referencia fr;
        """

        # Obtener datos de la consulta
        datos_bd = pd.read_sql(query, conn)
        conn.close()

        # Normalizar columnas de datos_bd
        datos_bd.columns = datos_bd.columns.str.strip().str.lower()

        # Filtrar y seleccionar las columnas necesarias
        df_ventas = datos_bd[['num_doc', 'tipo_doc', 'nombre_del_proyecto', 'segmento_afectacion', 
                              'ocupacion', 'tipo_cliente', 'nivel_afectacion', 'caracteristica', 'fecha_corte']]

        # Procesar datos para crear la tabla dinámica principal
        datos_clientes = []
        for _, row in hoja_df.iterrows():
            num_doc = row['num_doc']
            tid = row['tid']
            nombre_del_proyecto = row['nombre_del_proyecto']

            cliente_data = df_ventas[(df_ventas['num_doc'] == num_doc) & (df_ventas['tipo_doc'] == tid)].iloc[0]

            datos_clientes.append({
                'num_doc': num_doc,
                'tipo_doc': tid,
                'nombre_del_proyecto': nombre_del_proyecto,
                'segmento': cliente_data['segmento_afectacion'],
                'ocupacion': cliente_data['ocupacion'],
                'tipo_cliente': cliente_data['tipo_cliente'],
                'nivel_afectacion': cliente_data['nivel_afectacion'],
                'caracteristica': cliente_data['caracteristica'],
                'fecha_corte': cliente_data['fecha_corte'],
            })

        # Crear la tabla dinámica principal en un DataFrame
        tabla_dinamica_df = pd.DataFrame(datos_clientes)
        
        # Filtrar el DataFrame por el proyecto seleccionado
        proyectos_unicos = tabla_dinamica_df['nombre_del_proyecto'].unique()
      
        #Aplicación excel
         # Crear la aplicación de Excel
        with xw.App(visible=False) as app:
            wb = app.books.add()
            
            # Crear la hoja principal de clientes
            ws_clientes = wb.sheets[0]
            ws_clientes.name = 'clientes_v_c_afect'
            
            # Estilo de la hoja de clientes
            ws_clientes.range('A1').options(index=False, header=True).value = tabla_dinamica_df

            # Estilos para el encabezado de la tabla (A1:I1)
            ws_clientes.range('A1:I1').api.Font.Bold = True  # Texto en negrita
            ws_clientes.range('A1:I1').api.Font.Color = 0xFFFFFF  # Color del texto (Blanco)
            ws_clientes.range('A1:I1').api.Interior.Color = 0x4F81BD  # Fondo Azul
            ws_clientes.range('A1:I1').api.Borders.Weight = 2  # Bordes gruesos
            ws_clientes.range('A1:I1').api.Borders.Color = 0x000000  # Bordes negros

            # Aplicar bordes a todas las celdas de la tabla (desde A2 hasta la última fila de datos)
            ultima_fila = len(tabla_dinamica_df) + 1
            ws_clientes.range(f'A2:I{ultima_fila}').api.Borders.Weight = 2  # Bordes en todo el rango de datos
            ws_clientes.range(f'A2:I{ultima_fila}').api.Borders.Color = 0x000000  # Bordes negros

            # Estilo para las celdas de datos (desde A2 hasta la última fila)
            for row in range(2, ultima_fila + 1):  # Desde la fila 2 hasta la última fila de datos
                for col in range(9):  # Desde la columna A hasta la I (9 columnas)
                    col_letter = chr(65 + col)  # Convertir número de columna a letra
                    ws_clientes.range(f'{col_letter}{row}').api.Borders.Weight = 2  # Bordes en cada celda de datos
                    ws_clientes.range(f'{col_letter}{row}').api.Borders.Color = 0x000000  # Bordes negros
                    ws_clientes.range(f'{col_letter}{row}').api.Interior.Color = 0xF9F9F9  # Fondo gris claro en las celdas de datos

            
            # Crear la hoja de Información
            ws_informacion = wb.sheets.add('Información', after=ws_clientes)
            
            # Encabezado principal
            ws_informacion.range('A1').value = "Tablas Dinámicas por Proyecto"
            ws_informacion.range('A1').api.Font.Bold = True
            ws_informacion.range('A1').api.Font.Size = 14
            ws_informacion.range('A1').api.Font.Color = 0xFFFFFF  # Blanco
            ws_informacion.range('A1').api.Interior.Color = 0x4F81BD  # Azul
            ws_informacion.range('A1:G1').merge()
            ws_informacion.range('A1:G1').api.Borders.Weight = 2  # Bordes más gruesos
            
            # Selector de proyectos
            proyectos_unicos = tabla_dinamica_df['nombre_del_proyecto'].unique()
            ws_informacion.range('A2').value = "Seleccione un Proyecto:"
            ws_informacion.range('A2').api.Font.Bold = True
            
            # Lista de proyectos en la columna J
            for i, proyecto in enumerate(proyectos_unicos, start=3):
                ws_informacion.range(f'J{i}').value = proyecto
            
            proyectos_rango = f'J3:J{len(proyectos_unicos) + 2}'

            # Lista de proyectos en la columna J con estilos
            ws_informacion.range('J2').value = "Proyectos"
            ws_informacion.range('J2').api.Font.Bold = True
            ws_informacion.range('J2').api.Interior.Color = 0xC9DAF8  # Azul claro
            ws_informacion.range('J2:J2').api.Borders.Weight = 2  # Bordes en encabezado

            for i, proyecto in enumerate(proyectos_unicos, start=3):
                ws_informacion.range(f'J{i}').value = proyecto
                ws_informacion.range(f'J{i}').api.Borders.Weight = 2  # Bordes en cada celda
                ws_informacion.range(f'J{i}').api.Borders.Color = 0x000000  # Bordes negros
                ws_informacion.range(f'J{i}').api.Interior.Color = 0xF9F9F9  # Fondo gris claro

            
            # Agregar validación de lista desplegable en B2
            validation_range = ws_informacion.range(proyectos_rango).api
            ws_informacion.range('B2').api.Validation.Delete()
            ws_informacion.range('B2').api.Validation.Add(
                Type=3, AlertStyle=1, Operator=1,
                Formula1=f'={validation_range.Address}'
            )
            ws_informacion.range('B2').value = proyectos_unicos[0]
            
            # Recorrer cada categoría y extraer datos
            categorias = [
                ("Características", 'caracteristica'),
                ("Ocupación", 'ocupacion'),
                ("Segmento de Afectación", 'segmento')
            ]
            
            start_row = 4  # Iniciar debajo del selector de proyecto
            total_refs = []  # Para almacenar las referencias de los subtotales
            
            for nombre_tabla, columna in categorias:
                # Título de la tabla
                ws_informacion.range(f'A{start_row}').value = f"{nombre_tabla} del Proyecto:"
                ws_informacion.range(f'A{start_row}').formula = f'="{nombre_tabla} del Proyecto: " & B2'
                ws_informacion.range(f'A{start_row}').api.Font.Bold = True
                ws_informacion.range(f'A{start_row}').api.Interior.Color = 0xCCCCCC
                ws_informacion.range(f'A{start_row}').api.Borders.Weight = 2
                
                # Filtrar y contar las categorías únicas
                tabla_filtrada = tabla_dinamica_df.groupby([columna])['nombre_del_proyecto'].count().reset_index()
                tabla_filtrada = tabla_filtrada.rename(columns={'nombre_del_proyecto': 'Cantidad'})
                
                # Escribir los valores en la hoja
                ws_informacion.range(f'A{start_row + 1}').value = ["Valor", "Cantidad"]
                ws_informacion.range(f'A{start_row + 1}').api.Font.Bold = True
                ws_informacion.range(f'A{start_row + 1}').api.Interior.Color = 0xC9DAF8  # Azul claro
                ws_informacion.range(f'A{start_row + 1}:B{start_row + 1}').api.Borders.Weight = 2  # Bordes en el encabezado
                
                ws_informacion.range(f'A{start_row + 2}').options(index=False, header=False).value = tabla_filtrada.values
                
                # Agregar bordes a la tabla de datos
                ws_informacion.range(f'A{start_row + 2}:B{start_row + len(tabla_filtrada) + 1}').api.Borders.Weight = 2
                
                # Calcular subtotal
                total_fila = start_row + len(tabla_filtrada) + 2
                ws_informacion.range(f'A{total_fila}').value = f"Total {nombre_tabla}"
                ws_informacion.range(f'A{total_fila}').api.Font.Bold = True
                ws_informacion.range(f'A{total_fila}').api.Interior.Color = 0xFFFF99  # Amarillo
                ws_informacion.range(f'A{total_fila}').api.Borders.Weight = 2
                ws_informacion.range(f'B{total_fila}').formula = f'=SUM(B{start_row + 2}:B{total_fila - 1})'
                
                total_refs.append(f'B{total_fila}')
                
                start_row = total_fila + 2  # Avanzar a la siguiente tabla

            # Total General
            ws_informacion.range(f'A{start_row}').value = "Total General"
            ws_informacion.range(f'A{start_row}').api.Font.Bold = True
            ws_informacion.range(f'A{start_row}').api.Interior.Color = 0xD9EAD3  # Verde claro
            ws_informacion.range(f'A{start_row}').api.Borders.Weight = 2
            ws_informacion.range(f'B{start_row}').formula = f'={" + ".join(total_refs)}'
            
            # Aplicar bordes a la celda final
            ws_informacion.range(f'A{start_row}:B{start_row}').api.Borders.Weight = 2


            # Guardar el archivo Excel en el output_path
            wb.save(output_path)
            wb.close()

            # Limpiar tabla temporal
            conn = obtener_conexion()
            cursor = conn.cursor()
            cursor.execute("DROP TABLE IF EXISTS proceso.clientes_ventas_ciertas_vt_tmp PURGE")
            conn.commit()
            conn.close()

            print(f"Archivo procesado y guardado en: {output_path}")
            return "Archivo procesado con éxito", output_path

    except Exception as e:
        print(f"Error al procesar el archivo: {e}")
        return f"Error al procesar el archivo: {e}", None


@app.route('/upload', methods=['POST'])
def subir_archivo():
    if 'file' not in request.files:
        return jsonify({'error': 'No se encontró el archivo en la solicitud.'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No se seleccionó ningún archivo.'}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        output_path = r"Y:/VENTA CIERTA/Clientes_venta_cierta_procesado.xlsx"
        try:
            message, output_file = procesar_excel(filepath, output_path)
            if output_file:
                return jsonify({'message': message, 'output_file': output_file})
            else:
                return jsonify({'error': 'Error al generar el archivo procesado.'}), 500
        except Exception as e:
            return jsonify({'error': f'Error al procesar el archivo: {str(e)}'}), 500

    return jsonify({'error': 'Tipo de archivo no permitido.'}), 400


@app.route('/')
def index():
    return render_template('importar-datos.html')


if __name__ == "__main__":
     app.run(host="0.0.0.0", port=5000)