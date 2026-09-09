import pandas as pd
import matplotlib.pyplot as plt
import os

def plot_analysis(df, save_dir="reports/plots"):
    os.makedirs(save_dir, exist_ok=True)
    
    time_axis = pd.to_datetime(df['pc_timestamp'])
    
    # 1. Raw vs Smoothed
    plt.figure(figsize=(12, 6))
    plt.plot(time_axis, df['flame_raw'], label='Raw Flame Signal', alpha=0.5)
    if 'rolling_mean' in df.columns:
        plt.plot(time_axis, df['rolling_mean'], label='Smoothed (Mean)', linewidth=2)
    plt.title('Flame Signal over Time')
    plt.xlabel('Time')
    plt.ylabel('Signal Value')
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(save_dir, '1_raw_vs_smoothed.png'))
    plt.close()
    
    # 2. Baseline and Deviation
    if 'baseline' in df.columns and 'deviation_from_baseline' in df.columns:
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
        ax1.plot(time_axis, df['flame_raw'], label='Raw')
        ax1.plot(time_axis, df['baseline'], label='Baseline', color='red', linestyle='--')
        ax1.set_title('Signal vs Baseline')
        ax1.legend()
        ax1.grid(True)
        
        ax2.plot(time_axis, df['deviation_from_baseline'], label='Deviation', color='orange')
        ax2.set_title('Deviation from Baseline')
        ax2.legend()
        ax2.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(save_dir, '2_baseline_deviation.png'))
        plt.close()
        
    # 3. Rate of change
    if 'first_derivative' in df.columns:
        plt.figure(figsize=(12, 4))
        plt.plot(time_axis, df['first_derivative'], color='purple')
        plt.title('Rate of Change (First Derivative)')
        plt.grid(True)
        plt.savefig(os.path.join(save_dir, '3_rate_of_change.png'))
        plt.close()
        
    # 4. Anomaly and Risk Score
    if 'risk_score' in df.columns:
        fig, ax1 = plt.subplots(figsize=(12, 6))
        ax1.plot(time_axis, df['risk_score'], color='red', label='Risk Score (0-100)')
        ax1.set_ylabel('Risk Score')
        ax1.axhline(85, color='darkred', linestyle='--', label='FIRE Threshold')
        ax1.axhline(60, color='orange', linestyle='--', label='HIGH RISK Threshold')
        ax1.axhline(30, color='yellow', linestyle='--', label='WARNING Threshold')
        
        if 'anomaly_score_if' in df.columns:
            ax2 = ax1.twinx()
            ax2.plot(time_axis, df['anomaly_score_if'], color='gray', alpha=0.5, label='Anomaly Score')
            ax2.set_ylabel('Anomaly Score')
            
        plt.title('Risk Score and Anomalies')
        ax1.legend(loc='upper left')
        plt.grid(True)
        plt.savefig(os.path.join(save_dir, '4_risk_and_anomaly.png'))
        plt.close()
        
    print(f"Plots saved to {save_dir}/")
