import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import numpy as np
import pandas as pd
from pathlib import Path

RESULTS_DIR = Path('results')


def figure1_style(
    raw_series: pd.Series,
    envelope: pd.Series,
    peak_df: pd.DataFrame,
    index_name: str,
    save_path: Path = None
) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(15, 8), sharex=True)
    ax1, ax2 = axes
    ax1.plot(raw_series.index, raw_series.values, color='steelblue', alpha=0.6, linewidth=0.8, label='Raw High')
    ax1.plot(envelope.index, envelope.values, color='darkorange', linewidth=1.5, label='Processed Envelope')
    if not peak_df.empty:
        major = peak_df[peak_df['severity'] == 'major']
        lower = peak_df[peak_df['severity'] == 'lower']
        ax1.scatter(major['date'], major['envelope_value'], color='red', zorder=5, s=60, label='Major (>2.5 SWH)')
        ax1.scatter(lower['date'], lower['envelope_value'], color='orange', zorder=4, s=40, label='Lower (>2 SWH)')
        for _, row in major.iterrows():
            ax1.annotate(str(row['date'].year), (row['date'], row['envelope_value']),
                        textcoords='offset points', xytext=(0, 5), fontsize=7, color='red')
    ax1.set_ylabel(f'{index_name} Value')
    ax1.set_title(f'{index_name}: Raw Series vs Processed Envelope with Rogue-Wave Peaks')
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)
    if not peak_df.empty:
        ax2.bar(peak_df['date'], peak_df['prominence'],
                color=peak_df['severity'].map({'major': 'red', 'lower': 'orange', 'normal': 'steelblue'}),
                alpha=0.7)
    ax2.set_ylabel('Peak Prominence')
    ax2.set_xlabel('Date')
    ax2.set_title(f'{index_name}: Peak Prominences by Severity')
    ax2.grid(True, alpha=0.3)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()


def histogram_raw_peaks(
    raw_series: pd.Series,
    index_name: str,
    save_path: Path = None
) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.histplot(raw_series.values, bins=50, kde=True, ax=ax, color='steelblue')
    ax.set_xlabel(f'{index_name} Daily High')
    ax.set_ylabel('Frequency')
    ax.set_title(f'{index_name}: Distribution of Daily High Values')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()


def histogram_prominences(
    peak_df: pd.DataFrame,
    swh: float,
    index_name: str,
    save_path: Path = None
) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    if not peak_df.empty:
        sns.histplot(peak_df['prominence'].values, bins=30, kde=True, ax=ax, color='steelblue')
    ax.axvline(2.0 * swh, color='orange', linestyle='--', label=f'2×SWH={2*swh:.2f}')
    ax.axvline(2.5 * swh, color='red', linestyle='--', label=f'2.5×SWH={2.5*swh:.2f}')
    ax.set_xlabel('Peak Prominence')
    ax.set_ylabel('Count')
    ax.set_title(f'{index_name}: Histogram of Envelope Peak Prominences')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()


def figure2_style_density(
    diagnostic_df: pd.DataFrame,
    metric: str,
    index_name: str,
    save_path: Path = None
) -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    palette = {'0-5': 'red', '5-30': 'orange', '>30': 'steelblue'}
    bins_order = ['0-5', '5-30', '>30']
    for bin_label in bins_order:
        subset = diagnostic_df[diagnostic_df['bin_label'] == bin_label][metric].dropna()
        if len(subset) > 1:
            sns.kdeplot(subset, label=f'{bin_label} days', color=palette.get(bin_label, 'grey'), ax=ax)
    ax.set_xlabel(metric)
    ax.set_ylabel('Density')
    ax.set_title(f'{index_name}: {metric} by Days to Next Peak')
    ax.legend(title='Days to next peak')
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()


def figure3_style_scatter(
    grad_series: pd.Series,
    days_to_peak: pd.Series,
    index_name: str,
    gradient_cutoff: float = None,
    save_path: Path = None
) -> None:
    aligned = pd.concat([grad_series, days_to_peak], axis=1).dropna()
    if aligned.empty:
        return
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.scatter(aligned.iloc[:, 1], aligned.iloc[:, 0], alpha=0.4, s=15, color='steelblue')
    if gradient_cutoff is not None:
        ax.axhline(gradient_cutoff, color='red', linestyle='--', label=f'Cutoff={gradient_cutoff}')
    ax.set_xlabel('Days to Next Peak')
    ax.set_ylabel('|lambda_min| Gradient')
    ax.set_title(f'{index_name}: Eigenvalue Gradient vs Days to Next Major Peak')
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()


def figure_warning_indicator(
    raw_series: pd.Series,
    envelope: pd.Series,
    peak_df: pd.DataFrame,
    warning_df: pd.DataFrame,
    first_signals: pd.DatetimeIndex,
    threshold_warning: float,
    index_name: str,
    insample_end: str = None,
    save_path: Path = None
) -> None:
    fig, axes = plt.subplots(3, 1, figsize=(16, 12), sharex=True)
    # Panel 1: raw series + envelope + peaks
    ax1 = axes[0]
    ax1.plot(raw_series.index, raw_series.values, color='steelblue', alpha=0.5, lw=0.8, label='Raw High')
    ax1.plot(envelope.index, envelope.values, color='darkorange', lw=1.2, label='Envelope')
    if not peak_df.empty:
        major = peak_df[peak_df['severity'] == 'major']
        ax1.scatter(major['date'], major['envelope_value'], color='red', zorder=5, s=60, label='Major peaks')
    if insample_end:
        ax1.axvline(pd.Timestamp(insample_end), color='grey', linestyle=':', alpha=0.7, label='In/OOS split')
    ax1.set_ylabel(f'{index_name}')
    ax1.set_title(f'{index_name}: Series and Envelope')
    ax1.legend(fontsize=7)
    ax1.grid(True, alpha=0.3)
    # Panel 2: warning indicator W_i
    ax2 = axes[1]
    if not warning_df.empty:
        ax2.plot(warning_df['date'], warning_df['W_i'], color='purple', lw=1.0, label='W_i')
    ax2.axhline(threshold_warning, color='red', linestyle='--', label=f'Threshold={threshold_warning}')
    for sig in first_signals:
        ax2.axvline(sig, color='green', alpha=0.6, lw=0.8)
    if insample_end:
        ax2.axvline(pd.Timestamp(insample_end), color='grey', linestyle=':', alpha=0.7)
    ax2.set_ylabel('W_i')
    ax2.set_title(f'{index_name}: Warning Indicator W_i')
    ax2.legend(fontsize=7)
    ax2.grid(True, alpha=0.3)
    # Panel 3: first-signal markers on raw series
    ax3 = axes[2]
    ax3.plot(raw_series.index, raw_series.values, color='steelblue', alpha=0.7, lw=0.8)
    for sig in first_signals:
        ax3.axvline(sig, color='green', alpha=0.7, lw=1.0, label='First signal')
    if not peak_df.empty:
        major = peak_df[peak_df['severity'] == 'major']
        ax3.scatter(major['date'], raw_series.reindex(major['date'], method='nearest'), color='red', zorder=5, s=60)
    ax3.set_ylabel(f'{index_name}')
    ax3.set_xlabel('Date')
    ax3.set_title(f'{index_name}: First Warning Signal Dates')
    ax3.grid(True, alpha=0.3)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
