"""
Fecha Actualizaci�n: Mayo 2025
Area: RC Corp Inmobiliario y Constructor
Objetivo: Cupo Sombrilla


Elementos necesarios: 
    - ODBC Impala
    - Usuario Landing Zone
    - Acceso a zona LZ datos crudos
    - Acceso a la carpeta de la Divisi�n de Cr�dito Constructor

Insumo Requeridos: 
    - Base Enroque: 'Consolidado_Historico_Enroque-Cuadro'
    - IT: 'Base Informe T�cnico'
    - Control Constructor: 'Hist�rico_control'
- 

Tablas LZ:
    - S_Apoyo_Financiero.CREDITLENS_CRDLZ_UPHISTBCOLCORP
    - resultados_riesgos.ceniegarc_lz
"""


import pandas as pd
from pandas import ExcelWriter
from collections import OrderedDict
import pyodbc
from datetime import datetime, timedelta
from datetime import date
import calendar
       



# Obtener la fecha actual
now = datetime.now()
        
# Calcular el a�o y mes del mes anterior
year_v, mes_v = divmod(now.month - 2, 12)
year_v += now.year - 1 if year_v < 0 else now.year
mes_v += 1
         
# Obtener la cantidad de d�as en el mes anterior
ultimo_dia_mes_anterior = calendar.monthrange(year_v, mes_v)[1]



#Ruta donde se van a guardar los archivos
ruta_informes = "C:\Codigo Python\Cupo Sombrilla\AUTOMATIZACI�N CUPO SOMBRILLA\INFORMES"

# SE CONECTA CON ENRROQUE PARA LA CAPTURAR LOS DATOS"
filePath = "Z:\AUTOMATIZACION ENROQUE\INSUMOS TABLERO\Consolidado_Historico_Enroque-Cuadro.xlsx"

 #Definiendo las hojas
df = pd.read_excel(filePath, sheet_name='Sheet1')
df.columns= df.columns.str.lower().str.replace(" ","_")
df2 = df[['nit','sociedad', 'radicado','proyecto','grupo','creditosaprobados','tipodecredito','saldoactual','valorentregado','valorentregar','fecha_historico']]

print("\n Conectando a la base consolidada del Enroque")

df2.to_excel(ruta_informes + r'\BASE_Sombrilla.xlsx', index = False)

print("\n Finaliz� la conexi�n al enroque")

# SE CONECTA CON INFORME TECNICO CON BUSQUEDA POR RADICADO
filePath2 = "Z:\FORMATOS CREDITOS CONSTRUCTORES\PLANOS\Base Informe T�cnico.xlsx"

print("Se ley� la base de informe t�cnico")

# Definiendo las hojas
df3 = pd.read_excel(filePath2, sheet_name='base')
df3.columns= df3.columns.str.lower().str.replace(" ","_")

#Sobre escibre el nombre del campo para unirlo con la otra tabla que tiene nombre radicado en el campo
df3.rename(columns = {'radicado_cr�dito_constructor':'radicado'}, inplace = True)

#Se une las tablas con respecto al atributo radicado
df4 = pd.merge(df2, df3[['radicado','municipio_','costo_urbanismo','costo_directos','costo_indirectos','honorarios','costo_total','costos_financiables',
                         'credito_constructor','credito_preoperativo','credito_lote','tipo_fiducia','fecha__inicio_obra_','total_unidades','meses_programaci�n','total_ventas_esperadas',
                         'unidades_por_vender']],how="left")

#Se pasan los datos a excel
df4.to_excel(ruta_informes + r'\BASE_Sombrilla.xlsx', index = False)

print("\n Termin� consulta a Informe T�cnico")

# SE CONECTA CON CONTROL CON BUSQUEDA POR RADICADO
filePath3 =  "Z:\AUTOMATIZACI�N CONTROLES\INSUMOS TABLERO\Hist�rico_control.xlsx"

