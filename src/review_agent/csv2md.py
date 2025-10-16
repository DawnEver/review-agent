import argparse
import csv
import re
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path


def read_csv(path: Path, *, delimiter: str = ',', encoding: str = 'utf-8-sig') -> tuple[list[dict], list[str]]:
    with path.open('r', encoding=encoding, newline='') as f:
        reader = csv.DictReader(f, delimiter=delimiter, skipinitialspace=True)
        headers = list(reader.fieldnames or [])
        rows = [dict(row) for row in reader]
    return rows, headers


def _escape_md(text: object) -> str:
    s = '' if text is None else str(text)
    return s.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br>').replace('|', '\\|')


def _select_columns(headers: list[str], wanted: Iterable[str] | None) -> list[str]:
    if not wanted:
        return headers
    cols: list[str] = []
    hmap = {h.lower(): h for h in headers}
    for w in (x.strip() for x in wanted if x and x.strip()):
        key = w.lower()
        if key in hmap:
            cols.append(hmap[key])
            continue
        norm = re.sub(r'[^a-z0-9]', '', key)
        for h in headers:
            if re.sub(r'[^a-z0-9]', '', h.lower()) == norm:
                cols.append(h)
                break
    return cols or headers


def make_markdown_table(rows: Sequence[Mapping[str, object]], headers: Sequence[str]) -> str:
    lines = [
        f'| {" | ".join(_escape_md(h) for h in headers)} |',
        f'| {" | ".join(["---"] * len(headers))} |',
    ]
    lines.extend(f'| {" | ".join(_escape_md(r.get(h, "")) for h in headers)} |' for r in rows)
    return '\n'.join(lines) + '\n'


def rows_to_markdown(
    rows: list[dict],
    headers: list[str],
    *,
    columns: list[str] | None = None,
    sort_by: str | None = None,
    descending: bool = False,
    max_rows: int | None = None,
) -> str:
    cols = _select_columns(headers, columns)
    data = list(rows)
    if sort_by and sort_by in headers:
        data.sort(key=lambda r: (r.get(sort_by) is None, str(r.get(sort_by))), reverse=descending)
    if max_rows is not None:
        data = data[:max_rows]
    return make_markdown_table(data, cols)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='Convert CSV to Markdown table')
    p.add_argument('-i', '--input', required=True, help='Input CSV file')
    p.add_argument('-o', '--output', help='Output .md file path')
    p.add_argument('-c', '--columns', help='Comma-separated columns to include')
    p.add_argument('--delimiter', default=',', help='CSV delimiter')
    p.add_argument('--encoding', default='utf-8-sig', help='CSV encoding')
    p.add_argument('--sort-by', help='Sort column')
    p.add_argument('--desc', action='store_true', help='Sort descending')
    p.add_argument('--max-rows', type=int, help='Limit rows')
    return p


def main(argv: Sequence[str] | None = None) -> int:
    p = _build_parser()
    ns = p.parse_args(argv)

    in_path = Path(ns.input)
    if not in_path.exists():
        msg = f'Input CSV not found: {in_path}'
        raise FileNotFoundError(msg)

    rows, headers = read_csv(in_path, delimiter=ns.delimiter, encoding=ns.encoding)
    out_path = Path(ns.output) if ns.output else in_path.with_suffix('.md')

    cols = [c.strip() for c in ns.columns.split(',')] if ns.columns else None
    md = rows_to_markdown(rows, headers, columns=cols, sort_by=ns.sort_by, descending=ns.desc, max_rows=ns.max_rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(md, encoding='utf-8')
    return 0


def cli() -> None:
    raise SystemExit(main())


if __name__ == '__main__':
    cli()
