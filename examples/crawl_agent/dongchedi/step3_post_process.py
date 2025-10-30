# ruff: noqa: T201
import sys
from pathlib import Path

import pandas as pd


def main():
    input_path = Path(
        'C:/Users/linxu/OneDrive - The University of Nottingham/PEMC/251006-Ferrari_Future_Traction_PhD_Program/review/Companies/Dongchedi/tables/top_ev_brands-models.xlsx'
    )
    if not input_path.exists():
        print(f'Error: input file does not exist: {input_path}')
        sys.exit(1)

    # Read Excel
    try:
        df = pd.read_excel(input_path, sheet_name=0)
    except Exception as e:  # noqa: BLE001
        print(f'Failed to read Excel: {e}')
        sys.exit(1)

    # List columns
    cols_all = list(df.columns)

    # Columns to keep
    cols_input = [
        'car_id',
        '厂商',
        'car_name',
        '官方指导价',
        '级别',
        '能源类型',
        '上市时间',
        '电动机描述',
        '电机',
        '驱动电机数',
        '电机布局',
        '最大功率(kW)',
        '最大扭矩(N·m)',
        '电动机总功率(kW)',
        '电动机总马力(Ps)',
        '电动机总扭矩(N·m)',
        '前电动机最大功率(kW)',
        '前电动机最大扭矩(N·m)',
        '后电动机最大功率(kW)',
        '后电动机最大扭矩(N·m)',
        '纯电续航里程(km)工信部',
        '纯电续航里程(km)CLTC',
    ]

    # Validate columns
    missing = [c for c in cols_input if c not in cols_all]
    if missing:
        print('The following columns were not found in the sheet:', missing)
        sys.exit(1)

    # Select and save
    df_selected = df[cols_input]

    output_path = Path('output/selected_cols.xlsx')
    if not output_path.suffix:
        output_path = output_path.with_suffix('.xlsx')

    df_selected.to_excel(output_path, index=False)

    print(f'Saved {len(df_selected)} rows, {len(df_selected.columns)} columns to: {output_path}')


if __name__ == '__main__':
    main()
