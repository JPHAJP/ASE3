# -*- coding: utf-8 -*-
"""
Analiza datos de pruebas de gripper desde un archivo CSV 'Protocolo_Simple.csv'.
Calcula overshoot, estadísticas básicas, métricas de capacidad y genera reportes.
Requisitos: pandas, numpy, matplotlib (opcional)
Uso:
    python analiza_gripper.py [ruta_archivo]
Salida:
    - reporte_metricas.csv
    - reporte_repetibilidad.csv
    - reporte_por_objeto.csv
    - interpretacion.txt
"""

import sys
import os
import math
import warnings
from pathlib import Path
import pandas as pd
import numpy as np

# Opcional: para gráficos y análisis estadístico
try:
    import matplotlib.pyplot as plt
    PLOT_AVAILABLE = True
except ImportError:
    PLOT_AVAILABLE = False
    print("Nota: matplotlib no disponible. No se generarán gráficos.")

try:
    from scipy import stats
    from scipy.stats import f_oneway, shapiro, normaltest
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("Nota: scipy no disponible. No se realizará análisis ANOVA ni pruebas de normalidad.")

warnings.filterwarnings('ignore', category=RuntimeWarning)

# ---------- Parámetros ajustables ----------
TIME_TARGET_MS = 300.0        # Objetivo típico de tiempo de respuesta
OVERSHOOT_OK_PCT = 10.0        # % overshoot aceptable
SUCCESS_TARGET_PCT = 95.0     # Tasa de éxito esperada
TOL_POS_MM = 0.5              # Tolerancia para Cpk de posición (± TOL respecto a objetivo)
CPK_MIN_OBJ = 1.33            # Objetivo de capacidad típico
FORCE_TOLERANCE_N = 0.5       # Tolerancia aceptable en fuerza (N)

REQUIRED_COLS = [
    "ID_Prueba", "Tipo_Prueba", "Objeto", "Masa_g",
    "Setpoint_Fuerza_N", "Fuerza_Medida_N", "Fuerza_Pico_N",
    "Posicion_Objetivo_mm", "Posicion_mm",
    "Tiempo_Respuesta_ms", "Exito_Agarre_1o0",
    "Temp_Min_C", "Temp_Max_C", "Notas"
]


def compute_overshoot(setpoint, f_pico):
    """Calcula el overshoot como porcentaje del setpoint."""
    try:
        setpoint = float(setpoint)
        f_pico = float(f_pico)
        if pd.isna(setpoint) or setpoint == 0:
            return np.nan
        return (f_pico - setpoint) / setpoint * 100.0
    except (ValueError, TypeError):
        return np.nan


def compute_error(medida, setpoint):
    """Calcula el error absoluto entre medida y setpoint."""
    try:
        medida = float(medida)
        setpoint = float(setpoint)
        if pd.isna(medida) or pd.isna(setpoint):
            return np.nan
        return medida - setpoint
    except (ValueError, TypeError):
        return np.nan


def cpk_from_series(x, target, tol):
    """
    Calcula Cpk respecto a límites USL/LSL = target ± tol
    """
    x = pd.to_numeric(x, errors="coerce").dropna()
    if len(x) < 2 or pd.isna(target) or pd.isna(tol) or tol <= 0:
        return np.nan
    
    mu = x.mean()
    sigma = x.std(ddof=1)
    
    if sigma == 0 or np.isnan(sigma):
        # Si no hay variación, Cpk depende de si está en el objetivo
        if abs(mu - target) <= tol:
            return np.inf
        else:
            return 0.0
    
    usl = target + tol
    lsl = target - tol
    cpu = (usl - mu) / (3 * sigma)
    cpl = (mu - lsl) / (3 * sigma)
    
    return min(cpu, cpl)


def analyze_by_test_type(df):
    """Analiza métricas por tipo de prueba."""
    results = []
    
    for tipo, grupo in df.groupby("Tipo_Prueba"):
        n = len(grupo)
        exito_rate = 100.0 * pd.to_numeric(grupo["Exito_Agarre_1o0"], errors="coerce").fillna(0).mean()
        
        f_medida = pd.to_numeric(grupo["Fuerza_Medida_N"], errors="coerce")
        f_media = f_medida.mean()
        f_std = f_medida.std(ddof=1)
        
        t_resp = pd.to_numeric(grupo["Tiempo_Respuesta_ms"], errors="coerce")
        t_media = t_resp.mean()
        t_std = t_resp.std(ddof=1)
        
        ov = pd.to_numeric(grupo["Overshoot_pct"], errors="coerce")
        ov_media = ov.mean()
        
        results.append({
            "Tipo_Prueba": tipo,
            "n_pruebas": n,
            "Tasa_Exito_%": round(exito_rate, 2),
            "Fuerza_Media_N": round(f_media, 3) if not pd.isna(f_media) else np.nan,
            "Fuerza_Std_N": round(f_std, 3) if not pd.isna(f_std) else np.nan,
            "Tiempo_Media_ms": round(t_media, 1) if not pd.isna(t_media) else np.nan,
            "Tiempo_Std_ms": round(t_std, 1) if not pd.isna(t_std) else np.nan,
            "Overshoot_Media_%": round(ov_media, 2) if not pd.isna(ov_media) else np.nan
        })
    
    return pd.DataFrame(results)


def analyze_by_object(df):
    """Analiza métricas por tipo de objeto."""
    results = []
    
    for objeto, grupo in df.groupby("Objeto"):
        n = len(grupo)
        masa = pd.to_numeric(grupo["Masa_g"], errors="coerce").iloc[0]
        exito_rate = 100.0 * pd.to_numeric(grupo["Exito_Agarre_1o0"], errors="coerce").fillna(0).mean()
        
        f_medida = pd.to_numeric(grupo["Fuerza_Medida_N"], errors="coerce")
        f_media = f_medida.mean()
        
        t_resp = pd.to_numeric(grupo["Tiempo_Respuesta_ms"], errors="coerce")
        t_media = t_resp.mean()
        
        results.append({
            "Objeto": objeto,
            "Masa_g": masa,
            "n_pruebas": n,
            "Tasa_Exito_%": round(exito_rate, 2),
            "Fuerza_Media_N": round(f_media, 3) if not pd.isna(f_media) else np.nan,
            "Tiempo_Media_ms": round(t_media, 1) if not pd.isna(t_media) else np.nan
        })
    
    return pd.DataFrame(results).sort_values("Masa_g")


