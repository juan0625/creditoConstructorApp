# -*- coding: utf-8 -*-
"""
Fecha Actualización: Mayo 2025
Area: RC Corp Inmobiliario y Constructor
Objetivo: Cupo Sombrilla

Elementos necesarios: 
    - ODBC Impala
    - Usuario Landing Zone
    - Acceso a zona LZ datos crudos
    - Acceso a la carpeta de la División de Crédito Constructor

Insumo Requeridos: 
    - Base Enroque: 'Consolidado_Historico_Enroque-Cuadro'
    - IT: 'Base Informe Técnico'
    - Control Constructor: 'Histórico_control'
"""

import pandas as pd
import pyodbc
from datetime import datetime
import calendar
import os

# =============================================================================
# CONFIGURACIÓN INICIAL
# =============================================================================
print("="*80)
print("INICIANDO PROCESO DE CUPO SOMBRILLA")
print("="*80)

# Configuración de rutas y fechas
ruta_informes = r"C:\Codigo Python\Cupo Sombrilla\AUTOMATIZACIÓN CUPO SOMBRILLA\INFORMES"
now = datetime.now()
year_v, mes_v = (now.year, now.month - 2) if now.month > 2 else (now.year - 1, 12 + now.month - 2)
ultimo_dia_mes_anterior = calendar.monthrange(year_v, mes_v)[1]

# Crear directorio si no existe
os.makedirs(ruta_informes, exist_ok=True)

# =============================================================================
# FUNCIONES AUXILIARES
# =============================================================================
def conectar_impala():
    """Establece conexión con Impala"""
    print("\nConectando a Impala...")
    try:
        conn = pyodbc.connect("DSN=IMPALA_PROD", autocommit=True)
        print("✅ Conexión exitosa a Impala")
        return conn
    except pyodbc.Error as ex:
        print(f"❌ Error en conexión Impala: {ex}")
        return None

def ejecutar_consulta(conn, query):
    """Ejecuta consulta SQL y devuelve DataFrame"""
    try:
        cursor = conn.cursor()
        cursor.execute(query)
        column_names = [col[0] for col in cursor.description]
        df = pd.DataFrame.from_records(cursor.fetchall(), columns=column_names)
        print(f"✅ Consulta ejecutada - Registros obtenidos: {len(df)}")
        return df
    except Exception as e:
        print(f"❌ Error en consulta SQL: {e}")
        return pd.DataFrame()

# =============================================================================
# PROCESAMIENTO DE DATOS LOCALES
# =============================================================================
print("\n" + "="*80)
print("PROCESANDO ARCHIVOS LOCALES")
print("="*80)

# 1. Procesar Enroque
print("\nLeyendo base Enroque...")
df_enroque = pd.read_excel(
    r"Z:\AUTOMATIZACION ENROQUE\INSUMOS TABLERO\Consolidado_Historico_Enroque-Cuadro.xlsx",
    sheet_name='Sheet1'
)
df_enroque.columns = df_enroque.columns.str.lower().str.replace(" ", "_")
df_enroque = df_enroque[['nit', 'sociedad', 'radicado', 'proyecto', 'grupo', 
                         'creditosaprobados', 'tipodecredito', 'saldoactual', 
                         'valorentregado', 'valorentregar', 'fecha_historico']]
print("✅ Base Enroque procesada")

# 2. Procesar Informe Técnico
print("\nLeyendo Informe Técnico...")
df_it = pd.read_excel(
    r"Z:\FORMATOS CREDITOS CONSTRUCTORES\PLANOS\Base Informe Técnico.xlsx",
    sheet_name='base'
)
df_it.columns = df_it.columns.str.lower().str.replace(" ", "_")
df_it.rename(columns={'radicado_crédito_constructor': 'radicado'}, inplace=True)
print("✅ Informe Técnico procesado")

# 3. Procesar Control Constructor
print("\nLeyendo Control Constructor...")
df_control = pd.read_excel(
    r"Z:\AUTOMATIZACIÓN CONTROLES\INSUMOS TABLERO\Histórico_control.xlsx",
    sheet_name='Sheet1'
)
df_control.columns = df_control.columns.str.lower().str.replace(" ", "_")
df_control.rename(columns={'radicado': 'radicado'}, inplace=True)
print("✅ Control Constructor procesado")

