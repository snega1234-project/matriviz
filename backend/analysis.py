"""
Data Analysis and Visual Rendering Module
Handles Pandas and NumPy data manipulation and Seaborn/Matplotlib visualization.
All chart images are generated purely in memory (RAM) as bytes; no images are stored on disk.
"""

import os
import io
import base64
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Headless backend (no GUI, thread-safe)
import matplotlib.pyplot as plt
import seaborn as sns


def parse_csv_file(filepath: str) -> dict:
    """
    Reads CSV using Pandas and inspects columns, data types, missing values,
    and returns metadata and row preview for frontend display.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found at: {filepath}")

    df = pd.read_csv(filepath)
    df.columns = [str(c).strip() for c in df.columns]

    # Classify column types using NumPy and Pandas dtypes
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
    all_cols = df.columns.tolist()

    # Create safe preview (top 50 rows, NaN replaced with None for JSON serialization)
    preview_df = df.head(50).replace({np.nan: None})
    preview_records = preview_df.to_dict(orient='records')

    file_size_bytes = os.path.getsize(filepath)

    return {
        'total_rows': int(len(df)),
        'total_columns': int(len(df.columns)),
        'missing_values': int(df.isnull().sum().sum()),
        'columns': all_cols,
        'numeric_columns': numeric_cols,
        'categorical_columns': categorical_cols,
        'file_size': file_size_bytes,
        'preview_data': preview_records
    }


def generate_chart_image_bytes(
    filepath: str,
    x_axis: str,
    y_axis: str,
    chart_type: str = 'bar',
    palette: str = 'berry',
    is_dark: bool = True
) -> dict:
    """
    Performs Pandas & NumPy transformations and renders a Seaborn statistical plot.
    Returns the generated plot as an in-memory base64 byte string.
    NO IMAGE FILES ARE SAVED ON DISK.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Dataset file not found at: {filepath}")

    df = pd.read_csv(filepath)
    df.columns = [str(c).strip() for c in df.columns]

    if x_axis not in df.columns or y_axis not in df.columns:
        raise ValueError(f"Columns '{x_axis}' or '{y_axis}' not found in dataset.")

    # Data preprocessing with Pandas & NumPy
    df[y_axis] = pd.to_numeric(df[y_axis], errors='coerce')
    clean_df = df.dropna(subset=[x_axis, y_axis]).copy()

    if len(clean_df) == 0:
        raise ValueError("No valid numeric data found for selected axes after dropping NaN values.")

    # Direct data plotting without aggregation
    plot_df = clean_df.copy()

    # NumPy Statistical Analysis
    y_values_np = plot_df[y_axis].dropna().to_numpy()
    stats_summary = {
        'total_sum': float(np.sum(y_values_np)) if len(y_values_np) else 0.0,
        'mean': float(np.mean(y_values_np)) if len(y_values_np) else 0.0,
        'median': float(np.median(y_values_np)) if len(y_values_np) else 0.0,
        'std_dev': float(np.std(y_values_np)) if len(y_values_np) else 0.0,
        'min': float(np.min(y_values_np)) if len(y_values_np) else 0.0,
        'max': float(np.max(y_values_np)) if len(y_values_np) else 0.0,
        'count': int(len(y_values_np))
    }

    # Setup Matplotlib & Seaborn Styling
    plt.close('all')
    fig, ax = plt.subplots(figsize=(10, 5.5), dpi=140)

    if is_dark:
        bg_color = '#111827'
        fig_color = '#0b0f19'
        text_color = '#f8fafc'
        grid_color = '#1f293d'
        sns.set_theme(style="darkgrid", rc={
            'axes.facecolor': bg_color,
            'figure.facecolor': fig_color,
            'grid.color': grid_color,
            'text.color': text_color,
            'axes.labelcolor': text_color,
            'xtick.color': text_color,
            'ytick.color': text_color
        })
        fig.patch.set_facecolor(fig_color)
        ax.set_facecolor(bg_color)
    else:
        bg_color = '#ffffff'
        fig_color = '#f8fafc'
        text_color = '#0f172a'
        grid_color = '#e2e8f0'
        sns.set_theme(style="whitegrid", rc={
            'axes.facecolor': bg_color,
            'figure.facecolor': fig_color,
            'grid.color': grid_color,
            'text.color': text_color,
            'axes.labelcolor': text_color,
            'xtick.color': text_color,
            'ytick.color': text_color
        })
        fig.patch.set_facecolor(fig_color)
        ax.set_facecolor(bg_color)

    # Color palette mapping
    sns_palette_map = {
        'cyber': 'crest',
        'emerald': 'viridis',
        'sunset': 'flare',
        'berry': 'mako'
    }
    active_palette = sns_palette_map.get(palette, 'mako')

    chart_title = f"{y_axis} by {x_axis} ({chart_type.upper()})"

    # Render appropriate Seaborn visualization
    if chart_type == 'bar':
        sns.barplot(data=plot_df, x=x_axis, y=y_axis, ax=ax, palette=active_palette, hue=x_axis, legend=False)
        ax.tick_params(axis='x', rotation=35)

    elif chart_type in ['line', 'area']:
        sns.lineplot(data=plot_df, x=x_axis, y=y_axis, ax=ax, color='#38bdf8', marker='o', linewidth=2.5)
        if chart_type == 'area':
            ax.fill_between(range(len(plot_df)), plot_df[y_axis], color='#38bdf8', alpha=0.35)
        ax.tick_params(axis='x', rotation=35)

    elif chart_type == 'scatter':
        sns.scatterplot(data=plot_df, x=x_axis, y=y_axis, ax=ax, palette=active_palette, hue=x_axis, s=95, legend=False)
        ax.tick_params(axis='x', rotation=35)

    elif chart_type == 'box':
        sns.boxplot(data=clean_df, x=x_axis, y=y_axis, ax=ax, palette=active_palette, hue=x_axis, legend=False)
        ax.tick_params(axis='x', rotation=35)

    elif chart_type == 'violin':
        sns.violinplot(data=clean_df, x=x_axis, y=y_axis, ax=ax, palette=active_palette, hue=x_axis, legend=False)
        ax.tick_params(axis='x', rotation=35)

    elif chart_type == 'hist':
        sns.histplot(data=clean_df[y_axis], kde=True, ax=ax, color='#8b5cf6', bins=15)
        ax.set_xlabel(y_axis)

    elif chart_type in ['pie', 'doughnut']:
        ax.clear()
        positive_df = plot_df[plot_df[y_axis] > 0]
        pie_data = positive_df.sort_values(by=y_axis, ascending=False).head(8)
        if len(pie_data) == 0:
            pie_data = plot_df.head(8)
        colors = sns.color_palette(active_palette, len(pie_data))
        wedges, texts, autotexts = ax.pie(
            pie_data[y_axis],
            labels=pie_data[x_axis],
            autopct='%1.1f%%',
            colors=colors,
            startangle=140,
            wedgeprops=dict(width=0.45 if chart_type == 'doughnut' else 1.0, edgecolor=bg_color, linewidth=2)
        )
        for t in texts:
            t.set_color(text_color)
            t.set_fontsize(9)
        for at in autotexts:
            at.set_color('#ffffff')
            at.set_fontsize(9)
            at.set_weight('bold')

    ax.set_title(chart_title, fontsize=13, weight='bold', color=text_color, pad=15)
    if chart_type not in ['pie', 'doughnut', 'hist']:
        ax.set_xlabel(str(x_axis), fontsize=11, weight='bold', color=text_color)
        ax.set_ylabel(str(y_axis), fontsize=11, weight='bold', color=text_color)

    plt.tight_layout()

    # Capture plot in in-memory BytesIO buffer (NEVER SAVED TO DISK)
    image_buffer = io.BytesIO()
    plt.savefig(image_buffer, format='png', bbox_inches='tight', facecolor=fig.get_facecolor(), edgecolor='none')
    image_buffer.seek(0)
    image_bytes = image_buffer.getvalue()
    image_base64 = "data:image/png;base64," + base64.b64encode(image_bytes).decode('utf-8')

    plt.close(fig)

    # Series for client side if needed
    labels_list = [str(v) for v in plot_df[x_axis].tolist()]
    values_list = [float(v) if pd.notnull(v) else 0.0 for v in plot_df[y_axis].tolist()]

    return {
        'image_base64': image_base64,
        'chart_title': chart_title,
        'labels': labels_list,
        'values': values_list,
        'summary_stats': stats_summary,
        'engine': 'Pandas + NumPy + Seaborn (In-Memory Bytes Stream)'
    }


def delete_file_from_disk(filepath: str) -> bool:
    """
    Permanently deletes the uploaded CSV file from local disk.
    Called when user refreshes, closes frontend, or clears dataset.
    """
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False
    except Exception as e:
        print(f"Error deleting file {filepath}: {e}")
        return False
