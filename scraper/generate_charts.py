import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import os
from pathlib import Path

def generate_all_charts():
    # Configurar estilo de gráficos
    try:
        plt.style.use('seaborn-v0_8')
    except Exception:
        pass # Usar estilo por defecto si no está disponible seaborn-v0_8
    
    sns.set_palette("husl")

    # Rutas basadas en el directorio del script
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(BASE_DIR, 'dashboard', 'ramos_con_detalles.json')
    images_dir = os.path.join(BASE_DIR, 'dashboard', 'public', 'images')
    stats_path = os.path.join(BASE_DIR, 'dashboard', 'public', 'stats.json')

    # Crear directorios si no existen
    os.makedirs(images_dir, exist_ok=True)
    os.makedirs(os.path.dirname(stats_path), exist_ok=True)

    if not os.path.exists(json_path):
        print(f" ❗ No se pueden generar gráficos: '{json_path}' no existe.")
        return

    # Cargar datos
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Procesar datos
    subjects_data = []
    for subject in data.get('ramos_con_detalles', []):
        if subject.get('nota_final') is not None:  # Filtrar materias sin nota final
            subjects_data.append({
                'nombre': subject['nombre'],
                'nota_final': subject['nota_final'],
                'id_curso': subject['id_curso']
            })

    if not subjects_data:
        print(" ❗ No hay suficientes materias con nota final para generar gráficos.")
        return

    df = pd.DataFrame(subjects_data)

    # 1. Gráfico de barras - Notas por materia
    plt.figure(figsize=(15, 8))
    colors = plt.cm.viridis(np.linspace(0, 1, len(df)))
    bars = plt.bar(range(len(df)), df['nota_final'], color=colors, alpha=0.8, edgecolor='black', linewidth=0.5)

    plt.title('Rendimiento Académico por Materia', fontsize=20, fontweight='bold', pad=20)
    plt.xlabel('Materias', fontsize=14, fontweight='bold')
    plt.ylabel('Nota Final', fontsize=14, fontweight='bold')
    plt.xticks(range(len(df)), [name[:20] + '...' if len(name) > 20 else name for name in df['nombre']], 
               rotation=45, ha='right', fontsize=10)
    plt.ylim(0, 7.5)
    plt.grid(axis='y', alpha=0.3, linestyle='--')

    # Añadir valores en las barras
    for i, bar in enumerate(bars):
        height = bar.get_height()
        plt.text(bar.get_x() + bar.get_width()/2., height + 0.05,
                 f'{height:.1f}', ha='center', va='bottom', fontweight='bold')

    plt.tight_layout()
    plt.savefig(os.path.join(images_dir, 'grades_by_subject.png'), dpi=300, bbox_inches='tight')
    plt.close()

    # 2. Histograma de distribución de notas
    plt.figure(figsize=(10, 6))
    plt.hist(df['nota_final'], bins=15, color='skyblue', alpha=0.7, edgecolor='black', linewidth=1)
    promedio = df['nota_final'].mean()
    plt.axvline(promedio, color='red', linestyle='--', linewidth=2, 
                label=f'Promedio: {promedio:.2f}')
    plt.title('Distribución de Notas Finales', fontsize=18, fontweight='bold', pad=20)
    plt.xlabel('Nota Final', fontsize=14, fontweight='bold')
    plt.ylabel('Frecuencia', fontsize=14, fontweight='bold')
    plt.legend(fontsize=12)
    plt.grid(alpha=0.3, linestyle='--')
    plt.tight_layout()
    plt.savefig(os.path.join(images_dir, 'grade_distribution.png'), dpi=300, bbox_inches='tight')
    plt.close()

    # 3. Gráfico circular - Categorías de rendimiento
    def categorize_grade(grade):
        if grade >= 6.5:
            return 'Excelente (6.5-7.0)'
        elif grade >= 6.0:
            return 'Bueno (6.0-6.4)'
        elif grade >= 5.5:
            return 'Regular (5.5-5.9)'
        else:
            return 'Deficiente (<5.5)'

    df['categoria'] = df['nota_final'].apply(categorize_grade)
    category_counts = df['categoria'].value_counts()

    plt.figure(figsize=(10, 8))
    # Colores base para las categorías
    palette_colors = {'Excelente (6.5-7.0)': '#2ecc71', 'Bueno (6.0-6.4)': '#3498db', 'Regular (5.5-5.9)': '#f39c12', 'Deficiente (<5.5)': '#e74c3c'}
    colors_list = [palette_colors.get(cat, '#bdc3c7') for cat in category_counts.index]
    
    explode = tuple(0.05 for _ in range(len(category_counts)))
    wedges, texts, autotexts = plt.pie(category_counts.values, labels=category_counts.index, 
                                       autopct='%1.1f%%', startangle=90, colors=colors_list,
                                       explode=explode)

    plt.title('Distribución por Categorías de Rendimiento', fontsize=18, fontweight='bold', pad=20)

    for autotext in autotexts:
        autotext.set_color('white')
        autotext.set_fontweight('bold')
        autotext.set_fontsize(12)

    plt.tight_layout()
    plt.savefig(os.path.join(images_dir, 'performance_categories.png'), dpi=300, bbox_inches='tight')
    plt.close()

    # 4. Top 10 mejores y peores materias
    plt.figure(figsize=(14, 10))

    # Subplot para mejores materias
    plt.subplot(2, 1, 1)
    top_10 = df.nlargest(10, 'nota_final')
    bars1 = plt.barh(range(len(top_10)), top_10['nota_final'], color='green', alpha=0.7)
    plt.yticks(range(len(top_10)), [name[:30] + '...' if len(name) > 30 else name for name in top_10['nombre']])
    plt.xlabel('Nota Final', fontweight='bold')
    plt.title('Top 10 Mejores Materias', fontsize=16, fontweight='bold', pad=15)
    plt.grid(axis='x', alpha=0.3, linestyle='--')

    for i, bar in enumerate(bars1):
        width = bar.get_width()
        plt.text(width + 0.02, bar.get_y() + bar.get_height()/2,
                 f'{width:.1f}', ha='left', va='center', fontweight='bold')

    # Subplot para peores materias
    plt.subplot(2, 1, 2)
    bottom_10 = df.nsmallest(10, 'nota_final')
    bars2 = plt.barh(range(len(bottom_10)), bottom_10['nota_final'], color='red', alpha=0.7)
    plt.yticks(range(len(bottom_10)), [name[:30] + '...' if len(name) > 30 else name for name in bottom_10['nombre']])
    plt.xlabel('Nota Final', fontweight='bold')
    plt.title('Top 10 Materias con Menor Rendimiento', fontsize=16, fontweight='bold', pad=15)
    plt.grid(axis='x', alpha=0.3, linestyle='--')

    for i, bar in enumerate(bars2):
        width = bar.get_width()
        plt.text(width + 0.02, bar.get_y() + bar.get_height()/2,
                 f'{width:.1f}', ha='left', va='center', fontweight='bold')

    plt.tight_layout()
    plt.savefig(os.path.join(images_dir, 'top_bottom_subjects.png'), dpi=300, bbox_inches='tight')
    plt.close()

    # Generar estadísticas
    stats = {
        'total_materias': len(df),
        'promedio_general': float(df['nota_final'].mean()),
        'nota_maxima': float(df['nota_final'].max()),
        'nota_minima': float(df['nota_final'].min()),
        'desviacion_estandar': float(df['nota_final'].std()) if len(df) > 1 else 0.0,
        'materias_aprobadas': int(len(df[df['nota_final'] >= 4.0])),
        'materias_excelentes': int(len(df[df['nota_final'] >= 6.5]))
    }

    # Guardar estadísticas
    with open(stats_path, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print(" ✅ Gráficos y estadísticas actualizados exitosamente!")

if __name__ == "__main__":
    generate_all_charts()
