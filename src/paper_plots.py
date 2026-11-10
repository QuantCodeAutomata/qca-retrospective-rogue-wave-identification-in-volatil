"""Plots of saved descriptive diagnostic values; no numerical fitting here."""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def _finish(fig, path, title, synthetic=False):
    if synthetic:
        title += " [SYNTHETIC TEST]"
    fig.suptitle(title + "\nDescriptive reconstruction; conventions are documented", fontsize=11)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, dpi=140, bbox_inches="tight")
    plt.close(fig)


def correlation(table, index_name, path, synthetic=False):
    fig, ax = plt.subplots(figsize=(8, 4.7))
    ax.plot(table["lag_observations"], table["pearson_r"], color="navy")
    ax.axvline(0, color="grey", lw=0.7)
    ax.axhline(0, color="grey", lw=0.7)
    ax.set(xlabel="Lag in observed sessions (positive = future High)", ylabel="Pearson r")
    ax.grid(alpha=0.2)
    if not table["pearson_r"].notna().any():
        ax.text(0.5, 0.5, "No defined correlations; see counts/statuses in CSV", ha="center", transform=ax.transAxes)
    _finish(fig, path, f"Figure 5: {index_name}, corr(M_i, High[i+lag]), M_i > 0.0001", synthetic)


def aftershocks(windows, log_frame, metadata, path, synthetic=False):
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    for anchor, ax in zip(("2008-10-13", "2020-03-16", "2011-08-09"),
                           (axes[0, 0], axes[1, 0], axes[1, 1])):
        ax.set_title(anchor)
        if anchor not in windows:
            ax.text(0.5, 0.5, metadata["windows"][anchor]["reason"].replace("_", " "),
                    ha="center", transform=ax.transAxes)
            continue
        data = windows[anchor]
        t = data["observations_since_anchor"]
        ax.step(t, data["cumulative_count"], where="post", label="N(t)", color="royalblue")
        if data["fitted_count"].notna().any():
            ax.plot(t, data["fitted_count"], label="Integrated Omori fit", color="firebrick")
            fit = metadata["windows"][anchor]["fit"]
            r2 = "undefined" if fit["r_squared"] is None else f'{fit["r_squared"]:.3f}'
            ax.text(0.03, 0.93, f'R²={r2}; p={fit["p"]:.3g}, c={fit["c"]:.3g}\n{fit["status"]}',
                    transform=ax.transAxes, fontsize=7, va="top")
        else:
            ax.text(0.03, 0.93, metadata["windows"][anchor]["fit"]["status"], transform=ax.transAxes)
        right = ax.twinx()
        right.plot(t, data["high"], color="grey", alpha=0.5, linewidth=0.8)
        right.set_ylabel("VIX High", color="grey")
        ax.set(xlabel="Observed sessions after fixed anchor", ylabel="Cumulative selected raw peaks")
        ax.legend(fontsize=7)
    ax = axes[0, 1]
    ax.set_title("2008: fixed global-index log-linear fit")
    if log_frame is None:
        ax.text(0.5, 0.5, metadata["log_index_fit"]["status"], ha="center", transform=ax.transAxes)
    else:
        ax.scatter(log_frame["log_index"], log_frame["log_envelope"], s=7, label="Envelope", color="darkorange")
        ax.plot(log_frame["log_index"], log_frame["fitted_log_envelope"], label="OLS fit", color="navy")
        fit = metadata["log_index_fit"]
        r2 = "undefined" if fit["r_squared"] is None else f'{fit["r_squared"]:.3f}'
        ax.text(0.97, 0.95, f'slope={fit["slope"]:.3g}\nR²={r2}',
                transform=ax.transAxes, fontsize=8, va="top", ha="right")
        ax.legend(fontsize=7)
    ax.set(xlabel="ln(global observed index, 1-based)", ylabel="ln(envelope)")
    _finish(fig, path, "Supplement S1: raw-prominence aftershocks (explicit interpretation)", synthetic)


def increments(histograms, path, synthetic=False):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8))
    for representation, ax in zip(("raw", "standardized"), axes):
        panel = histograms.loc[histograms["representation"] == representation]
        for lag, group in panel.groupby("lag_observations", sort=True):
            centers = (group["bin_left"].to_numpy() + group["bin_right"].to_numpy()) / 2
            density = group["probability_density"].to_numpy()
            ax.plot(centers, np.where(density > 0, density, np.nan), label=f"{lag} sessions", linewidth=1)
        ax.set_yscale("log")
        ax.set(xlabel="Envelope difference" if representation == "raw" else "(Difference - mean) / std (ddof=0)",
               ylabel="Probability density", title=representation.title())
        if len(panel):
            ax.legend(fontsize=7)
        else:
            ax.text(0.5, 0.5, "No defined distributions", ha="center", transform=ax.transAxes)
    _finish(fig, path, "Supplement S2: envelope increments; 100 shared bins per panel", synthetic)


def _raw_axis(ax, highs, year):
    data = highs.loc[highs.index.year == year]
    ax.plot(data.index, data.to_numpy(), color="grey", alpha=0.6, linewidth=0.8)
    ax.set_ylabel("Daily High")
    ax.grid(alpha=0.2)
    right = ax.twinx()
    return right


def received_and_event(highs, windows, label, threshold, path, synthetic=False):
    years = (2018, 2020) if label == "S3" else (2020,)
    fig, axes = plt.subplots(len(years), 2, figsize=(13, 4 * len(years)), squeeze=False)
    for row, year in enumerate(years):
        for ax in axes[row]:
            ax.tick_params(axis="x", labelrotation=25)
        if year not in windows:
            for ax in axes[row]:
                ax.text(0.5, 0.5, f"{year}: no warning rows", ha="center", transform=ax.transAxes)
            continue
        data = windows[year]
        right = _raw_axis(axes[row, 0], highs, year)
        column = "C_i" if label == "S3" else "W_i"
        right.plot(data["date"], data[column], color="darkorange", linewidth=1, label=f"{column} received")
        if label == "S4":
            right.axhline(threshold, color="navy", linestyle="--", linewidth=0.8, label="Warning threshold")
        right.set_ylabel(column)
        right.legend(fontsize=7, loc="upper right")
        axes[row, 0].set_title(f"{year}: {'gradient count' if label == 'S3' else 'warning strength'} at receipt")
        right = _raw_axis(axes[row, 1], highs, year)
        right.scatter(data["date"], data["M_i"], color="firebrick", s=9, alpha=0.6, label="M_i at signal_date")
        # Every received row remains a separate observation, even where several
        # explanatory event dates coincide. Neither series is a trade timestamp.
        right.scatter(data["event_date"], data["M_i"], color="navy", marker="x", s=12, alpha=0.5,
                      label="Same M_i at explanatory event_date")
        right.set_ylabel("M_i: maximum gradient")
        right.legend(fontsize=7, loc="upper right")
        axes[row, 1].set_title(f"{year}: event date versus receipt (all rows retained)")
    _finish(fig, path, f"Supplement {label}: explanatory event dates are not availability dates", synthetic)