print("Se ley� el Control con �xito")

# Definiendo las hojas
df5 = pd.read_excel(filePath3, sheet_name='Sheet1')
df5.columns= df5.columns.str.lower().str.replace(" ","_")

#Sobre escibre el nombre del campo para unirlo con la otra tabla que tiene nombre radicado en el campo
df5.rename(columns = {'RADICADO':'radicado'}, inplace = True)

#Se une las tablas con respecto al atributo radicado
df6 = pd.merge(df4, df5[['radicado','mes_inicio_obra','avance_obra_meses','numero_inmuebles_por_vender','numero_inmuebles_vendidos','valor_total_ventas',
                         'programacion_actual','meses_prorrogados','vencimiento_credito','avance_obra']],how="left")
df6['inmuebles_totales'] = df6['numero_inmuebles_por_vender']+df6['numero_inmuebles_vendidos']

#Se pasan los datos a excel
df6.to_excel(ruta_informes + r'\BASE_Sombrilla.xlsx', index = False)

print("\n Termin� la consulta al Control")


#SE CONECTA CON EL NIT PARA LA CONSULTA DE CREDITLEANS

filePath4 = ruta_informes + r'\BASE_llave.xlsx'

df7 = pd.read_excel(filePath4, sheet_name='Llaves')
df8 = pd.merge(df6, df7 [['grupo','Nit_Constructor']],how="left")
df8['Nit_Constructor'] = df8['Nit_Constructor'].fillna(0)

df8.to_excel(ruta_informes + r'\BASE_Sombrilla.xlsx', index = False)

#SE CONECTA CON CREDILEANS EEFF SACAR ACTIVO - PASIVO - PATRIMONIO

print("Conectando a Impala")

CONN_STR = "DSN=IMPALA_PROD" 

def as_pandas(cursor):
    names = [metadata[0] for metadata in cursor.description]
    return pd.DataFrame([dict(zip(names, row)) for row in cursor], columns=names)

try:
    cn = pyodbc.connect(CONN_STR, autocommit = True )
    print("Conexion Exitosa")
except pyodbc.Error as ex:
    print(ex)

now = datetime.now()
ano = now.strftime("%Y")
mes = now.strftime("%m")
dia = now.strftime("%d")

filePath5 = ruta_informes + r'\BASE_Sombrilla.xlsx'

df9 = pd.read_excel(filePath5, sheet_name='Sheet1')
column_name="Nit_Constructor"
mylist = df9[column_name].tolist()
mylist=list(set(mylist))
cadena=str(mylist[0])

for i in range(1,len(mylist)):
    cadena=cadena+', '+str(mylist[i])

print("concatenaci�n de informe")

