"""
Data Analysis and Visual Rendering Module
Handles Pandas and NumPy data manipulation and Seaborn/Matplotlib visualization.
Supports both CSV (.csv) and Excel (.xlsx, .xls) files.
Automatically handles categorical columns and frequency counts when no numeric column is present.
All chart images are generated purely in memory (RAM) as bytes; no images are stored on disk.
"""

import os
import io
import base64
import numpy as np
import pandas as pd
import matplotlib

matplotlib.use("Agg")  # Headless backend (no GUI, thread-safe)
import matplotlib.pyplot as plt
import seaborn as sns


def load_dataset(filepath: str) -> pd.DataFrame:
    """
    Loads dataset from either CSV (.csv) or Excel (.xlsx, .xls) formats.
    Strips whitespace from column names.
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found at: {filepath}")

    ext = os.path.splitext(filepath)[1].lower()
    if ext in [".xlsx", ".xls"]:
        df = pd.read_excel(filepath)
    else:
        df = pd.read_csv(filepath)

    df.columns = [str(c).strip() for c in df.columns]
    return df


def parse_csv_file(filepath: str) -> dict:
    """
    Reads CSV or Excel using Pandas and inspects columns, data types, missing values,
    and returns metadata and row preview for frontend display.
    """
    df = load_dataset(filepath)

    # Classify column types using NumPy and Pandas dtypes
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(exclude=[np.number]).columns.tolist()
    all_cols = df.columns.tolist()

    # Create safe preview (top 50 rows, NaN replaced with None for JSON serialization)
    preview_df = df.head(50).replace({np.nan: None})
    preview_records = preview_df.to_dict(orient="records")

    file_size_bytes = os.path.getsize(filepath)

    return {
        "total_rows": int(len(df)),
        "total_columns": int(len(df.columns)),
        "missing_values": int(df.isnull().sum().sum()),
        "columns": all_cols,
        "numeric_columns": numeric_cols,
        "categorical_columns": categorical_cols,
        "file_size": file_size_bytes,
        "preview_data": preview_records,
    }


def generate_chart_image_bytes(
    filepath: str,
    x_axis: str,
    y_axis: str,
    chart_type: str = "bar",
    palette: str = "berry",
    is_dark: bool = True,
) -> dict:
    """
    Performs Pandas & NumPy transformations and renders a Seaborn statistical plot.
    Intelligently supports both numeric values and categorical frequency counts (for checklists, status sheets, etc.).
    Returns the generated plot as an in-memory base64 byte string.
    NO IMAGE FILES ARE SAVED ON DISK.
    """
    df = load_dataset(filepath)

    if x_axis not in df.columns or y_axis not in df.columns:
        raise ValueError(f"Columns '{x_axis}' or '{y_axis}' not found in dataset.")

    # Drop rows where selected columns are missing
    clean_df = df.dropna(subset=[x_axis]).copy()
    if len(clean_df) == 0:
        raise ValueError(f"No valid rows found in dataset for column '{x_axis}'.")

    # Determine if Y-axis can be treated as numeric
    cleaned_y_str = (
        clean_df[y_axis].astype(str).str.replace(r"[\$,%]", "", regex=True).str.strip()
    )
    numeric_y = pd.to_numeric(cleaned_y_str, errors="coerce")
    valid_numeric_count = numeric_y.notnull().sum()

    is_numeric_y = (valid_numeric_count > 0) and (
        (valid_numeric_count / len(clean_df)) >= 0.35
    )

    if is_numeric_y:
        # Numeric metric mode
        clean_df["__metric__"] = numeric_y
        clean_df = clean_df.dropna(subset=["__metric__"]).copy()
        y_metric_col = "__metric__"
        y_display_label = y_axis
        mode_prefix = ""
        group_col = x_axis
        count_label = y_axis
    else:
        # Categorical / Text mode (e.g. checklists, logs, test scenarios):
        # Automatically compute Frequency Count by X-axis!
        # If X is ID-like (almost every value unique) every count would be 1
        # (flat chart), so group by the Y column instead: "Count of X by Y".
        x_nunique = clean_df[x_axis].nunique()
        y_nunique = clean_df[y_axis].dropna().nunique()
        if (
            x_axis != y_axis
            and x_nunique / len(clean_df) >= 0.9
            and 0 < y_nunique < x_nunique
        ):
            group_col = y_axis
            count_label = x_axis
            clean_df = clean_df.dropna(subset=[y_axis]).copy()
        else:
            group_col = x_axis
            count_label = y_axis
        counts_df = clean_df.groupby(group_col, as_index=False).size()
        counts_df.rename(columns={"size": "__metric__"}, inplace=True)
        clean_df = counts_df.copy()
        y_metric_col = "__metric__"
        y_display_label = f"Count ({count_label})"
        mode_prefix = "Count of "

    if len(clean_df) == 0:
        raise ValueError(
            f"No valid data to visualize for selected columns '{x_axis}' and '{y_axis}'."
        )

    # NumPy Statistical Analysis
    y_values_np = clean_df[y_metric_col].to_numpy()
    stats_summary = {
        "total_sum": float(np.sum(y_values_np)) if len(y_values_np) else 0.0,
        "mean": float(np.mean(y_values_np)) if len(y_values_np) else 0.0,
        "median": float(np.median(y_values_np)) if len(y_values_np) else 0.0,
        "std_dev": float(np.std(y_values_np)) if len(y_values_np) else 0.0,
        "min": float(np.min(y_values_np)) if len(y_values_np) else 0.0,
        "max": float(np.max(y_values_np)) if len(y_values_np) else 0.0,
        "count": int(len(y_values_np)),
    }

    # Intelligent data handling based on chart type & cardinality
    chart_note = ""
    plot_df = clean_df.copy()

    if chart_type in ["bar", "pie", "doughnut"]:
        # Aggregate duplicates by X-axis
        aggregated = clean_df.groupby(group_col, as_index=False)[y_metric_col].sum()
        aggregated = aggregated.sort_values(by=y_metric_col, ascending=False)

        # Keep Top 15 if there are many categories to avoid overlapping labels
        if len(aggregated) > 15:
            plot_df = aggregated.head(15).copy()
            chart_note = " (Top 15)"
        else:
            plot_df = aggregated.copy()

    elif chart_type in ["box", "violin"]:
        # If in categorical frequency count mode, fall back to bar plot
        if not is_numeric_y:
            chart_type = "bar"
            aggregated = (
                clean_df.groupby(group_col, as_index=False)[y_metric_col]
                .sum()
                .sort_values(by=y_metric_col, ascending=False)
            )
            plot_df = (
                aggregated.head(15).copy()
                if len(aggregated) > 15
                else aggregated.copy()
            )
        else:
            if clean_df[group_col].nunique() > 8:
                top_cats = clean_df[group_col].value_counts().head(8).index
                plot_df = clean_df[clean_df[group_col].isin(top_cats)].copy()
                chart_note = " (Top 8 Categories)"

    # Setup Matplotlib & Seaborn Styling
    plt.close("all")
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=110)

    if is_dark:
        bg_color = "#111827"
        fig_color = "#0b0f19"
        text_color = "#f8fafc"
        grid_color = "#1f293d"
        sns.set_theme(
            style="darkgrid",
            rc={
                "axes.facecolor": bg_color,
                "figure.facecolor": fig_color,
                "grid.color": grid_color,
                "text.color": text_color,
                "axes.labelcolor": text_color,
                "xtick.color": text_color,
                "ytick.color": text_color,
            },
        )
        fig.patch.set_facecolor(fig_color)
        ax.set_facecolor(bg_color)
    else:
        bg_color = "#ffffff"
        fig_color = "#f8fafc"
        text_color = "#0f172a"
        grid_color = "#e2e8f0"
        sns.set_theme(
            style="whitegrid",
            rc={
                "axes.facecolor": bg_color,
                "figure.facecolor": fig_color,
                "grid.color": grid_color,
                "text.color": text_color,
                "axes.labelcolor": text_color,
                "xtick.color": text_color,
                "ytick.color": text_color,
            },
        )
        fig.patch.set_facecolor(fig_color)
        ax.set_facecolor(bg_color)

    # Color palette mapping
    sns_palette_map = {
        "cyber": "crest",
        "emerald": "viridis",
        "sunset": "flare",
        "berry": "mako",
    }
    active_palette = sns_palette_map.get(palette, "mako")

    chart_title = (
        f"{mode_prefix}{count_label} by {group_col} ({chart_type.upper()}){chart_note}"
    )

    # Render appropriate Seaborn visualization
    if chart_type == "bar":
        sns.barplot(
            data=plot_df,
            x=group_col,
            y=y_metric_col,
            ax=ax,
            palette=active_palette,
            hue=group_col,
            legend=False,
        )
        ax.tick_params(axis="x", rotation=35)

    elif chart_type in ["line", "area"]:
        sns.lineplot(
            data=plot_df,
            x=group_col,
            y=y_metric_col,
            ax=ax,
            color="#38bdf8",
            marker="o",
            linewidth=2.2,
        )
        if chart_type == "area":
            ax.fill_between(
                range(len(plot_df)), plot_df[y_metric_col], color="#38bdf8", alpha=0.35
            )
        ax.tick_params(axis="x", rotation=35)
        if len(plot_df) > 30:
            ax.xaxis.set_major_locator(plt.MaxNLocator(15))

    elif chart_type == "scatter":
        sns.scatterplot(
            data=plot_df,
            x=group_col,
            y=y_metric_col,
            ax=ax,
            palette=active_palette,
            hue=group_col,
            s=90,
            legend=False,
        )
        ax.tick_params(axis="x", rotation=35)
        if len(plot_df) > 30:
            ax.xaxis.set_major_locator(plt.MaxNLocator(15))

    elif chart_type == "box":
        sns.boxplot(
            data=plot_df,
            x=group_col,
            y=y_metric_col,
            ax=ax,
            palette=active_palette,
            hue=group_col,
            legend=False,
        )
        ax.tick_params(axis="x", rotation=35)

    elif chart_type == "violin":
        sns.violinplot(
            data=plot_df,
            x=group_col,
            y=y_metric_col,
            ax=ax,
            palette=active_palette,
            hue=group_col,
            legend=False,
        )
        ax.tick_params(axis="x", rotation=35)

    elif chart_type == "hist":
        sns.histplot(
            data=clean_df[y_metric_col], kde=True, ax=ax, color="#8b5cf6", bins=15
        )
        ax.set_xlabel(str(y_display_label))

    elif chart_type in ["pie", "doughnut"]:
        ax.clear()
        positive_df = plot_df[plot_df[y_metric_col] > 0]
        pie_data = positive_df.sort_values(by=y_metric_col, ascending=False).head(8)
        if len(pie_data) == 0:
            pie_data = plot_df.head(8)
        colors = sns.color_palette(active_palette, len(pie_data))
        wedges, texts, autotexts = ax.pie(
            pie_data[y_metric_col],
            labels=pie_data[group_col],
            autopct="%1.1f%%",
            colors=colors,
            startangle=140,
            wedgeprops=dict(
                width=0.45 if chart_type == "doughnut" else 1.0,
                edgecolor=bg_color,
                linewidth=2,
            ),
        )
        for t in texts:
            t.set_color(text_color)
            t.set_fontsize(9)
        for at in autotexts:
            at.set_color("#ffffff")
            at.set_fontsize(9)
            at.set_weight("bold")

    ax.set_title(chart_title, fontsize=12, weight="bold", color=text_color, pad=12)
    if chart_type not in ["pie", "doughnut", "hist"]:
        ax.set_xlabel(str(group_col), fontsize=10, weight="bold", color=text_color)
        ax.set_ylabel(
            str(y_display_label), fontsize=10, weight="bold", color=text_color
        )

    # Make sure tick text uses the theme colour and category labels stay readable
    ax.tick_params(axis="both", colors=text_color, labelsize=9)
    if chart_type not in ["pie", "doughnut", "hist"]:
        for lbl in ax.get_xticklabels():
            lbl.set_rotation(40)
            lbl.set_ha("right")
            lbl.set_rotation_mode("anchor")

    # Format xticklabels so they don't overlap if still dense
    xticklabels = ax.get_xticklabels()
    if len(xticklabels) > 30:
        step = max(1, len(xticklabels) // 15)
        for i, lbl in enumerate(xticklabels):
            if i % step != 0:
                lbl.set_visible(False)

    plt.tight_layout()

    # Capture plot in in-memory BytesIO buffer (NEVER SAVED TO DISK)
    image_buffer = io.BytesIO()
    plt.savefig(
        image_buffer,
        format="png",
        bbox_inches="tight",
        facecolor=fig.get_facecolor(),
        edgecolor="none",
    )
    image_buffer.seek(0)
    image_bytes = image_buffer.getvalue()
    image_base64 = "data:image/png;base64," + base64.b64encode(image_bytes).decode(
        "utf-8"
    )

    plt.close(fig)

    # Series for client side if needed
    labels_list = [str(v) for v in plot_df[group_col].tolist()]
    values_list = [
        float(v) if pd.notnull(v) else 0.0 for v in plot_df[y_metric_col].tolist()
    ]

    return {
        "image_base64": image_base64,
        "chart_title": chart_title,
        "labels": labels_list,
        "values": values_list,
        "summary_stats": stats_summary,
        "engine": "Pandas + NumPy + Seaborn (In-Memory Bytes Stream)",
    }


def delete_file_from_disk(filepath: str) -> bool:
    """
    Permanently deletes the uploaded dataset file from local disk.
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