def analyze_repeatability(df_rep, tol_pos_mm):
    """Analiza las pruebas de repetibilidad con métricas detalladas."""
    if len(df_rep) == 0:
        return pd.DataFrame()
    
    rep_rows = []
    df_rep = df_rep.copy()
    df_rep["Posicion_Objetivo_mm"] = pd.to_numeric(df_rep["Posicion_Objetivo_mm"], errors="coerce")
    df_rep["Posicion_mm"] = pd.to_numeric(df_rep["Posicion_mm"], errors="coerce")
    
    for (obj, objetivo), g in df_rep.groupby(["Objeto", "Posicion_Objetivo_mm"]):
        pos = g["Posicion_mm"].dropna()
        
        if len(pos) < 2:
            continue
        
        media = pos.mean()
        std = pos.std(ddof=1)
        minimo = pos.min()
        maximo = pos.max()
        rango = maximo - minimo
        cpk = cpk_from_series(pos, objetivo, tol_pos_mm)
        
        # Error sistemático (sesgo)
        sesgo = media - objetivo if not pd.isna(objetivo) else np.nan
        
        rep_rows.append({
            "Objeto": obj,
            "Posicion_Objetivo_mm": objetivo,
            "n": len(pos),
            "Media_mm": round(media, 3),
            "Std_mm": round(std, 4),
            "Min_mm": round(minimo, 3),
            "Max_mm": round(maximo, 3),
            "Rango_mm": round(rango, 3),
            "Sesgo_mm": round(sesgo, 3) if not pd.isna(sesgo) else np.nan,
            f"Cpk_(±{tol_pos_mm}mm)": round(cpk, 3) if not pd.isna(cpk) else np.nan
        })
    
    return pd.DataFrame(rep_rows)


def analyze_anova_by_test_type(df):
    """
    Realiza análisis ANOVA para comparar diferencias entre tipos de prueba.
    Analiza variables: Fuerza_Medida_N, Tiempo_Respuesta_ms, Overshoot_pct
    """
    if not SCIPY_AVAILABLE:
        print("Advertencia: scipy no disponible. No se puede realizar ANOVA.")
        return pd.DataFrame()
    
    results = []
    variables = ['Fuerza_Medida_N', 'Tiempo_Respuesta_ms', 'Overshoot_pct', 'Error_Fuerza_N']
    
    for var in variables:
        try:
            # Preparar datos por tipo de prueba
            grupos = []
            tipos = []
            
            for tipo, grupo in df.groupby('Tipo_Prueba'):
                data = pd.to_numeric(grupo[var], errors='coerce').dropna()
                if len(data) >= 3:  # Mínimo 3 observaciones por grupo
                    grupos.append(data.values)
                    tipos.append(tipo)
            
            if len(grupos) >= 2:
                # Realizar ANOVA
                f_stat, p_value = f_oneway(*grupos)
                
                # Calcular estadísticas descriptivas por grupo
                group_stats = []
                for i, (tipo, grupo_data) in enumerate(zip(tipos, grupos)):
                    group_stats.append({
                        'Tipo_Prueba': tipo,
                        'n': len(grupo_data),
                        'Media': np.mean(grupo_data),
                        'Std': np.std(grupo_data, ddof=1),
                        'Min': np.min(grupo_data),
                        'Max': np.max(grupo_data)
                    })
                
                results.append({
                    'Variable': var,
                    'F_statistic': round(f_stat, 4),
                    'p_value': round(p_value, 6),
                    'Significativo': 'Sí' if p_value < 0.05 else 'No',
                    'n_grupos': len(grupos),
                    'Interpretacion': 'Diferencias significativas entre grupos' if p_value < 0.05 
                                   else 'No hay diferencias significativas entre grupos',
                    'Estadisticas_grupos': group_stats
                })
            else:
                results.append({
                    'Variable': var,
                    'F_statistic': np.nan,
                    'p_value': np.nan,
                    'Significativo': 'N/A',
                    'n_grupos': len(grupos),
                    'Interpretacion': f'Insuficientes grupos válidos para ANOVA (se requieren ≥2, se tienen {len(grupos)})',
                    'Estadisticas_grupos': []
                })
                
        except Exception as e:
            results.append({
                'Variable': var,
                'F_statistic': np.nan,
                'p_value': np.nan,
                'Significativo': 'Error',
                'n_grupos': 0,
                'Interpretacion': f'Error en análisis: {str(e)}',
                'Estadisticas_grupos': []
            })
    
    return pd.DataFrame(results)


