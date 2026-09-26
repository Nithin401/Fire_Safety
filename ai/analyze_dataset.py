import argparse
import os
from preprocessing import clean_data
from features import extract_features
from anomaly_detection import calculate_baseline, detect_anomalies_zscore, detect_anomalies_isolation_forest
from risk_engine import run_risk_engine
from visualize import plot_analysis

def analyze(input_csv):
    print(f"Analyzing dataset: {input_csv}")
    
    # 1. Preprocessing
    df, report = clean_data(input_csv)
    print("\n--- DATA QUALITY REPORT ---")
    for k, v in report.items():
        print(f"{k}: {v}")
        
    if len(df) < 10:
        print("Not enough data to analyze.")
        return
        
    # 2. Features
    print("\nExtracting features...")
    df = extract_features(df)
    
    # 3. Baseline & Anomaly
    print("Calculating baseline and detecting anomalies...")
    df = calculate_baseline(df)
    df = detect_anomalies_zscore(df)
    df = detect_anomalies_isolation_forest(df)
    
    # 4. Risk Engine
    print("Running risk engine...")
    df = run_risk_engine(df)
    
    # 5. Visualization
    print("Generating plots...")
    plot_analysis(df)
    
    # Summary
    print("\n--- ANALYSIS SUMMARY ---")
    print(f"Total valid samples: {len(df)}")
    print(f"Duration: {df['pc_timestamp'].max() - df['pc_timestamp'].min()}")
    print(f"Flame Raw - Min: {df['flame_raw'].min()}, Max: {df['flame_raw'].max()}, Mean: {df['flame_raw'].mean():.2f}, Std: {df['flame_raw'].std():.2f}")
    if 'state' in df.columns:
        print("\nRisk State Distribution:")
        print(df['state'].value_counts())
        
    # Save processed data
    output_path = input_csv.replace(".csv", "_analyzed.csv")
    df.to_csv(output_path, index=False)
    print(f"\nAnalyzed dataset saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analyze a flame sensor dataset")
    parser.add_argument("--input", required=True, help="Path to input CSV file")
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"File not found: {args.input}")
    else:
        analyze(args.input)