query_str = """WITH
EEFF AS (
SELECT  cast(numeroid as bigint) as numeroid,
        totaldeudacp as Deuda_Cp,
        totaldeudalp as Deuda_LP,
        totalassets as Activo_Total,
        totalnetworth as Patrimonio,
        statementdate as Fecha,
        endeudsinvalorperc as Endeudamientosinvaloriza,
        coberturainteresveces as Ebitdasobreintereses,
        pasivofinancebitdaveces as Pasivofinancierosobreebitda,
        acctspayabledays as Rotacionproveedoresdias,
        grsacctsrecdays as Rotacioncarteradias,
        totalinvdays as Rotacioninventariodias,
        totalinventory as Totalinventario,
        endeudfinperc as Endeudamientofinanciero,
        auditmethod as Auditor,
        CAST(concat(strleft(statementdate,4),substr(statementdate,6,2)) AS BIGINT) AS statementdate_corte
FROM S_Apoyo_Financiero.CREDITLENS_CRDLZ_UPHISTBCOLCORP
WHERE YEAR = YEAR(DATE_SUB(NOW(), 1))  AND ingestion_MONTH = MONTH(DATE_SUB(NOW(), 1)) AND ingestion_DAY = DAY(DATE_SUB(NOW(), 1))
AND LOCATE('SIMULACION – ', TRIM(UPPER(customername))) = 0
AND cast(numeroid as bigint) IN ("""+cadena+ """)
)
, EEFF_fecha AS (
select  numeroid,
        cast(Deuda_Cp as bigint) as Deuda_Cp,
        cast(Deuda_Lp as bigint) as Deuda_LP,
        cast(Activo_Total as bigint) as Activo_Total,
        Cast(Patrimonio as bigint) as Patrimonio,
        Cast(Endeudamientosinvaloriza as bigint) as Endeudamientosinvaloriza,
        Cast(Ebitdasobreintereses as bigint) as Ebitdasobreintereses,
        Cast(Pasivofinancierosobreebitda as bigint) as Pasivofinancierosobreebitda,
        Cast(Rotacionproveedoresdias as bigint) as Rotacionproveedoresdias,
        Cast(Rotacioncarteradias as bigint) as Rotacioncarteradias,
        Cast(Rotacioninventariodias as bigint) as Rotacioninventariodias,
        Cast(Totalinventario as bigint) as Totalinventario,
        Cast(Endeudamientofinanciero as bigint) as Endeudamientofinanciero,
        TRIM(Auditor) as Auditor,
        Fecha,
        max(statementdate_corte) as corte_ult_EEFF 
from EEFF 
group by 1,2,3,4,5,6,7,8,9,10,11,12,13,14,15)
,Max_EEFF as (SELECT *, row_number() over (partition by numeroid order by corte_ult_EEFF desc) as rn
FROM EEFF_fecha)
SELECT * FROM Max_EEFF WHERE rn<=1;"""

#Ejecutando la consulta y convierto a dataframe

cursor = cn.cursor()
creditleans = as_pandas(cursor.execute(query_str))

creditleans.to_excel(ruta_informes + r'\creditlean.xlsx', index = False)

print('Termino la consulta a creditlens')
      

#CRUCE ENTRE BASE_sombrilla y CREDILEANS

filePath6 = ruta_informes + r'\creditlean.xlsx'

df10_completo = pd.read_excel(filePath6, sheet_name='Sheet1')

#ELIMINA LOS DIFERENTES DE REVISOR
df10 =  df10_completo[(df10_completo['auditor'] == "Revisor")]

#CALCULA EL PASIVO 
df10['pasivo_total'] = df10['activo_total']-df10['patrimonio']
df10['deuda_Total'] = df10['deuda_cp']+df10['deuda_lp']
#Sobre escibre el nombre del campo para unirlo con la otra tabla que tiene nombre radicado en el campo
df10.rename(columns = {'numeroid':'Nit_Constructor'}, inplace = True)
#Se une las tablas con respecto al atributo radicado
df11 = pd.merge(df8, df10[['Nit_Constructor','activo_total','patrimonio','pasivo_total','endeudamientosinvaloriza',
                           'ebitdasobreintereses','pasivofinancierosobreebitda','rotacionproveedoresdias',
                           'rotacioninventariodias','rotacioncarteradias','totalinventario','fecha','endeudamientofinanciero','auditor',
                           'deuda_cp','deuda_lp','deuda_Total']],how="left")

print('Termino consolidaci�n con creditleans')

#CONECTA CON CENIEGARC PARA TOMAR LA DEUDA CORPORATIVA

print("Conectando a Impala")
CONN_STR = "DSN=IMPALA_PROD" 

def as_pandas(cursor):
    names = [metadata[0] for metadata in cursor.description]
    return pd.DataFrame([dict(zip(names, row)) for row in cursor], columns=names)

try:
    cn = pyodbc.connect(CONN_STR, autocommit = True )
    print("Conexion Exitosa")
except pyodbc.Error as ex:
    print(ex)

now = datetime.now()
ano = now.strftime("%Y")
mes = now.strftime("%m")
dia = now.strftime("%d")

