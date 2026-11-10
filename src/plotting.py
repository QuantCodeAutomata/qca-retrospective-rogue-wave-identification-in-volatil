import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
from pathlib import Path
from scipy.signal import find_peaks


def figure1_style(
    raw_series: pd.Series,
    envelope: pd.Series,
    peak_df: pd.DataFrame,
    index_name: str,
    save_path: Path = None,
    raw_peak_df: pd.DataFrame = None,
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
    if raw_peak_df is not None and not raw_peak_df.empty:
        raw_major = raw_peak_df[raw_peak_df.severity == 'major']
        ax1.scatter(raw_major.date, raw_major.envelope_value, marker='x', color='grey',
                    s=24, alpha=0.6, label='Raw major (own raw SWH)')
    if index_name.split()[0] == 'VIX':
        ax1.axhline(35, color='grey', ls=':', lw=0.8, label='VIX = 35')
    ax1.set_ylabel(f'{index_name} Value')
    ax1.set_title(f'{index_name}: Raw Series vs Processed Envelope with Rogue-Wave Peaks')
    ax1.legend(fontsize=8)
    ax1.grid(True, alpha=0.3)
    if not peak_df.empty:
        # Calendar-width bars can become narrower than a pixel over decades.
        # Line widths remain visible without changing the dates or values.
        for severity, color, width in [('normal', 'steelblue', 0.5),
                                        ('lower', 'orange', 1.0), ('major', 'red', 1.2)]:
            group = peak_df[peak_df['severity'] == severity]
            ax2.vlines(group['date'], 0, group['prominence'], colors=color,
                       linewidths=width, alpha=0.8, label=severity)
        ax2.legend(fontsize=8)
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
    peaks, _ = find_peaks(raw_series.to_numpy(dtype=float))
    heights = raw_series.to_numpy(dtype=float)[peaks]
    if len(heights):
        sns.histplot(heights, bins=50, ax=ax, color='steelblue')
        ax.set_yscale('log')
    else:
        ax.text(0.5, 0.5, 'No interior peaks', ha='center', transform=ax.transAxes)
    if index_name.split()[0] == 'VIX':
        ax.axvline(35, color='orange', ls='--', label='VIX = 35')
        ax.legend()
    ax.set_xlabel(f'{index_name} Daily High at local peaks')
    ax.set_ylabel('Frequency')
    ax.set_title(f'{index_name}: Distribution of Raw Peak Heights')
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
        sns.histplot(peak_df['prominence'].values, bins=30, ax=ax, color='steelblue')
        ax.set_yscale('log')
        ax.axvline(peak_df['prominence'].mean(), color='grey', linestyle=':', label='Mean prominence')
    ax.axvline(swh, color='black', linestyle=':', label=f'SWH={swh:.2f}')
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
        if len(subset) > 1 and subset.nunique() > 1:
            sns.kdeplot(subset, label=f'{bin_label} days', color=palette.get(bin_label, 'grey'), ax=ax)
    metric_labels = {'width': 'Eigenvector width (time units)',
                     'loc_distance': 'Distance to window end (time units)',
                     'skewness': 'Potential skewness',
                     'kurtosis': 'Potential excess kurtosis'}
    ax.set_xlabel(metric_labels.get(metric, metric))
    ax.set_ylabel('Density')
    ax.set_title(f'{index_name}: {metric} by Days to Next Peak')
    handles, labels = ax.get_legend_handles_labels()
    if handles:
        ax.legend(title='Days to next peak')
    else:
        ax.text(0.5, 0.5, 'No eligible pre-peak groups for this sample',
                ha='center', va='center', transform=ax.transAxes)
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
    fig, ax = plt.subplots(figsize=(10, 6))
    if aligned.empty:
        ax.text(0.5, 0.5, 'No future labeled peaks in this sample',
                ha='center', va='center', transform=ax.transAxes)
    else:
        ax.scatter(aligned.iloc[:, 1], aligned.iloc[:, 0], alpha=0.4, s=15, color='steelblue')
    if gradient_cutoff is not None and not aligned.empty:
        ax.axhline(gradient_cutoff, color='red', linestyle='--', label=f'Cutoff={gradient_cutoff}')
    ax.set_xlabel('Days to Next Peak')
    ax.set_ylabel('|lambda_min| Gradient')
    ax.set_title(f'{index_name}: Eigenvalue Gradient vs Days to Next Major Peak')
    if gradient_cutoff is not None and not aligned.empty:
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
    fig, axes = plt.subplots(4, 1, figsize=(16, 14), sharex=True)
    # Panel 1: raw series + envelope + peaks
    ax1 = axes[0]
    ax1.plot(raw_series.index, raw_series.values, color='steelblue', alpha=0.5, lw=0.8, label='Raw High')
    ax1.plot(envelope.index, envelope.values, color='darkorange', lw=1.2, label='Envelope')
    if not peak_df.empty:
        major = peak_df[peak_df['severity'] == 'major']
        ax1.scatter(major['date'], major['envelope_value'], color='red', zorder=5, s=60, label='Major peaks')
        lower = peak_df[peak_df['severity'] == 'lower']
        ax1.scatter(lower.date, lower.envelope_value, marker='x', color='orange', s=45, label='Lower peaks')
    if insample_end and raw_series.index[0] <= pd.Timestamp(insample_end) <= raw_series.index[-1]:
        ax1.axvline(pd.Timestamp(insample_end), color='grey', linestyle=':', alpha=0.7, label='In/OOS split')
    ax1.set_ylabel(f'{index_name}')
    ax1.set_title(f'{index_name}: Series and Envelope')
    ax1.legend(fontsize=7)
    ax1.grid(True, alpha=0.3)
    strength_ax = axes[1]
    strength_ax.plot(warning_df.date, warning_df.M_i, color='steelblue', lw=0.8)
    strength_ax.set_ylabel('M_i (signed gradient)')
    strength_ax.set_title('Maximum gradient in the currently known block')
    strength_ax.grid(alpha=0.3)
    # Warning indicator W_i
    ax2 = axes[2]
    if not warning_df.empty:
        ax2.plot(warning_df['date'], warning_df['W_i'], color='purple', lw=1.0, label='W_i')
    ax2.axhline(threshold_warning, color='red', linestyle='--', label=f'Threshold={threshold_warning}')
    for sig in first_signals:
        ax2.axvline(sig, color='green', alpha=0.6, lw=0.8)
    if insample_end and raw_series.index[0] <= pd.Timestamp(insample_end) <= raw_series.index[-1]:
        ax2.axvline(pd.Timestamp(insample_end), color='grey', linestyle=':', alpha=0.7)
    ax2.set_ylabel('W_i')
    ax2.set_title(f'{index_name}: Warning Indicator W_i')
    ax2.legend(fontsize=7)
    ax2.grid(True, alpha=0.3)
    # Panel 3: first-signal markers on raw series
    ax3 = axes[3]
    ax3.plot(raw_series.index, raw_series.values, color='steelblue', alpha=0.7, lw=0.8)
    for sig in first_signals:
        ax3.axvline(sig, color='green', alpha=0.7, lw=1.0, label='First signal')
    if not peak_df.empty:
        major = peak_df[peak_df['severity'] == 'major']
        ax3.scatter(major['date'], raw_series.reindex(major['date']), color='red', zorder=5, s=60)
    ax3.set_ylabel(f'{index_name}')
    ax3.set_xlabel('Date')
    ax3.set_title(f'{index_name}: First Warning Signal Dates')
    ax3.grid(True, alpha=0.3)
    if insample_end and pd.Timestamp(insample_end) > raw_series.index[0]:
        shade_end = min(pd.Timestamp(insample_end), raw_series.index[-1])
        for ax in axes:
            ax.axvspan(raw_series.index[0], shade_end, color='grey', alpha=0.10)
    plt.tight_layout()
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()


def figure3_full_comparison(frame, index_name, cutoff, save_path):
    """Figure 3a-d content without guessing the article's visual normalization."""
    fig, axes = plt.subplots(2, 2, figsize=(17, 10))
    eligible = frame.dropna(subset=['days_to_next_peak'])
    for ax, column, title in [(axes[0, 0], 'grad_lambda', 'a) Minimum eigenvalue'),
                               (axes[0, 1], 'grad_sq_env', 'b) Squared envelope')]:
        ax.scatter(eligible.days_to_next_peak, eligible[column], s=6, alpha=0.35, color='black')
        if cutoff is not None:
            ax.axhline(cutoff, color='red', ls='--', label=f'Descriptive cutoff {cutoff:g}')
            ax.legend(fontsize=8)
        ax.set(xlabel='Observed sessions to next major peak', ylabel='Signed gradient', title=title)
        ax.grid(alpha=0.2)
    ax = axes[1, 0]
    ax.plot(frame.index, frame.envelope, color='grey', ls='--', lw=0.8, label='Envelope')
    right = ax.twinx()
    right.plot(frame.index, frame.negative_potential, color='black', lw=0.7, label='-U at window endpoint')
    right.plot(frame.index, frame.abs_lambda_min, color='red', lw=0.7, label='|minimum eigenvalue|')
    ax.set(ylabel='Index points', title='c) Envelope, potential and eigenvalue')
    right.set_ylabel('Squared index points / operator units')
    ax.legend(loc='upper left', fontsize=7); right.legend(loc='upper right', fontsize=7)
    ax = axes[1, 1]
    ax.plot(frame.index, frame.raw_high, color='grey', ls=':', lw=0.8, label='Raw High')
    right = ax.twinx()
    right.plot(frame.index, frame.grad_lambda, color='black', lw=0.7, label='Eigenvalue gradient')
    if cutoff is not None:
        right.axhline(cutoff, color='red', ls='--', lw=0.7, label=f'Cutoff {cutoff:g}')
    ax.set(ylabel='Index points', title='d) Raw High and eigenvalue gradient')
    right.set_ylabel('Signed gradient')
    ax.legend(loc='upper left', fontsize=7); right.legend(loc='upper right', fontsize=7)
    for ax in axes[1]:
        ax.tick_params(axis='x', labelrotation=25)
        ax.grid(alpha=0.2)
    fig.suptitle(f'{index_name}: Figure 3 diagnostics — full-history envelope, descriptive only')
    fig.tight_layout(); fig.savefig(save_path, dpi=150); plt.close(fig)
