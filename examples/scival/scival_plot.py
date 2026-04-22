"""Generate area-level comparison charts from SciVal author CSV output."""

from __future__ import annotations

import csv
import re
from pathlib import Path

import matplotlib.pyplot as plt


def _to_int(raw_value: str) -> int:
    """Convert formatted numeric text to int.

    Args:
        raw_value: String that may include commas and spaces.

    Returns:
        Integer value, or 0 for an empty string.

    """
    cleaned = raw_value.replace(',', '').strip()
    return int(cleaned) if cleaned else 0


def _to_float(raw_value: str) -> float:
    """Convert formatted numeric text to float.

    Args:
        raw_value: String that may include commas and spaces.

    Returns:
        Floating-point value, or 0.0 for an empty string.

    """
    cleaned = raw_value.replace(',', '').strip()
    return float(cleaned) if cleaned else 0.0


def _chunk_sequence(items: list[str], chunk_size: int) -> list[list[str]]:
    """Split a list into equally sized chunks.

    Args:
        items: Items to chunk.
        chunk_size: Maximum number of items per chunk.

    Returns:
        Chunked list of items.

    """
    return [items[index : index + chunk_size] for index in range(0, len(items), chunk_size)]


def export_area_comparison_plots(csv_path: Path, chart_dir: Path, top_n: int = 10) -> list[Path]:
    """Export area-level institution comparison charts from the author CSV.

    Each chart uses a faceted small-multiples layout with one subplot per institution.
    Every subplot shares the same rank axis and y-axis scales to support cross-school
    comparison inside the same area.

    Args:
        csv_path: Parsed author CSV path.
        chart_dir: Output directory for generated figures.
        top_n: Number of top-ranked authors per institution to display.

    Returns:
        List of generated chart paths.

    """
    chart_dir.mkdir(parents=True, exist_ok=True)

    with csv_path.open(encoding='utf-8', newline='') as file:
        reader = csv.DictReader(file)
        rows = list(reader)

    rows = [row for row in rows if row.get('rank', '').isdigit() and int(row['rank']) <= top_n]

    area_to_rows: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        area = row.get('area', '').strip()
        if not area:
            continue
        area_to_rows.setdefault(area, []).append(row)

    generated_paths: list[Path] = []
    rank_labels = list(range(1, top_n + 1))
    max_facets_per_page = 6

    for area, area_rows in sorted(area_to_rows.items()):
        institutions = sorted({row['institute'] for row in area_rows})
        if not institutions:
            continue

        # Prioritize University of Nottingham to first position
        nottingham = 'University of Nottingham'
        if nottingham in institutions:
            institutions.remove(nottingham)
            institutions.insert(0, nottingham)

        safe_area = re.sub(r'[^a-zA-Z0-9]+', '_', area.strip().lower()).strip('_')
        area_rows_by_institute: dict[str, list[dict[str, str]]] = {}
        for row in area_rows:
            institute = row['institute'].strip()
            if institute:
                area_rows_by_institute.setdefault(institute, []).append(row)

        area_output_series: dict[int, float] = {}
        area_h_index_series: dict[int, float] = {}
        for rank in rank_labels:
            rank_rows = [row for row in area_rows if row['rank'].isdigit() and int(row['rank']) == rank]
            if rank_rows:
                area_output_series[rank] = sum(
                    _to_int(row.get('scholarly_output_count', '0')) for row in rank_rows
                ) / len(rank_rows)
                area_h_index_series[rank] = sum(_to_float(row.get('h_index', '0')) for row in rank_rows) / len(
                    rank_rows
                )
            else:
                area_output_series[rank] = 0.0
                area_h_index_series[rank] = 0.0

        output_max = max(
            [area_output_series[rank] for rank in rank_labels]
            + [_to_int(row.get('scholarly_output_count', '0')) for row in area_rows]
        )
        h_index_max = max(
            [area_h_index_series[rank] for rank in rank_labels]
            + [_to_float(row.get('h_index', '0')) for row in area_rows]
        )

        cmap = plt.get_cmap('tab10')
        institution_chunks = _chunk_sequence(institutions, max_facets_per_page)

        for page_index, institution_chunk in enumerate(institution_chunks, start=1):
            rows_count = 2
            cols_count = 3
            fig_width = 4.2 * cols_count
            fig_height = 3.2 * rows_count
            fig, axes = plt.subplots(
                rows_count,
                cols_count,
                figsize=(fig_width, fig_height),
                dpi=300,
                sharex=True,
                sharey=True,
            )
            flat_axes = list(axes.flat)

            for axis_index, ax_left in enumerate(flat_axes):
                if axis_index >= len(institution_chunk):
                    ax_left.axis('off')
                    continue

                institution = institution_chunk[axis_index]
                institution_rows = area_rows_by_institute[institution]
                rank_to_row = {int(row['rank']): row for row in institution_rows if row['rank'].isdigit()}

                scholarly_output_series = [
                    _to_int(rank_to_row.get(rank, {}).get('scholarly_output_count', '0')) for rank in rank_labels
                ]
                h_index_series = [_to_float(rank_to_row.get(rank, {}).get('h_index', '0')) for rank in rank_labels]

                accent_color = cmap(axis_index % cmap.N)
                background_color = '#d9d9d9'

                area_bar = ax_left.bar(
                    rank_labels,
                    [area_output_series[rank] for rank in rank_labels],
                    width=0.72,
                    color=background_color,
                    alpha=0.55,
                    edgecolor='none',
                )
                author_bar = ax_left.bar(
                    rank_labels,
                    scholarly_output_series,
                    width=0.44,
                    color=accent_color,
                    alpha=0.92,
                    edgecolor='none',
                )
                ax_left.text(
                    0.5,
                    -0.20,
                    institution,
                    transform=ax_left.transAxes,
                    ha='center',
                    va='top',
                )
                ax_left.set_xticks(rank_labels)
                ax_left.grid(axis='y', linestyle='--', alpha=0.22)
                ax_left.set_xlim(0.5, top_n + 0.5)
                ax_left.set_ylim(0, max(1.0, output_max * 1.08))

                ax_right = ax_left.twinx()
                h_index_line = ax_right.plot(
                    rank_labels,
                    h_index_series,
                    color=accent_color,
                    linewidth=1.7,
                    marker='o',
                    markersize=3.0,
                    markeredgecolor='white',
                    markeredgewidth=1.0,
                )[0]
                ax_right.set_ylim(0, max(1.0, h_index_max * 1.08))

                if axis_index == 0:
                    ax_left.legend(
                        [area_bar, author_bar, h_index_line],
                        ['Area avg output', 'Scholarly output', 'H-index'],
                        frameon=True,
                        facecolor='white',
                        framealpha=0.8,
                    )

                col_position = axis_index % cols_count
                if col_position == 0:
                    ax_left.tick_params(axis='y', left=True, labelleft=True)
                    ax_right.tick_params(axis='y', right=False, labelright=False)
                elif col_position == cols_count - 1:
                    ax_left.tick_params(axis='y', left=False, labelleft=False)
                    ax_right.tick_params(axis='y', right=True, labelright=True)
                else:
                    ax_left.tick_params(axis='y', left=False, labelleft=False)
                    ax_right.tick_params(axis='y', right=False, labelright=False)
                ax_left.tick_params(axis='x', bottom=True, labelbottom=True)

            fig.suptitle(
                f'SciVal Top Authors by Rank | Area: {area} | Page {page_index}/{len(institution_chunks)}',
            )
            fig.text(
                0.02,
                0.50,
                'Scholarly Output Count',
                va='center',
                ha='left',
                rotation=90,
                color='#333333',
            )
            fig.text(
                0.98,
                0.50,
                'h-index',
                va='center',
                ha='right',
                rotation=-90,
                color='#333333',
            )
            fig.text(
                0.5,
                0.012,
                'Gray background bars show the area average. Blue bars and lines show each institution.',
                ha='center',
                color='#555555',
            )
            fig.tight_layout(rect=(0.05, 0.10, 0.95, 0.93))

            page_suffix = '' if len(institution_chunks) == 1 else f'_part{page_index:02d}'
            output_path = chart_dir / f'scival_top_authors_{safe_area}{page_suffix}.png'
            fig.savefig(output_path, bbox_inches='tight')
            plt.close(fig)
            generated_paths.append(output_path)

    return generated_paths