def analyze_normal_distribution(df):
    """
    Analiza la distribución normal de las variables principales y calcula
    casos fuera de ±3σ (límites de control estadístico).
    """
    results = []
    variables = ['Fuerza_Medida_N', 'Tiempo_Respuesta_ms', 'Overshoot_pct', 'Error_Fuerza_N']
    
    for var in variables:
        try:
            data = pd.to_numeric(df[var], errors='coerce').dropna()
            
            if len(data) < 3:
                results.append({
                    'Variable': var,
                    'n': len(data),
                    'Media': np.nan,
                    'Desv_Std': np.nan,
                    'Limite_Inferior_3sigma': np.nan,
                    'Limite_Superior_3sigma': np.nan,
                    'Casos_fuera_3sigma': np.nan,
                    'Pct_fuera_3sigma': np.nan,
                    'Shapiro_W': np.nan,
                    'Shapiro_p': np.nan,
                    'Es_Normal_Shapiro': 'N/A',
                    'Normaltest_stat': np.nan,
                    'Normaltest_p': np.nan,
                    'Es_Normal_DAgostino': 'N/A',
                    'Interpretacion': 'Insuficientes datos para análisis'
                })
                continue
            
            # Estadísticas básicas
            media = np.mean(data)
            std = np.std(data, ddof=1)
            n = len(data)
            
            # Límites de ±3σ
            limite_inf_3s = media - 3 * std
            limite_sup_3s = media + 3 * std
            
            # Casos fuera de ±3σ
            fuera_3sigma = ((data < limite_inf_3s) | (data > limite_sup_3s)).sum()
            pct_fuera_3sigma = (fuera_3sigma / n) * 100
            
            # Pruebas de normalidad
            shapiro_w, shapiro_p = np.nan, np.nan
            normaltest_stat, normaltest_p = np.nan, np.nan
            
            if SCIPY_AVAILABLE:
                try:
                    if n >= 3 and n <= 5000:  # Shapiro-Wilk funciona bien en este rango
                        shapiro_w, shapiro_p = shapiro(data)
                    
                    if n >= 8:  # D'Agostino requiere al menos 8 observaciones
                        normaltest_stat, normaltest_p = normaltest(data)
                except:
                    pass  # Si hay error, mantener NaN
            
            # Interpretación de normalidad
            es_normal_shapiro = 'N/A'
            if not np.isnan(shapiro_p):
                es_normal_shapiro = 'Sí' if shapiro_p > 0.05 else 'No'
            
            es_normal_dagostino = 'N/A'
            if not np.isnan(normaltest_p):
                es_normal_dagostino = 'Sí' if normaltest_p > 0.05 else 'No'
            
            # Interpretación general
            if pct_fuera_3sigma <= 0.27:  # Esperado teóricamente: ~0.27%
                control_msg = "Dentro de control estadístico"
            elif pct_fuera_3sigma <= 1.0:
                control_msg = "Ligeramente fuera de control"
            else:
                control_msg = "Fuera de control estadístico"
            
            interpretacion = f"{control_msg}. "
            if es_normal_shapiro == 'Sí' or es_normal_dagostino == 'Sí':
                interpretacion += "Distribución aproximadamente normal."
            elif es_normal_shapiro == 'No' or es_normal_dagostino == 'No':
                interpretacion += "Distribución NO normal - considerar transformaciones."
            else:
                interpretacion += "Normalidad no evaluada."
            
            results.append({
                'Variable': var,
                'n': n,
                'Media': round(media, 4),
                'Desv_Std': round(std, 4),
                'Limite_Inferior_3sigma': round(limite_inf_3s, 4),
                'Limite_Superior_3sigma': round(limite_sup_3s, 4),
                'Casos_fuera_3sigma': int(fuera_3sigma),
                'Pct_fuera_3sigma': round(pct_fuera_3sigma, 2),
                'Shapiro_W': round(shapiro_w, 4) if not np.isnan(shapiro_w) else np.nan,
                'Shapiro_p': round(shapiro_p, 4) if not np.isnan(shapiro_p) else np.nan,
                'Es_Normal_Shapiro': es_normal_shapiro,
                'Normaltest_stat': round(normaltest_stat, 4) if not np.isnan(normaltest_stat) else np.nan,
                'Normaltest_p': round(normaltest_p, 4) if not np.isnan(normaltest_p) else np.nan,
                'Es_Normal_DAgostino': es_normal_dagostino,
                'Interpretacion': interpretacion
            })
            
        except Exception as e:
            results.append({
                'Variable': var,
                'n': 0,
                'Media': np.nan,
                'Desv_Std': np.nan,
                'Limite_Inferior_3sigma': np.nan,
                'Limite_Superior_3sigma': np.nan,
                'Casos_fuera_3sigma': np.nan,
                'Pct_fuera_3sigma': np.nan,
                'Shapiro_W': np.nan,
                'Shapiro_p': np.nan,
                'Es_Normal_Shapiro': 'Error',
                'Normaltest_stat': np.nan,
                'Normaltest_p': np.nan,
                'Es_Normal_DAgostino': 'Error',
                'Interpretacion': f'Error en análisis: {str(e)}'
            })
    
    return pd.DataFrame(results)