# 4. Procesar Llaves
print("\nLeyendo base de llaves...")
df_llaves = pd.read_excel(
    os.path.join(ruta_informes, 'BASE_llave.xlsx'),
    sheet_name='Llaves'
)
print("✅ Base de llaves procesada")

# 5. Fusionar datasets
print("\nFusionando datasets locales...")
df_merged = (
    df_enroque
    .merge(df_it, on='radicado', how='left')
    .merge(df_control, on='radicado', how='left')
    .merge(df_llaves[['grupo', 'Nit_Constructor']], on='grupo', how='left')
)

df_merged['Nit_Constructor'] = df_merged['Nit_Constructor'].fillna(0)
df_merged['inmuebles_totales'] = df_merged['numero_inmuebles_por_vender'] + df_merged['numero_inmuebles_vendidos']
print("✅ Datasets locales fusionados")

# =============================================================================
# CONSULTAS A BASES DE DATOS
# =============================================================================
print("\n" + "="*80)
print("CONSULTANDO BASES DE DATOS REMOTAS")
print("="*80)

# Obtener lista de NITs únicos
nits = df_merged['Nit_Constructor'].dropna().unique()
nits_str = ",".join(map(str, nits))
print(f"\nNITs a consultar: {len(nits)}")

# 1. Consulta a CreditLens
print("\nConsultando CreditLens...")
conn = conectar_impala()
if conn:
    query_creditlens = f"""
    WITH EEFF AS (
        SELECT CAST(numeroid AS BIGINT) AS numeroid,
               totaldeudacp AS Deuda_Cp,
               totaldeudalp AS Deuda_LP,
               totalassets AS Activo_Total,
               totalnetworth AS Patrimonio,
               statementdate AS Fecha,
               endeudsinvalorperc AS Endeudamientosinvaloriza,
               coberturainteresveces AS Ebitdasobreintereses,
               pasivofinancebitdaveces AS Pasivofinancierosobreebitda,
               acctspayabledays AS Rotacionproveedoresdias,
               grsacctsrecdays AS Rotacioncarteradias,
               totalinvdays AS Rotacioninventariodias,
               totalinventory AS Totalinventario,
               endeudfinperc AS Endeudamientofinanciero,
               auditmethod AS Auditor,
               CAST(CONCAT(STRLEFT(statementdate,4), SUBSTR(statementdate,6,2)) AS BIGINT) AS statementdate_corte
        FROM S_Apoyo_Financiero.CREDITLENS_CRDLZ_UPHISTBCOLCORP
        WHERE YEAR = YEAR(DATE_SUB(NOW(), 1))
          AND ingestion_MONTH = MONTH(DATE_SUB(NOW(), 1))
          AND ingestion_DAY = DAY(DATE_SUB(NOW(), 1))
          AND LOCATE('SIMULACIÓN – ', TRIM(UPPER(customername))) = 0
          AND CAST(numeroid AS BIGINT) IN ({nits_str})
    )
    SELECT * FROM (
        SELECT *, ROW_NUMBER() OVER (PARTITION BY numeroid ORDER BY statementdate_corte DESC) AS rn
        FROM EEFF
    ) sub WHERE rn = 1;
    """
    
    df_creditlens = ejecutar_consulta(conn, query_creditlens)
    
    if not df_creditlens.empty:
        df_creditlens.rename(columns={'numeroid': 'Nit_Constructor'}, inplace=True)
        df_creditlens['pasivo_total'] = df_creditlens['Activo_Total'] - df_creditlens['Patrimonio']
        df_creditlens['deuda_Total'] = df_creditlens['Deuda_Cp'] + df_creditlens['Deuda_Lp']
        df_creditlens = df_creditlens[df_creditlens['Auditor'] == "Revisor"]
        
        # Fusionar con datos locales
        df_merged = df_merged.merge(df_creditlens, on='Nit_Constructor', how='left')
        print("✅ Datos de CreditLens fusionados")
    else:
        print("⚠️ No se encontraron datos en CreditLens")
else:
    print("⚠️ Saltando consulta a CreditLens por error de conexión")

