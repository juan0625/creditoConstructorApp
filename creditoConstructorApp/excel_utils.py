import pandas as pd
import os

EXCEL_PATH = os.path.join(os.path.expanduser('~'), 'pilotos', 'base_proyectos_pilotos.xlsx')

def save_to_excel(data):
    columns = [
        'ID PROYECTO', 'TIPO DE CREDITO', 'TIPO DE PRODUCTO', 'GRUPO DE RIESGO (CARPETA GERENCIADOR)',
        'NIT GRUPO DE RIESGO', 'NOMBRE PROYECTO', 'TIPO DE PROYECTO', 'NIT TITULAR',
        'TITULAR CREDITO', 'GERENTE', 'ARQUITECTO', 'AUXILIAR', 'PERITO', 'CIUDAD',
        'MONTO SOLICITADO 1 DESEMBOLSO', 'MONTO SOLICITADO CPI', 'MONTO SOLICITADO LOTE',
        'TOTAL VALOR APROBADO', 'CALIFICACIÓN IT', 'COSTOS FINANCIABLES', 'VALOR LOTE',
        'VALOR TOTAL PROYECTO', 'MESES PROGRAMACIÓN', 'TOTAL DE INMUEBLES', 'MESES PARA VENTA (12)'
    ]
    
    try:
        if os.path.exists(EXCEL_PATH):
            df_existing = pd.read_excel(EXCEL_PATH)
            df_new = pd.DataFrame([data], columns=columns)
            df = pd.concat([df_existing, df_new], ignore_index=True)
        else:
            os.makedirs(os.path.dirname(EXCEL_PATH), exist_ok=True)
            df = pd.DataFrame([data], columns=columns)
        
        df.to_excel(EXCEL_PATH, index=False)
        return True
    except Exception as e:
        print(f"Error saving to Excel: {e}")
        return False