def generate_plots(df, output_dir="."):
    """Genera gráficos de análisis si matplotlib está disponible."""
    if not PLOT_AVAILABLE:
        return
    
    try:
        # 1. Distribución de éxitos vs fuerza setpoint
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Análisis de Rendimiento del Gripper', fontsize=16, fontweight='bold')
        
        # Éxito vs Setpoint de Fuerza
        df_plot = df.copy()
        df_plot['Exito'] = pd.to_numeric(df_plot['Exito_Agarre_1o0'], errors='coerce')
        df_plot['Setpoint'] = pd.to_numeric(df_plot['Setpoint_Fuerza_N'], errors='coerce')
        
        exitos = df_plot.groupby('Setpoint')['Exito'].agg(['mean', 'count'])
        axes[0, 0].scatter(exitos.index, exitos['mean'] * 100, s=exitos['count']*10, alpha=0.6)
        axes[0, 0].axhline(y=SUCCESS_TARGET_PCT, color='r', linestyle='--', label=f'Objetivo {SUCCESS_TARGET_PCT}%')
        axes[0, 0].set_xlabel('Setpoint de Fuerza (N)')
        axes[0, 0].set_ylabel('Tasa de Éxito (%)')
        axes[0, 0].set_title('Éxito vs Setpoint de Fuerza')
        axes[0, 0].legend()
        axes[0, 0].grid(True, alpha=0.3)
        
        # Overshoot vs Setpoint
        ov_data = df_plot[['Setpoint', 'Overshoot_pct']].dropna()
        axes[0, 1].scatter(ov_data['Setpoint'], ov_data['Overshoot_pct'], alpha=0.5)
        axes[0, 1].axhline(y=OVERSHOOT_OK_PCT, color='r', linestyle='--', label=f'Límite {OVERSHOOT_OK_PCT}%')
        axes[0, 1].set_xlabel('Setpoint de Fuerza (N)')
        axes[0, 1].set_ylabel('Overshoot (%)')
        axes[0, 1].set_title('Overshoot vs Setpoint')
        axes[0, 1].legend()
        axes[0, 1].grid(True, alpha=0.3)
        
        # Tiempo de respuesta por objeto
        tiempo_obj = df_plot.groupby('Objeto')['Tiempo_Respuesta_ms'].agg(['mean', 'std'])
        tiempo_obj = tiempo_obj.sort_values('mean')
        axes[1, 0].barh(range(len(tiempo_obj)), tiempo_obj['mean'], xerr=tiempo_obj['std'], alpha=0.7)
        axes[1, 0].set_yticks(range(len(tiempo_obj)))
        axes[1, 0].set_yticklabels(tiempo_obj.index, fontsize=8)
        axes[1, 0].axvline(x=TIME_TARGET_MS, color='r', linestyle='--', label=f'Objetivo {TIME_TARGET_MS}ms')
        axes[1, 0].set_xlabel('Tiempo de Respuesta (ms)')
        axes[1, 0].set_title('Tiempo de Respuesta por Objeto')
        axes[1, 0].legend()
        axes[1, 0].grid(True, alpha=0.3, axis='x')
        
        # Error de fuerza
        df_plot['Error_Fuerza'] = df_plot.apply(
            lambda r: compute_error(r['Fuerza_Medida_N'], r['Setpoint_Fuerza_N']), axis=1
        )
        error_data = df_plot[['Setpoint', 'Error_Fuerza']].dropna()
        axes[1, 1].scatter(error_data['Setpoint'], error_data['Error_Fuerza'], alpha=0.5)
        axes[1, 1].axhline(y=0, color='g', linestyle='-', linewidth=2, label='Error = 0')
        axes[1, 1].axhline(y=FORCE_TOLERANCE_N, color='r', linestyle='--', alpha=0.7)
        axes[1, 1].axhline(y=-FORCE_TOLERANCE_N, color='r', linestyle='--', alpha=0.7, label=f'±{FORCE_TOLERANCE_N}N')
        axes[1, 1].set_xlabel('Setpoint de Fuerza (N)')
        axes[1, 1].set_ylabel('Error de Fuerza (N)')
        axes[1, 1].set_title('Error de Fuerza vs Setpoint')
        axes[1, 1].legend()
        axes[1, 1].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'analisis_gripper.png'), dpi=150, bbox_inches='tight')
        print("✓ Gráfico guardado: analisis_gripper.png")
        plt.close()
        
    except Exception as e:
        print(f"Advertencia: No se pudieron generar gráficos. Error: {e}")


def generate_distribution_plots(df, normal_analysis, output_dir="."):
    """Genera gráficos de distribución normal y límites de control."""
    if not PLOT_AVAILABLE:
        return
    
    try:
        variables = ['Fuerza_Medida_N', 'Tiempo_Respuesta_ms', 'Overshoot_pct', 'Error_Fuerza_N']
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle('Análisis de Distribución Normal y Límites de Control (±3σ)', 
                    fontsize=16, fontweight='bold')
        
        axes = axes.ravel()
        
        for i, var in enumerate(variables):
            # Obtener datos
            data = pd.to_numeric(df[var], errors='coerce').dropna()
            
            if len(data) < 3:
                axes[i].text(0.5, 0.5, f'Insuficientes datos\npara {var}', 
                           ha='center', va='center', transform=axes[i].transAxes)
                axes[i].set_title(f'{var}')
                continue
            
            # Buscar estadísticas en normal_analysis
            var_stats = normal_analysis[normal_analysis['Variable'] == var]
            if len(var_stats) > 0:
                media = var_stats.iloc[0]['Media']
                std = var_stats.iloc[0]['Desv_Std']
                limite_inf = var_stats.iloc[0]['Limite_Inferior_3sigma']
                limite_sup = var_stats.iloc[0]['Limite_Superior_3sigma']
                fuera_3sigma = var_stats.iloc[0]['Casos_fuera_3sigma']
                pct_fuera = var_stats.iloc[0]['Pct_fuera_3sigma']
            else:
                media = np.mean(data)
                std = np.std(data, ddof=1)
                limite_inf = media - 3 * std
                limite_sup = media + 3 * std
                fuera_3sigma = ((data < limite_inf) | (data > limite_sup)).sum()
                pct_fuera = (fuera_3sigma / len(data)) * 100
            
            # Histograma con curva normal teórica
            axes[i].hist(data, bins=20, density=True, alpha=0.7, color='lightblue', 
                        edgecolor='black', label='Datos observados')
            
            # Curva normal teórica
            x = np.linspace(data.min(), data.max(), 100)
            y = stats.norm.pdf(x, media, std)
            axes[i].plot(x, y, 'r-', linewidth=2, label='Distribución Normal Teórica')
            
            # Límites de control ±3σ
            axes[i].axvline(media, color='green', linestyle='-', linewidth=2, label=f'Media = {media:.3f}')
            axes[i].axvline(limite_inf, color='red', linestyle='--', linewidth=2, 
                           label=f'Límite inferior (-3σ)')
            axes[i].axvline(limite_sup, color='red', linestyle='--', linewidth=2, 
                           label=f'Límite superior (+3σ)')
            
            # Marcar puntos fuera de control
            fuera_control = data[(data < limite_inf) | (data > limite_sup)]
            if len(fuera_control) > 0:
                y_height = axes[i].get_ylim()[1] * 0.1
                axes[i].scatter(fuera_control, [y_height] * len(fuera_control), 
                              color='red', s=50, marker='x', 
                              label=f'Fuera de control ({int(fuera_3sigma)} casos, {pct_fuera:.1f}%)')
            
            # Configurar gráfico
            axes[i].set_title(f'{var}\nσ = {std:.4f}, Fuera ±3σ: {pct_fuera:.1f}%')
            axes[i].set_xlabel('Valores')
            axes[i].set_ylabel('Densidad')
            axes[i].legend(fontsize=8)
            axes[i].grid(True, alpha=0.3)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'distribucion_normal.png'), dpi=150, bbox_inches='tight')
        print("✓ Gráfico guardado: distribucion_normal.png")
        plt.close()
        
    except Exception as e:
        print(f"Advertencia: No se pudieron generar gráficos de distribución. Error: {e}")


