"""
FireShield AI — Processed Dataset Compiler

Compiles raw session CSV files from data/real and data/synthetic into a clean,
versioned, schema-validated master dataset (Parquet and CSV).
Preserves raw data immutability. Generates data summary report.
"""

import os
import argparse
import datetime
import pandas as pd
from ai.data_validation import validate_dataframe

def build_processed_dataset(raw_dirs: list[str], output_dir: str = "data/processed/v1", version: str = "1.0"):
    os.makedirs(output_dir, exist_ok=True)
    
    valid_dfs = []
    synthetic_count = 0
    real_count = 0
    session_ids = set()
    
    for r_dir in raw_dirs:
        if not os.path.exists(r_dir):
            continue
        for root, _, files in os.walk(r_dir):
            for file in files:
                if file.endswith('.csv'):
                    filepath = os.path.join(root, file)
                    try:
                        df = pd.read_csv(filepath)
                        valid, errors = validate_dataframe(df, file)
                        if valid:
                            valid_dfs.append(df)
                            source = df['data_source'].iloc[0]
                            if source == 'synthetic':
                                synthetic_count += 1
                            else:
                                real_count += 1
                            session_ids.add(df['sessionId'].iloc[0])
                        else:
                            print(f"[SKIP] Invalid file {file}: {errors[0]}")
                    except Exception as e:
                        print(f"[SKIP] Error reading {file}: {e}")
                        
    if not valid_dfs:
        print("[ERROR] No valid dataframes collected.")
        return None
        
    master_df = pd.concat(valid_dfs, ignore_index=True)
    master_df['timestamp'] = pd.to_datetime(master_df['timestamp'])
    master_df = master_df.sort_values(by=['sessionId', 'timestamp']).reset_index(drop=True)
    
    # Save versioned artifacts
    parquet_path = os.path.join(output_dir, "dataset.parquet")
    csv_path = os.path.join(output_dir, "dataset.csv")
    
    master_df.to_parquet(parquet_path, index=False)
    master_df.to_csv(csv_path, index=False)
    print(f"[SUCCESS] Compiled {len(master_df)} rows across {len(session_ids)} sessions into {output_dir}")
    
    # Generate Data Summary Report
    template_path = "docs/data_summary_template.md"
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
            
        counts = master_df['label'].value_counts()
        c_norm = counts.get('NORMAL', 0)
        c_fire = counts.get('FIRE', 0)
        c_false = counts.get('FALSE_ALARM', 0)
        total = len(master_df)
        
        synth_rows = len(master_df[master_df['data_source'] == 'synthetic'])
        real_rows = len(master_df[master_df['data_source'] == 'real'])
        
        summary_md = template.format(
            version=version,
            generation_time=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            total_rows=total,
            total_sessions=len(session_ids),
            min_date=str(master_df['timestamp'].min()),
            max_date=str(master_df['timestamp'].max()),
            count_normal=c_norm,
            pct_normal=(c_norm / total) * 100 if total > 0 else 0,
            count_fire=c_fire,
            pct_fire=(c_fire / total) * 100 if total > 0 else 0,
            count_false=c_false,
            pct_false=(c_false / total) * 100 if total > 0 else 0,
            flame_min=int(master_df['flameRaw'].min()),
            flame_mean=float(master_df['flameRaw'].mean()),
            flame_max=int(master_df['flameRaw'].max()),
            flame_std=float(master_df['flameRaw'].std()),
            temp_min=float(master_df['tempC'].min()),
            temp_mean=float(master_df['tempC'].mean()),
            temp_max=float(master_df['tempC'].max()),
            temp_std=float(master_df['tempC'].std()),
            hum_min=float(master_df['humidity'].min()),
            hum_mean=float(master_df['humidity'].mean()),
            hum_max=float(master_df['humidity'].max()),
            hum_std=float(master_df['humidity'].std()),
            gas_min=int(master_df['gasRaw'].min()),
            gas_mean=float(master_df['gasRaw'].mean()),
            gas_max=int(master_df['gasRaw'].max()),
            gas_std=float(master_df['gasRaw'].std()),
            smoke_min=int(master_df['smokeRaw'].min()),
            smoke_mean=float(master_df['smokeRaw'].mean()),
            smoke_max=int(master_df['smokeRaw'].max()),
            smoke_std=float(master_df['smokeRaw'].std()),
            synthetic_sessions=synthetic_count,
            synthetic_rows=synth_rows,
            real_sessions=real_count,
            real_rows=real_rows
        )
        
        summary_out = os.path.join(output_dir, "data_summary.md")
        with open(summary_out, 'w', encoding='utf-8') as f:
            f.write(summary_md)
        print(f"[SUCCESS] Wrote data summary report to {summary_out}")
        
    return master_df

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build Processed Dataset")
    parser.add_argument("--output-dir", type=str, default="data/processed/v1")
    parser.add_argument("--version", type=str, default="1.0")
    args = parser.parse_args()
    
    build_processed_dataset(
        raw_dirs=["data/real", "data/synthetic"],
        output_dir=args.output_dir,
        version=args.version
    )
