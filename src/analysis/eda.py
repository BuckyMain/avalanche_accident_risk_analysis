"""Exploratory analysis: accident-day rates and core Kennzahlen plots."""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.paths import FIGURES, PROCESSED


def accident_rate_by(df: pd.DataFrame, by: str | list[str]) -> pd.DataFrame:
    """Compute accident-day rates grouped by one or more columns.

    Groups ``region_day`` rows by ``by`` and returns:

    - ``n_region_days``: number of region-day observations
    - ``n_accident_days``: sum of ``accident_occurred``
    - ``rate``: accident days / region-days
    """

    g = (
        df.groupby(by, dropna=False)
        .agg(
            n_region_days=("accident_occurred", "size"),
            n_accident_days=("accident_occurred", "sum"),
        )
        .reset_index()
    )
    g["rate"] = g["n_accident_days"] / g["n_region_days"]
    return g


def kennzahlen_summaries(
    df: pd.DataFrame,
    *,
    top_n_regions: int = 10,
    print_tables: bool = True,
) -> dict[str, pd.DataFrame]:
    """Required first-slice Kennzahlen from ``region_day``.

    Returns rate tables for danger level, weekend vs weekday, and the
    top ``top_n_regions`` major regions by accident-day rate.
    """

    by_danger = accident_rate_by(
        df.dropna(subset=["danger_level"]),
        "danger_level",
    ).sort_values("danger_level")

    by_weekend = accident_rate_by(df, "is_weekend").sort_values("is_weekend")

    by_major = (
        accident_rate_by(df.dropna(subset=["major_region"]), "major_region")
        .sort_values("rate", ascending=False)
        .head(top_n_regions)
        .reset_index(drop=True)
    )

    summaries = {
        "by_danger_level": by_danger,
        "by_is_weekend": by_weekend,
        "by_major_region_top": by_major,
    }

    if print_tables:
        print("=== Rate by danger_level ===")
        print(by_danger.to_string(index=False))
        print("\n=== Rate by is_weekend ===")
        print(by_weekend.to_string(index=False))
        print(f"\n=== Top {top_n_regions} rates by major_region ===")
        print(by_major.to_string(index=False))

    return summaries


def plot_rate_by_danger(df: pd.DataFrame, out: Path | None = None) -> Path:
    """Bar chart: accident-day rate vs forecast danger level."""

    FIGURES.mkdir(parents=True, exist_ok=True)
    out = out or FIGURES / "eda_rate_by_danger.png"

    rates = accident_rate_by(
        df.dropna(subset=["danger_level"]),
        "danger_level",
    ).sort_values("danger_level")

    fig, ax = plt.subplots(figsize=(7, 4))
    ax.bar(
        rates["danger_level"].astype(int).astype(str),
        rates["rate"],
        color="#c0392b",
    )
    ax.set_xlabel("Danger level")
    ax.set_ylabel("Accident-day rate")
    ax.set_title("Accident probability per region-day by danger level")
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def plot_weekend_effect(df: pd.DataFrame, out: Path | None = None) -> Path:
    """Line chart: weekday vs weekend accident-day rate by danger level."""

    FIGURES.mkdir(parents=True, exist_ok=True)
    out = out or FIGURES / "eda_weekend_effect.png"

    rates = accident_rate_by(
        df.dropna(subset=["danger_level"]),
        ["danger_level", "is_weekend"],
    ).sort_values(["is_weekend", "danger_level"])

    fig, ax = plt.subplots(figsize=(8, 4))
    for weekend, label, color in [
        (0, "Weekday", "#2980b9"),
        (1, "Weekend", "#e67e22"),
    ]:
        sub = rates[rates["is_weekend"] == weekend]
        ax.plot(
            sub["danger_level"],
            sub["rate"],
            marker="o",
            label=label,
            color=color,
        )
    ax.set_xlabel("Danger level")
    ax.set_ylabel("Accident-day rate")
    ax.set_title("Weekend vs weekday accident rate by danger level")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out, bbox_inches="tight")
    plt.close(fig)
    return out


def run_kennzahlen(
    region_day: pd.DataFrame | None = None,
    *,
    top_n_regions: int = 10,
) -> dict[str, pd.DataFrame]:
    """Load ``region_day``, print Kennzahlen, and write the two core plots."""

    if region_day is None:
        path = PROCESSED / "region_day.parquet"
        if not path.exists():
            raise FileNotFoundError(
                f"Missing {path}. Run src.analysis.integrate.build_integrated_tables first."
            )
        region_day = pd.read_parquet(path)

    summaries = kennzahlen_summaries(
        region_day,
        top_n_regions=top_n_regions,
        print_tables=True,
    )
    danger_path = plot_rate_by_danger(region_day)
    weekend_path = plot_weekend_effect(region_day)
    print(f"\nWrote {danger_path}")
    print(f"Wrote {weekend_path}")
    return summaries


if __name__ == "__main__":
    run_kennzahlen()
