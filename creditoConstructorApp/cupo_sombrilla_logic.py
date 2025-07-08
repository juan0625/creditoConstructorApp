import pandas as pd
import numpy as np

def procesar_paso_2(cenegar_path):
    """Simula el procesamiento del Paso 2"""
    # Lógica real iría aquí
    df = pd.read_excel(cenegar_path)
    # Ejemplo de procesamiento
    df['nueva_columna'] = df['obl'].apply(lambda x: 'Constructor' if 'CONST' in str(x) else 'Corporativo')
    return df

def procesar_paso_3(base_path):
    """Simula el procesamiento del Paso 3"""
    df = pd.read_excel(base_path)
    
    # Ordenar datos
    df = df.sort_values(by=['Nit_Constructor', 'radicado'])
    
    # Quitar duplicados
    df = df.drop_duplicates(subset=['Nit_Constructor', 'radicado'])
    
    # Buscar NITs en cero
    df['Nit_Constructor'] = df['Nit_Constructor'].replace(0, np.nan)
    df['Nit_Constructor'] = df['Nit_Constructor'].fillna(df.groupby('grupo')['Nit_Constructor'].transform('first'))
    
    return df