def generate_anova_plots(df, anova_results, output_dir="."):
    """Genera gráficos de boxplot para visualizar diferencias entre tipos de prueba."""
    if not PLOT_AVAILABLE:
        return
    
    try:
        # Filtrar variables con resultados válidos de ANOVA
        variables_validas = []
        for _, row in anova_results.iterrows():
            if not pd.isna(row['F_statistic']) and row['n_grupos'] >= 2:
                variables_validas.append(row['Variable'])
        
        if len(variables_validas) == 0:
            print("No hay variables válidas para gráficos ANOVA")
            return
        
        n_vars = len(variables_validas)
        cols = 2
        rows = (n_vars + cols - 1) // cols
        
        fig, axes = plt.subplots(rows, cols, figsize=(14, 4*rows))
        fig.suptitle('Análisis ANOVA - Distribución por Tipo de Prueba', 
                    fontsize=16, fontweight='bold')
        
        if n_vars == 1:
            axes = [axes]
        elif rows == 1:
            axes = axes
        else:
            axes = axes.ravel()
        
        for i, var in enumerate(variables_validas):
            # Preparar datos
            data_plot = []
            labels_plot = []
            
            for tipo, grupo in df.groupby('Tipo_Prueba'):
                data = pd.to_numeric(grupo[var], errors='coerce').dropna()
                if len(data) >= 3:
                    data_plot.append(data.values)
                    labels_plot.append(tipo)
            
            if len(data_plot) >= 2:
                # Boxplot
                bp = axes[i].boxplot(data_plot, labels=labels_plot, patch_artist=True)
                
                # Colorear las cajas
                colors = plt.cm.Set3(np.linspace(0, 1, len(data_plot)))
                for patch, color in zip(bp['boxes'], colors):
                    patch.set_facecolor(color)
                    patch.set_alpha(0.7)
                
                # Obtener estadísticas ANOVA
                anova_row = anova_results[anova_results['Variable'] == var].iloc[0]
                p_val = anova_row['p_value']
                significativo = anova_row['Significativo']
                
                axes[i].set_title(f'{var}\nF = {anova_row["F_statistic"]:.3f}, '
                                f'p = {p_val:.4f} ({significativo})')
                axes[i].set_ylabel('Valores')
                axes[i].tick_params(axis='x', rotation=45)
                axes[i].grid(True, alpha=0.3)
                
                # Marcar significancia
                if significativo == 'Sí':
                    axes[i].text(0.02, 0.98, '* Significativo', transform=axes[i].transAxes,
                               verticalalignment='top', bbox=dict(boxstyle='round', 
                               facecolor='yellow', alpha=0.7))
        
        # Ocultar subplots vacíos
        for j in range(n_vars, len(axes)):
            axes[j].set_visible(False)
        
        plt.tight_layout()
        plt.savefig(os.path.join(output_dir, 'anova_boxplots.png'), dpi=150, bbox_inches='tight')
        print("✓ Gráfico guardado: anova_boxplots.png")
        plt.close()
        
    except Exception as e:
        print(f"Advertencia: No se pudieron generar gráficos ANOVA. Error: {e}")


