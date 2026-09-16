"""
FireShield AI — Multi-Sensor Visualization & Baseline Report Generator

Generates comprehensive multi-panel engineering plots:
- Panel 1: Multi-channel Raw Signals (Flame, Temp, Gas, Smoke)
- Panel 2: Flame Raw vs Dynamic Baseline & Deviation
- Panel 3: First Derivatives (Rates of Change)
- Panel 4: Z-Scores, Fusion Confidence & Risk Score
"""

import os
import argparse
import pandas as pd
import matplotlib.pyplot as plt

def generate_baseline_report_plot(features_path: str = "data/features/v1/features.parquet",
                                  output_path: str = "docs/reports/baseline_analysis.png",
                                  session_to_plot: str = None):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    if features_path.endswith('.parquet'):
        df = pd.read_parquet(features_path)
    else:
        df = pd.read_csv(features_path)
        
    if session_to_plot is None:
        # Pick the first FIRE session to show the complete baseline -> spike -> recovery
        fire_sessions = df[df['label'] == 'FIRE']['sessionId'].unique()
        session_to_plot = fire_sessions[0] if len(fire_sessions) > 0 else df['sessionId'].iloc[0]
        
    session_df = df[df['sessionId'] == session_to_plot].sort_values(by='timestamp').reset_index(drop=True)
    time_idx = range(len(session_df))
    
    fig, axes = plt.subplots(4, 1, figsize=(14, 12), sharex=True)
    fig.suptitle(f"FireShield AI — Multi-Sensor Baseline & Anomaly Analysis\nSession: {session_to_plot}", fontsize=14, fontweight='bold')
    
    # Panel 1: Multi-Channel Raw Signals
    ax1 = axes[0]
    ax1.plot(time_idx, session_df['flameRaw'], label='Flame IR (ADC)', color='#d9534f', linewidth=2)
    ax1.set_ylabel('Flame ADC (0-1023)', color='#d9534f')
    ax1.tick_params(axis='y', labelcolor='#d9534f')
    ax1.grid(True, alpha=0.3)
    
    ax1_twin = ax1.twinx()
    ax1_twin.plot(time_idx, session_df['tempC'], label='Temp (°C)', color='#f0ad4e', linewidth=1.5, linestyle='--')
    ax1_twin.plot(time_idx, session_df['gasRaw'], label='Gas (ADC)', color='#5cb85c', linewidth=1.5, linestyle=':')
    ax1_twin.set_ylabel('Temp (°C) / Gas (ADC)', color='#333333')
    ax1.set_title('Raw Multi-Sensor Input Signals', fontsize=11)
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax1_twin.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper left')
    
    # Panel 2: Flame vs Rolling Median Baseline & Deviation
    ax2 = axes[1]
    ax2.plot(time_idx, session_df['flameRaw'], label='Flame Raw', color='#d9534f', alpha=0.6)
    if 'flame_baseline' in session_df.columns:
        ax2.plot(time_idx, session_df['flame_baseline'], label='Rolling Baseline (Median W=50)', color='#0275d8', linewidth=2, linestyle='--')
    if 'deviation_from_baseline' in session_df.columns:
        ax2.plot(time_idx, session_df['deviation_from_baseline'], label='Baseline Deviation (Δ)', color='#9c27b0', linewidth=1.5)
    ax2.set_ylabel('ADC / Deviation')
    ax2.set_title('Environmental Baseline Tracking & Signal Deviation', fontsize=11)
    ax2.legend(loc='lower left')
    ax2.grid(True, alpha=0.3)
    
    # Panel 3: Rates of Change (First Derivatives)
    ax3 = axes[2]
    if 'first_derivative' in session_df.columns:
        ax3.plot(time_idx, session_df['first_derivative'], label='Flame Velocity (d/dt)', color='#6f42c1', linewidth=1.5)
    if 'temp_roc' in session_df.columns:
        ax3.plot(time_idx, session_df['temp_roc'] * 10.0, label='Temp ROC x10', color='#fd7e14', linewidth=1.5, linestyle='--')
    ax3.set_ylabel('Rate of Change')
    ax3.set_title('First Derivative Dynamics (Thermal & Optical Velocities)', fontsize=11)
    ax3.legend(loc='lower left')
    ax3.grid(True, alpha=0.3)
    
    # Panel 4: Sensor Fusion & Confidence Indicators
    ax4 = axes[3]
    if 'fusion_confidence_score' in session_df.columns:
        ax4.plot(time_idx, session_df['fusion_confidence_score'] * 100.0, label='Fusion Confidence (%)', color='#28a745', linewidth=2)
    if 'anomaly_flag_zscore' in session_df.columns:
        ax4.scatter(time_idx, session_df['anomaly_flag_zscore'] * 90.0, label='Z-Score Anomaly Trigger', color='red', marker='x', s=40)
    ax4.axhline(85, color='darkred', linestyle='--', alpha=0.5, label='FIRE Alert Threshold')
    ax4.axhline(60, color='orange', linestyle='--', alpha=0.5, label='HIGH RISK Threshold')
    ax4.set_ylabel('Confidence / Score (%)')
    ax4.set_xlabel('Sample Index (Seconds)')
    ax4.set_title('Cross-Sensor Fusion Confidence & Statistical Anomaly Flags', fontsize=11)
    ax4.legend(loc='upper left')
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()
    print(f"[SUCCESS] Multi-panel baseline analysis report generated: {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Baseline & Anomaly Report Generator")
    parser.add_argument("--features", type=str, default="data/features/v1/features.parquet")
    parser.add_argument("--output", type=str, default="docs/reports/baseline_analysis.png")
    parser.add_argument("--session", type=str, default=None)
    args = parser.parse_args()
    
    generate_baseline_report_plot(
        features_path=args.features,
        output_path=args.output,
        session_to_plot=args.session
    )