# 2. Consulta a CENIEGAR
print("\nConsultando CENIEGAR...")
if conn:
    query_ceniegar = f"""
    SELECT id,
           IF(ofcenie=470,'Leasing','Banco') AS linea,
           obl,
           vdesem,
           sk,
           (CASE califi
                WHEN 'A' THEN 'C1'
                WHEN 'B' THEN 'C2'
                WHEN 'C' THEN 'C3'
                WHEN 'D' THEN 'C4'
                WHEN 'E' THEN 'C5'
                WHEN 'F' THEN 'C6'
                WHEN 'G' THEN 'C7'
                WHEN 'H' THEN 'C8'
                WHEN 'N' THEN 'C9'
                WHEN 'O' THEN 'C10'
                WHEN 'P' THEN 'C11'
                WHEN 'Q' THEN 'C12'
                WHEN 'R' THEN 'C13'
                WHEN 'S' THEN 'C14'
                WHEN 'T' THEN 'C15'
                WHEN 'U' THEN 'C16'
                WHEN 'V' THEN 'C17'
                WHEN 'W' THEN 'C18'
                WHEN 'X' THEN 'C19'        
            END) AS calificacion,
           pitotal,
           pktotal,
           altmora 
    FROM resultados_riesgos.ceniegarc_lz
    WHERE ingestion_year = {year_v} 
      AND ingestion_month = {mes_v}
      AND CAST(id AS BIGINT) IN ({nits_str});
    """
    
    df_ceniegar = ejecutar_consulta(conn, query_ceniegar)
    conn.close()
    
    if not df_ceniegar.empty:
        # Guardar resultados de CENIEGAR
        ruta_ceniegar = os.path.join(ruta_informes, 'cenegar_Saldos.xlsx')
        df_ceniegar.to_excel(ruta_ceniegar, index=False)
        print(f"✅ Resultados de CENIEGAR guardados en: {ruta_ceniegar}")
    else:
        print("⚠️ No se encontraron datos en CENIEGAR")
else:
    print("⚠️ Saltando consulta a CENIEGAR por error de conexión")

# =============================================================================
# PROCESAMIENTO FINAL Y GUARDADO
# =============================================================================
print("\n" + "="*80)
print("PROCESAMIENTO FINAL")
print("="*80)

# Seleccionar y ordenar columnas finales
print("\nPreparando dataset final...")
columnas_finales = [
    'Nit_Constructor', 'radicado', 'sociedad', 'proyecto', 'grupo', 
    'creditosaprobados', 'tipodecredito', 'saldoactual', 'valorentregado',
    'valorentregar', 'fecha_historico', 'municipio_', 'costo_urbanismo',
    'costo_directos', 'costo_indirectos', 'honorarios', 'costo_total',
    'costos_financiables', 'credito_constructor', 'credito_preoperativo',
    'credito_lote', 'tipo_fiducia', 'mes_inicio_obra', 'avance_obra_meses',
    'numero_inmuebles_por_vender', 'numero_inmuebles_vendidos', 'inmuebles_totales',
    'valor_total_ventas', 'programacion_actual', 'activo_total', 'patrimonio',
    'pasivo_total', 'meses_prorrogados', 'vencimiento_credito', 'avance_obra',
    'endeudamientosinvaloriza', 'ebitdasobreintereses', 'pasivofinancierosobreebitda',
    'rotacionproveedoresdias', 'rotacioninventariodias', 'rotacioncarteradias',
    'totalinventario', 'fecha', 'endeudamientofinanciero', 'auditor',
    'fecha__inicio_obra_', 'total_unidades', 'meses_programación', 
    'total_ventas_esperadas', 'unidades_por_vender', 'deuda_cp', 'deuda_lp', 'deuda_Total'
]

df_final = df_merged[columnas_finales]

# Guardar resultado final
ruta_final = os.path.join(ruta_informes, 'BASE_Sombrilla.xlsx')
df_final.to_excel(ruta_final, index=False)
print(f"✅ Dataset final guardado en: {ruta_final}")
print(f"📊 Total de registros procesados: {len(df_final)}")

# =============================================================================
# FIN DEL PROCESO
# =============================================================================
print("\n" + "="*80)
print("PROCESO COMPLETADO EXITOSAMENTE")
print("="*80)