def generate_interpretation(metrics, rep_table, obj_table, df, anova_results=None, normal_analysis=None):
    """Genera un reporte de interpretación detallado."""
    lines = []
    lines.append("=" * 70)
    lines.append("REPORTE DE ANÁLISIS DE GRIPPER")
    lines.append("=" * 70)
    lines.append(f"\nTotal de pruebas: {metrics['n_total']}")
    lines.append(f"Rango de temperatura: {metrics['Temp_Min_C']:.1f}°C - {metrics['Temp_Max_C']:.1f}°C")
    
    # Sección de éxito
    lines.append("\n" + "=" * 70)
    lines.append("1. TASA DE ÉXITO")
    lines.append("=" * 70)
    tasa = metrics['tasa_exito_pct']
    status = "✓ OK" if tasa >= SUCCESS_TARGET_PCT else "✗ REQUIERE ATENCIÓN"
    lines.append(f"Tasa de éxito global: {tasa:.1f}% {status}")
    lines.append(f"Objetivo: ≥{SUCCESS_TARGET_PCT}%")
    lines.append(f"Éxitos: {metrics['n_exitos']} / {metrics['n_total']}")
    
    # Análisis de falla por setpoint
    if metrics['n_total'] - metrics['n_exitos'] > 0:
        df_fallas = df[pd.to_numeric(df['Exito_Agarre_1o0'], errors='coerce') == 0]
        if len(df_fallas) > 0:
            lines.append(f"\nAnálisis de fallas ({len(df_fallas)} casos):")
            setpoint_fallas = df_fallas.groupby('Setpoint_Fuerza_N').size().sort_values(ascending=False)
            for sp, count in setpoint_fallas.head(3).items():
                lines.append(f"  - Setpoint {sp}N: {count} fallas")
    
    # Sección de fuerza
    lines.append("\n" + "=" * 70)
    lines.append("2. DESEMPEÑO DE FUERZA")
    lines.append("=" * 70)
    lines.append(f"Fuerza medida promedio: {metrics['Fuerza_media']:.3f} ± {metrics['Fuerza_std']:.3f} N")
    lines.append(f"Error promedio: {metrics['Error_Fuerza_media']:.3f} N")
    
    if not math.isnan(metrics.get('Error_Fuerza_pct_dentro', np.nan)):
        pct_dentro = metrics['Error_Fuerza_pct_dentro']
        status = "✓ OK" if pct_dentro >= 90 else "⚠ Revisar"
        lines.append(f"Casos dentro de tolerancia (±{FORCE_TOLERANCE_N}N): {pct_dentro:.1f}% {status}")
    
    # Sección de overshoot
    lines.append("\n" + "=" * 70)
    lines.append("3. OVERSHOOT")
    lines.append("=" * 70)
    if not math.isnan(metrics["Overshoot_media_pct"]):
        ov_media = metrics['Overshoot_media_pct']
        pct_dentro = metrics['Overshoot_pct_dentro']
        status = "✓ OK" if pct_dentro >= 80 else "⚠ Revisar tuning PID"
        lines.append(f"Overshoot promedio: {ov_media:.2f}%")
        lines.append(f"Casos ≤{OVERSHOOT_OK_PCT}%: {pct_dentro:.1f}% {status}")
        lines.append(f"Límite objetivo: ≤{OVERSHOOT_OK_PCT}%")
    
    # Sección de tiempo
    lines.append("\n" + "=" * 70)
    lines.append("4. TIEMPO DE RESPUESTA")
    lines.append("=" * 70)
    if not math.isnan(metrics["Tiempo_media_ms"]):
        t_media = metrics['Tiempo_media_ms']
        t_std = metrics.get('Tiempo_std_ms', np.nan)
        pct_cumple = metrics['Tiempo_pct_cumple']
        status = "✓ OK" if pct_cumple >= 90 else "⚠ Optimizar"
        
        lines.append(f"Tiempo promedio: {t_media:.1f} ± {t_std:.1f} ms")
        lines.append(f"Casos ≤{TIME_TARGET_MS}ms: {pct_cumple:.1f}% {status}")
        lines.append(f"Objetivo: ≤{TIME_TARGET_MS}ms")
    
    # Sección de repetibilidad
    if len(rep_table) > 0:
        lines.append("\n" + "=" * 70)
        lines.append("5. REPETIBILIDAD Y CAPACIDAD DEL PROCESO")
        lines.append("=" * 70)
        
        worst = rep_table.sort_values(by=rep_table.columns[-1]).iloc[0]
        best = rep_table.sort_values(by=rep_table.columns[-1], ascending=False).iloc[0]
        cpk_col = rep_table.columns[-1]
        
        lines.append(f"\nMejor Cpk: {best[cpk_col]:.2f} (Objeto: {best['Objeto']}, "
                    f"objetivo: {best['Posicion_Objetivo_mm']}mm)")
        lines.append(f"Peor Cpk: {worst[cpk_col]:.2f} (Objeto: {worst['Objeto']}, "
                    f"objetivo: {worst['Posicion_Objetivo_mm']}mm)")
        
        cpk_val = worst[cpk_col]
        if cpk_val >= CPK_MIN_OBJ:
            status = f"✓ Proceso capaz (Cpk ≥ {CPK_MIN_OBJ})"
        elif cpk_val >= 1.0:
            status = f"⚠ Proceso marginal (1.0 ≤ Cpk < {CPK_MIN_OBJ})"
        else:
            status = "✗ Proceso no capaz (Cpk < 1.0) - Requiere mejora"
        
        lines.append(f"\nEvaluación: {status}")
        lines.append(f"Desviación estándar (peor caso): {worst['Std_mm']:.4f} mm")
        
        # Resumen por objeto
        lines.append(f"\nResumen por objeto:")
        for _, row in rep_table.iterrows():
            lines.append(f"  - {row['Objeto']} ({row['Posicion_Objetivo_mm']}mm): "
                        f"σ={row['Std_mm']:.4f}mm, Cpk={row[cpk_col]:.2f}")
    
    # Análisis por objeto
    if len(obj_table) > 0:
        lines.append("\n" + "=" * 70)
        lines.append("6. DESEMPEÑO POR TIPO DE OBJETO")
        lines.append("=" * 70)
        for _, row in obj_table.iterrows():
            lines.append(f"\n{row['Objeto']} ({row['Masa_g']}g):")
            lines.append(f"  - Pruebas: {row['n_pruebas']}")
            lines.append(f"  - Éxito: {row['Tasa_Exito_%']:.1f}%")
            lines.append(f"  - Fuerza media: {row['Fuerza_Media_N']:.3f}N")
            lines.append(f"  - Tiempo medio: {row['Tiempo_Media_ms']:.1f}ms")
    
    # Recomendaciones
    lines.append("\n" + "=" * 70)
    lines.append("7. RECOMENDACIONES")
    lines.append("=" * 70)
    
    recommendations = []
    
    if tasa < SUCCESS_TARGET_PCT:
        recommendations.append("⚠ Mejorar tasa de éxito: revisar setpoints de fuerza bajos")
    
    if not math.isnan(metrics.get('Overshoot_pct_dentro', np.nan)) and metrics['Overshoot_pct_dentro'] < 80:
        recommendations.append("⚠ Ajustar parámetros PID para reducir overshoot")
    
    if not math.isnan(metrics.get('Tiempo_pct_cumple', np.nan)) and metrics['Tiempo_pct_cumple'] < 90:
        recommendations.append("⚠ Optimizar tiempo de respuesta")
    
    if len(rep_table) > 0:
        worst_cpk = rep_table[cpk_col].min()
        if worst_cpk < CPK_MIN_OBJ:
            recommendations.append(f"⚠ Mejorar repetibilidad (Cpk objetivo: {CPK_MIN_OBJ})")
    
    if len(recommendations) == 0:
        lines.append("✓ Sistema dentro de especificaciones. Mantener monitoreo continuo.")
    else:
        for rec in recommendations:
            lines.append(rec)
    
    # Sección de análisis ANOVA
    if anova_results is not None and len(anova_results) > 0:
        lines.append("\n" + "=" * 70)
        lines.append("8. ANÁLISIS ANOVA - DIFERENCIAS ENTRE TIPOS DE PRUEBA")
        lines.append("=" * 70)
        
        for _, row in anova_results.iterrows():
            var = row['Variable']
            lines.append(f"\n{var}:")
            
            if row['n_grupos'] >= 2 and not pd.isna(row['F_statistic']):
                lines.append(f"  - Estadístico F: {row['F_statistic']:.4f}")
                lines.append(f"  - Valor p: {row['p_value']:.6f}")
                lines.append(f"  - Significativo: {row['Significativo']}")
                lines.append(f"  - Grupos analizados: {row['n_grupos']}")
                lines.append(f"  - Interpretación: {row['Interpretacion']}")
                
                # Mostrar estadísticas por grupo si están disponibles
                if 'Estadisticas_grupos' in row and row['Estadisticas_grupos']:
                    lines.append("  - Estadísticas por tipo de prueba:")
                    for grupo_stat in row['Estadisticas_grupos']:
                        lines.append(f"    • {grupo_stat['Tipo_Prueba']}: "
                                   f"n={grupo_stat['n']}, "
                                   f"μ={grupo_stat['Media']:.3f}, "
                                   f"σ={grupo_stat['Std']:.3f}")
            else:
                lines.append(f"  - {row['Interpretacion']}")
    
    # Sección de análisis de distribución normal
    if normal_analysis is not None and len(normal_analysis) > 0:
        lines.append("\n" + "=" * 70)
        lines.append("9. ANÁLISIS DE DISTRIBUCIÓN NORMAL Y CONTROL ESTADÍSTICO")
        lines.append("=" * 70)
        
        for _, row in normal_analysis.iterrows():
            var = row['Variable']
            lines.append(f"\n{var}:")
            
            if not pd.isna(row['Media']):
                lines.append(f"  - n: {row['n']}")
                lines.append(f"  - Media: {row['Media']:.4f}")
                lines.append(f"  - Desviación estándar: {row['Desv_Std']:.4f}")
                lines.append(f"  - Límites de control (±3σ): [{row['Limite_Inferior_3sigma']:.4f}, {row['Limite_Superior_3sigma']:.4f}]")
                lines.append(f"  - Casos fuera de ±3σ: {row['Casos_fuera_3sigma']} ({row['Pct_fuera_3sigma']:.2f}%)")
                
                # Pruebas de normalidad
                if not pd.isna(row['Shapiro_p']):
                    lines.append(f"  - Test Shapiro-Wilk: W={row['Shapiro_W']:.4f}, p={row['Shapiro_p']:.4f} → {row['Es_Normal_Shapiro']}")
                
                if not pd.isna(row['Normaltest_p']):
                    lines.append(f"  - Test D'Agostino: stat={row['Normaltest_stat']:.4f}, p={row['Normaltest_p']:.4f} → {row['Es_Normal_DAgostino']}")
                
                lines.append(f"  - Interpretación: {row['Interpretacion']}")
            else:
                lines.append(f"  - {row['Interpretacion']}")
    
    lines.append("\n" + "=" * 70)
    lines.append("Fin del reporte")
    lines.append("=" * 70)
    
    return "\n".join(lines)