filePath7 = ruta_informes + r'\BASE_Sombrilla.xlsx'

df12 = pd.read_excel(filePath7, sheet_name='Sheet1')
column_name="Nit_Constructor"
mylist = df12[column_name].tolist()
mylist=list(set(mylist))
cadena=str(mylist[0])

for i in range(1,len(mylist)):
    cadena=cadena+', '+str(mylist[i])

print("concatenaci�n de informe")

query_str = """select id,
        if(ofcenie=470,'Leasing','Banco') as linea,
        obl,
        vdesem,
        sk,
        (case
        when califi='A' then 'C1'
        when califi='B' then 'C2'
        when califi='C' then 'C3'
        when califi='D' then 'C4'
        when califi='E' then 'C5'
        when califi='F' then 'C6'
        when califi='G' then 'C7'
        when califi='H' then 'C8'
        when califi='N' then 'C9'
        when califi='O' then 'C10'
        when califi='P' then 'C11'
        when califi='Q' then 'C12'
        when califi='R' then 'C13'
        when califi='S' then 'C14'
        when califi='T' then 'C15'
        when califi='U' then 'C16'
        when califi='V' then 'C17'
        when califi='W' then 'C18'
        when califi='X' then 'C19'        
        end) as calificacion,
        pitotal,
        pktotal,
        altmora 
from 
resultados_riesgos.ceniegarc_lz
where ingestion_year = {} AND ingestion_month = {}
AND cast(id as BIGINT) IN ({})""".format(year_v, mes_v, cadena)

cursor = cn.cursor()
finacle = as_pandas(cursor.execute(query_str))
     
finacle.to_excel(ruta_informes + r'\cenegar_Saldos.xlsx', index = False)

print('Finalizo la consulta a ceniegarc')

#TABLA DINAMICA QUE SUMA LA DEUDA POR OBLIGACIÓN
#df11.groupby(by=["b"]).sum()


df11 = df11 [['Nit_Constructor','radicado','sociedad','proyecto','grupo','creditosaprobados','tipodecredito','saldoactual',
              'valorentregado','valorentregar','fecha_historico','municipio_','costo_urbanismo','costo_directos','costo_indirectos',
              'honorarios','costo_total','costos_financiables','credito_constructor','credito_preoperativo','credito_lote',
              'tipo_fiducia','mes_inicio_obra','avance_obra_meses','numero_inmuebles_por_vender','numero_inmuebles_vendidos','inmuebles_totales',
              'valor_total_ventas','programacion_actual','activo_total','patrimonio','pasivo_total','meses_prorrogados','vencimiento_credito','avance_obra',
              'endeudamientosinvaloriza','ebitdasobreintereses','pasivofinancierosobreebitda','rotacionproveedoresdias',
              'rotacioninventariodias','rotacioncarteradias','totalinventario','fecha','endeudamientofinanciero','auditor',
              'fecha__inicio_obra_','total_unidades','meses_programaci�n','total_ventas_esperadas','unidades_por_vender',
              'deuda_cp','deuda_lp','deuda_Total']]

#ORDENA POR NIT, RADICADO Y TIPO DE CREDITO 
#df11 = df11.sort_values(by = ['Nit_Constructor','radicado','tipodecredito','fecha_historico'],
                           # ascending=[True,True,True,False])
                            
#QUITA DUPLICADOS 
#df11_=df11.drop_duplicates(['Nit_Constructor','radicado','tipodecredito'])

#ELIMINA LOS PROYECTOS QUE ESTAN ESTUDIO PERO NO APROBADOS 
#df11_=  df11_[(df11_['saldoactual'] + df11_['valorentregar']) !=0 ]

df11.to_excel(ruta_informes + r'\BASE_Sombrilla.xlsx', index = False)

print('Termin� con �xito la ejecuci�n del script del cupo sombrilla')
