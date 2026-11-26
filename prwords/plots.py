"""Charts. One idea per figure, thin marks, quiet grid, text in neutral ink."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

INK = "#1f2933"
MUTED = "#6b7785"
GRID = "#e4e7eb"
SURFACE = "#ffffff"
BLUE = "#2a78d6"
ORANGE = "#eb6834"
AQUA = "#1baf7a"


def _x(monthly: pd.DataFrame) -> pd.Series:
    return pd.to_datetime(monthly["month"]) + pd.Timedelta(days=14)


def _style(ax, ylabel: str | None = None, title: str | None = None) -> None:
    ax.set_axisbelow(True)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=MUTED, length=0, labelsize=9)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK, fontsize=9.5)
    if title:
        ax.set_title(title, loc="left", color=INK, fontsize=10.5, fontweight="bold")


def _line(ax, monthly, col, color=BLUE, ci=None, band=None, label=None):
    x = _x(monthly)
    y = monthly[col]
    if band:
        ax.fill_between(x, monthly[band[0]], monthly[band[1]], color=color, alpha=0.12, linewidth=0)
    if ci:
        ax.fill_between(x, monthly[ci[0]], monthly[ci[1]], color=color, alpha=0.28, linewidth=0)
    ax.plot(x, y, color=color, linewidth=2, label=label)
    full = ~monthly["partial"]
    ax.plot(x[full], y[full], "o", color=color, markersize=5, markeredgecolor=SURFACE, markeredgewidth=1.4)
    ax.plot(x[~full], y[~full], "o", markerfacecolor=SURFACE, markeredgecolor=color, markersize=5,
            markeredgewidth=1.4)


def _save(fig, path: Path) -> None:
    fig.savefig(path, dpi=200, bbox_inches="tight", facecolor=SURFACE)
    plt.close(fig)


def _footer(fig, text: str) -> None:
    fig.text(0.01, -0.01, text, color=MUTED, fontsize=8, ha="left", va="top")


def plot_words(monthly: pd.DataFrame, repo: str, path: Path) -> None:
    fig, (ax, ax2) = plt.subplots(2, 1, figsize=(10, 6.2), sharex=True,
                                  gridspec_kw={"height_ratios": [3.2, 1], "hspace": 0.08})
    _line(ax, monthly, "median_words", ci=("median_words_ci_low", "median_words_ci_high"),
          band=("p25_words", "p75_words"), label="Median")
    ax.set_ylim(bottom=0)
    _style(ax, "Words per description\n(non-empty, template removed)",
           f"{repo}: pull request description length by month")
    ax.fill_between([], [], [], color=BLUE, alpha=0.12, label="Middle 50% of PRs")
    ax.fill_between([], [], [], color=BLUE, alpha=0.28, label="95% interval for median")
    ax.legend(frameon=False, loc="upper left", labelcolor=MUTED, fontsize=9)
    ax2.bar(_x(monthly), monthly["n_prs"], width=20, color=MUTED, alpha=0.55)
    _style(ax2, "PRs opened")
    _footer(fig, "Hollow markers are partial months.")
    _save(fig, path)


def plot_size(monthly: pd.DataFrame, repo: str, path: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True, gridspec_kw={"hspace": 0.12})
    _line(axes[0], monthly, "median_files_changed", ci=("median_files_changed_ci_low", "median_files_changed_ci_high"))
    axes[0].set_ylim(bottom=0)
    _style(axes[0], "Median files changed", f"{repo}: size of pull requests by month")
    _line(axes[1], monthly, "median_churn", ci=("median_churn_ci_low", "median_churn_ci_high"), color=BLUE)
    axes[1].set_yscale("log")
    _style(axes[1], "Median lines changed\n(added + deleted, log scale)")
    _footer(fig, "Bands are 95% bootstrap intervals for the median. Hollow markers are partial months.")
    _save(fig, path)


def plot_flow(monthly: pd.DataFrame, repo: str, path: Path) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(10, 6.4), sharex=True, gridspec_kw={"hspace": 0.12})
    _line(axes[0], monthly, "merge_rate")
    axes[0].set_ylim(0, 1)
    axes[0].yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0))
    _style(axes[0], "Share of PRs merged", f"{repo}: merge rate and time to merge by month")
    _line(axes[1], monthly, "median_hours_to_merge",
          ci=("median_hours_to_merge_ci_low", "median_hours_to_merge_ci_high"))
    axes[1].set_yscale("log")
    _style(axes[1], "Median hours to merge\n(merged PRs, log scale)")
    _footer(fig, "Recent months can understate merge rate because PRs are still open. Hollow markers are partial months.")
    _save(fig, path)


def plot_labels(monthly: pd.DataFrame, cat_names: list[str], repo: str, path: Path) -> None:
    n = len(cat_names)
    cols = 3
    rows = int(np.ceil(n / cols))
    fig, axes = plt.subplots(rows, cols, figsize=(11, 2.6 * rows), sharex=True, squeeze=False,
                             gridspec_kw={"hspace": 0.45, "wspace": 0.25})
    for ax, name in zip(axes.flat, cat_names):
        _line(ax, monthly, f"share_{name}")
        ax.set_ylim(bottom=0)
        ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=0))
        _style(ax, None, name.replace("_", " "))
        ax.tick_params(axis="x", labelrotation=45)
    for ax in list(axes.flat)[n:]:
        ax.set_visible(False)
    fig.suptitle(f"{repo}: share of PRs carrying each label category", x=0.01, ha="left", color=INK,
                 fontsize=12, fontweight="bold", y=1.0)
    _footer(fig, "A PR can carry several categories. Hollow markers are partial months.")
    _save(fig, path)


def plot_ai_signals(monthly: pd.DataFrame, repo: str, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(10, 4))
    _line(ax, monthly, "share_ai_disclosed")
    ax.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1.0, decimals=1))
    _style(ax, "PRs naming an AI tool", f"{repo}: PRs that name an AI tool, by month")
    ax.set_ylim(bottom=0)
    _footer(fig, "A proxy. It does not show who or what wrote a description. Hollow markers are partial months.")
    _save(fig, path)


def plot_effects(effects: pd.DataFrame, repo: str, path: Path) -> None:
    ok = effects[effects["status"] == "ok"]
    exposures = list(dict.fromkeys(effects["exposure"]))
    colors = {"M1 month effects": BLUE, "M2 plus description length": ORANGE, "M3 same author": AQUA}
    fig, axes = plt.subplots(1, len(exposures), figsize=(5.8 * len(exposures), 4.8), sharey=True, squeeze=False)
    outcomes = list(dict.fromkeys(effects["label"]))
    ypos = {o: i for i, o in enumerate(outcomes[::-1])}
    offsets = {"M1 month effects": 0.22, "M2 plus description length": 0.0, "M3 same author": -0.22}
    for ax, exp in zip(axes.flat, exposures):
        sub = ok[ok["exposure"] == exp]
        for model, color in colors.items():
            s = sub[sub["model"] == model]
            y = [ypos[l] + offsets[model] for l in s["label"]]
            ax.errorbar(s["pct_difference"], y, xerr=[s["pct_difference"] - s["ci_low"], s["ci_high"] - s["pct_difference"]],
                        fmt="o", color=color, markersize=5, linewidth=1.4, capsize=0, label=model)
        ax.axvline(0, color=MUTED, linewidth=1)
        ax.set_yticks(list(ypos.values()))
        ax.set_yticklabels(list(ypos.keys()))
        n_e = int(effects.loc[effects["exposure"] == exp, "n_exposed"].max())
        _style(ax, None, f"{exp.replace('_', ' ')} (n = {n_e:,} exposed)")
        ax.grid(axis="x", color=GRID, linewidth=0.8)
        ax.grid(axis="y", visible=False)
        ax.set_xlabel("Difference versus other PRs (%)", color=INK, fontsize=9.5)
    axes.flat[0].legend(frameon=False, loc="lower left", labelcolor=MUTED, fontsize=8.5)
    fig.suptitle(f"{repo}: size and speed of flagged PRs versus others", x=0.01, ha="left",
                 color=INK, fontsize=12, fontweight="bold", y=1.02)
    _footer(fig, "Points are percentage differences in (1 + outcome) with 95% intervals clustered by author. Left of zero means smaller or faster.")
    _save(fig, path)