def main():
    """Función principal."""
    # Determinar archivo de entrada
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        # Buscar archivos CSV o Excel en el directorio
        if os.path.exists("Protocolo_Simple.csv"):
            input_file = "Protocolo_Simple.csv"
        elif os.path.exists("Protocolo_Simple.xlsx"):
            input_file = "Protocolo_Simple.xlsx"
        else:
            print("Error: No se encontró archivo de entrada.")
            print("Uso: python analiza_gripper.py [archivo.csv o archivo.xlsx]")
            sys.exit(1)
    
    print(f"\n{'='*70}")
    print(f"Analizando archivo: {input_file}")
    print(f"{'='*70}\n")
    
    # Leer archivo
    try:
        if input_file.endswith('.csv'):
            df = pd.read_csv(input_file, encoding='utf-8-sig')
        elif input_file.endswith('.xlsx'):
            df = pd.read_excel(input_file, sheet_name="Datos")
        else:
            print("Error: Formato de archivo no soportado. Use CSV o XLSX.")
            sys.exit(1)
    except Exception as e:
        print(f"Error al leer archivo: {e}")
        sys.exit(1)
    
    # Validación de columnas
    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        print(f"Advertencia: Faltan columnas esperadas: {missing}")
        print("Continuando con columnas disponibles...")
    
    # Limpieza inicial
    print(f"Registros cargados: {len(df)}")
    
    # Calcular overshoot
    df["Overshoot_pct"] = df.apply(
        lambda r: compute_overshoot(r["Setpoint_Fuerza_N"], r["Fuerza_Pico_N"]), 
        axis=1
    )
    
    # Calcular error de fuerza
    df["Error_Fuerza_N"] = df.apply(
        lambda r: compute_error(r["Fuerza_Medida_N"], r["Setpoint_Fuerza_N"]), 
        axis=1
    )
    
    # Métricas globales
    metrics = {}
    metrics["n_total"] = len(df)
    
    exito_series = pd.to_numeric(df["Exito_Agarre_1o0"], errors="coerce").fillna(0)
    metrics["n_exitos"] = int(exito_series.sum())
    metrics["tasa_exito_pct"] = 100.0 * exito_series.mean()
    
    # Fuerza
    f_medida = pd.to_numeric(df["Fuerza_Medida_N"], errors="coerce")
    metrics["Fuerza_media"] = f_medida.mean()
    metrics["Fuerza_std"] = f_medida.std(ddof=1)
    metrics["Fuerza_min"] = f_medida.min()
    metrics["Fuerza_max"] = f_medida.max()
    
    # Error de fuerza
    error_fuerza = pd.to_numeric(df["Error_Fuerza_N"], errors="coerce")
    metrics["Error_Fuerza_media"] = error_fuerza.mean()
    metrics["Error_Fuerza_std"] = error_fuerza.std(ddof=1)
    metrics["Error_Fuerza_pct_dentro"] = 100.0 * error_fuerza.apply(
        lambda x: 1 if (not np.isnan(x) and abs(x) <= FORCE_TOLERANCE_N) else 0
    ).mean()
    
    # Overshoot
    ov = pd.to_numeric(df["Overshoot_pct"], errors="coerce")
    metrics["Overshoot_media_pct"] = ov.mean()
    metrics["Overshoot_std_pct"] = ov.std(ddof=1)
    metrics["Overshoot_pct_dentro"] = 100.0 * ov.apply(
        lambda x: 1 if (not np.isnan(x) and x <= OVERSHOOT_OK_PCT) else 0
    ).mean()
    
    # Tiempo
    t_resp = pd.to_numeric(df["Tiempo_Respuesta_ms"], errors="coerce")
    metrics["Tiempo_media_ms"] = t_resp.mean()
    metrics["Tiempo_std_ms"] = t_resp.std(ddof=1)
    metrics["Tiempo_min_ms"] = t_resp.min()
    metrics["Tiempo_max_ms"] = t_resp.max()
    metrics["Tiempo_pct_cumple"] = 100.0 * t_resp.apply(
        lambda x: 1 if (not np.isnan(x) and x <= TIME_TARGET_MS) else 0
    ).mean()
    
    # Temperatura
    temp_min = pd.to_numeric(df["Temp_Min_C"], errors="coerce")
    temp_max = pd.to_numeric(df["Temp_Max_C"], errors="coerce")
    metrics["Temp_Min_C"] = temp_min.min()
    metrics["Temp_Max_C"] = temp_max.max()
    
    # Análisis por tipo de prueba
    print("\nAnalizando por tipo de prueba...")
    test_type_table = analyze_by_test_type(df)
    
    # Análisis por objeto
    print("Analizando por tipo de objeto...")
    obj_table = analyze_by_object(df)
    
    # Análisis de repetibilidad
    print("Analizando repetibilidad...")
    df_rep = df[df["Tipo_Prueba"].astype(str).str.lower() == "repetibilidad"].copy()
    rep_table = analyze_repeatability(df_rep, TOL_POS_MM)
    
    # Análisis ANOVA por tipo de prueba
    print("Realizando análisis ANOVA por tipo de prueba...")
    anova_results = analyze_anova_by_test_type(df)
    
    # Análisis de distribución normal
    print("Analizando distribución normal y límites de control...")
    normal_analysis = analyze_normal_distribution(df)
    
    # Guardar resultados
    print("\nGuardando resultados...")
    
    report = pd.DataFrame([metrics])
    report.to_csv("reporte_metricas.csv", index=False, encoding="utf-8-sig")
    print("✓ reporte_metricas.csv")
    
    if len(test_type_table) > 0:
        test_type_table.to_csv("reporte_por_tipo_prueba.csv", index=False, encoding="utf-8-sig")
        print("✓ reporte_por_tipo_prueba.csv")
    
    if len(obj_table) > 0:
        obj_table.to_csv("reporte_por_objeto.csv", index=False, encoding="utf-8-sig")
        print("✓ reporte_por_objeto.csv")
    
    if len(rep_table) > 0:
        rep_table.to_csv("reporte_repetibilidad.csv", index=False, encoding="utf-8-sig")
        print("✓ reporte_repetibilidad.csv")
    
    # Guardar nuevos análisis
    if len(anova_results) > 0:
        anova_results.to_csv("reporte_anova.csv", index=False, encoding="utf-8-sig")
        print("✓ reporte_anova.csv")
    
    if len(normal_analysis) > 0:
        normal_analysis.to_csv("reporte_distribucion_normal.csv", index=False, encoding="utf-8-sig")
        print("✓ reporte_distribucion_normal.csv")
    
    # Guardar datos procesados con columnas calculadas
    df_output = df.copy()
    df_output.to_csv("datos_procesados.csv", index=False, encoding="utf-8-sig")
    print("✓ datos_procesados.csv")
    
    # Generar interpretación
    print("\nGenerando interpretación...")
    interpretation = generate_interpretation(metrics, rep_table, obj_table, df, anova_results, normal_analysis)
    
    with open("interpretacion.txt", "w", encoding="utf-8") as f:
        f.write(interpretation)
    print("✓ interpretacion.txt")
    
    # Generar gráficos
    if PLOT_AVAILABLE:
        print("\nGenerando gráficos...")
        generate_plots(df)
        generate_distribution_plots(df, normal_analysis)
        generate_anova_plots(df, anova_results)
    
    # Mostrar resumen en consola
    print("\n" + "="*70)
    print("RESUMEN EJECUTIVO")
    print("="*70)
    print(f"Total de pruebas: {metrics['n_total']}")
    print(f"Tasa de éxito: {metrics['tasa_exito_pct']:.1f}%")
    print(f"Fuerza promedio: {metrics['Fuerza_media']:.3f} ± {metrics['Fuerza_std']:.3f} N")
    print(f"Tiempo promedio: {metrics['Tiempo_media_ms']:.1f} ± {metrics['Tiempo_std_ms']:.1f} ms")
    print(f"Overshoot promedio: {metrics['Overshoot_media_pct']:.2f}%")
    
    if len(rep_table) > 0:
        cpk_col = rep_table.columns[-1]
        min_cpk = rep_table[cpk_col].min()
        max_cpk = rep_table[cpk_col].max()
        print(f"Cpk (repetibilidad): {min_cpk:.2f} - {max_cpk:.2f}")
    
    print("="*70)
    print("\n✓ Análisis completado exitosamente!")
    print(f"\nArchivos generados en: {os.path.abspath('.')}")
    print("  - reporte_metricas.csv")
    print("  - reporte_por_tipo_prueba.csv")
    print("  - reporte_por_objeto.csv")
    if len(rep_table) > 0:
        print("  - reporte_repetibilidad.csv")
    if len(anova_results) > 0:
        print("  - reporte_anova.csv")
    if len(normal_analysis) > 0:
        print("  - reporte_distribucion_normal.csv")
    print("  - datos_procesados.csv")
    print("  - interpretacion.txt")
    if PLOT_AVAILABLE:
        print("  - analisis_gripper.png")
        print("  - distribucion_normal.png")
        print("  - anova_boxplots.png")
    print("\n")


if __name__ == "__main__":
    main()