"""
visualizations.py — ProfMatch: Generate all figures for the final report.
Run from the project root where profmatch.db lives.
"""

import sqlite3
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns
from sklearn.decomposition import TruncatedSVD

# ── styling ──────────────────────────────────────────────────────────────────
PALETTE = ["#2C3E7A", "#4A90D9", "#6DB8F2", "#A8D4F5", "#D0E9FB"]
sns.set_theme(style="whitegrid", font_scale=1.05)
plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.dpi": 150,
})

os.makedirs("figures", exist_ok=True)

# ── connect ───────────────────────────────────────────────────────────────────
conn = sqlite3.connect("profmatch.db")


def fig_rating_distribution():
    df = pd.read_sql("SELECT rating, COUNT(*) AS cnt FROM rating GROUP BY rating ORDER BY rating", conn)
    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(df["rating"].astype(str), df["cnt"], color=PALETTE[1], edgecolor="white", linewidth=0.8)
    for bar, val in zip(bars, df["cnt"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                str(val), ha="center", va="bottom", fontsize=9, color="#333")
    ax.set_xlabel("Star Rating (1 = Lowest, 5 = Highest)", labelpad=8)
    ax.set_ylabel("Number of Ratings")
    ax.set_title("Fig 1 — Distribution of Student Ratings", fontweight="bold", pad=12)
    ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    plt.tight_layout()
    plt.savefig("figures/fig1_rating_distribution.png", bbox_inches="tight")
    plt.close()
    print("Saved fig1_rating_distribution.png")



def fig_top_professors():
    query = """
        SELECT p.professor_name,
               ROUND(AVG(r.rating), 2) AS avg_rating,
               COUNT(r.rating_id)      AS num_ratings
        FROM professor p
        JOIN section s  ON p.professor_id = s.professor_id
        JOIN rating r   ON s.section_id   = r.section_id
        GROUP BY p.professor_id
        HAVING num_ratings >= 3
        ORDER BY avg_rating DESC
        LIMIT 10
    """
    df = pd.read_sql(query, conn)
    fig, ax = plt.subplots(figsize=(8, 5))
    colors = [PALETTE[0] if v >= df["avg_rating"].median() else PALETTE[2]
              for v in df["avg_rating"]]
    bars = ax.barh(df["professor_name"][::-1], df["avg_rating"][::-1],
                   color=colors[::-1], edgecolor="white")
    for bar, val in zip(bars, df["avg_rating"][::-1]):
        ax.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height() / 2,
                f"{val:.2f}", va="center", fontsize=8.5, color="#333")
    ax.set_xlim(0, 5.4)
    ax.set_xlabel("Average Rating (out of 5)")
    ax.set_title("Fig 2 — Top 10 Professors by Average Rating\n(min. 3 ratings)", fontweight="bold", pad=12)
    ax.axvline(x=df["avg_rating"].mean(), color="#E74C3C", linestyle="--",
               linewidth=1.2, label=f"Global mean: {df['avg_rating'].mean():.2f}")
    ax.legend(fontsize=8)
    plt.tight_layout()
    plt.savefig("figures/fig2_top_professors.png", bbox_inches="tight")
    plt.close()
    print("Saved fig2_top_professors.png")


def fig_sparsity_heatmap():
    query = """
        SELECT r.student_id, p.professor_id, p.professor_name, r.rating
        FROM rating r
        JOIN section s ON r.section_id = s.section_id
        JOIN professor p ON s.professor_id = p.professor_id
    """
    df = pd.read_sql(query, conn)
    matrix = df.pivot_table(index="student_id", columns="professor_name",
                            values="rating", aggfunc="mean")

    # Subset: top 30 students (most ratings) × all professors
    rated_counts = matrix.notna().sum(axis=1).sort_values(ascending=False)
    sub = matrix.loc[rated_counts.head(30).index]

    fig, ax = plt.subplots(figsize=(12, 6))
    mask = sub.isna()
    # Show rated cells as colored, unrated as light grey
    display = sub.copy()
    sns.heatmap(display, mask=mask, cmap="Blues", vmin=1, vmax=5,
                linewidths=0.4, linecolor="#eee",
                cbar_kws={"label": "Rating", "shrink": 0.6},
                ax=ax, annot=False)
    # Grey out missing
    sns.heatmap(display.isna(), mask=~mask, cmap=["#F0F0F0"],
                linewidths=0.4, linecolor="#eee", cbar=False, ax=ax)

    ax.set_xlabel("Professor", labelpad=8)
    ax.set_ylabel("Student ID (Top 30 by activity)", labelpad=8)
    ax.set_title("Fig 3 — Interaction Matrix: Rated Cells (colored) vs. Missing (grey)\n"
                 "Illustrates extreme data sparsity inherent to the dataset",
                 fontweight="bold", pad=12)
    ax.tick_params(axis="x", rotation=45, labelsize=7)
    ax.tick_params(axis="y", labelsize=7)
    plt.tight_layout()
    plt.savefig("figures/fig3_sparsity_heatmap.png", bbox_inches="tight")
    plt.close()
    print("Saved fig3_sparsity_heatmap.png")



def fig_ratings_per_student():
    df = pd.read_sql("""
        SELECT student_id, COUNT(*) AS cnt FROM rating GROUP BY student_id
    """, conn)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.hist(df["cnt"], bins=range(1, df["cnt"].max() + 2), color=PALETTE[1],
            edgecolor="white", align="left")
    ax.set_xlabel("Number of Ratings Submitted per Student")
    ax.set_ylabel("Number of Students")
    ax.set_title("Fig 4 — Ratings per Student\n(Most students rated very few professors)",
                 fontweight="bold", pad=12)
    median_val = df["cnt"].median()
    ax.axvline(median_val, color="#E74C3C", linestyle="--",
               linewidth=1.2, label=f"Median: {median_val:.0f}")
    ax.legend(fontsize=9)
    plt.tight_layout()
    plt.savefig("figures/fig4_ratings_per_student.png", bbox_inches="tight")
    plt.close()
    print("Saved fig4_ratings_per_student.png")



def fig_svd_explained_variance():
    query = """
        SELECT r.student_id, p.professor_id, r.rating
        FROM rating r
        JOIN section s ON r.section_id = s.section_id
        JOIN professor p ON s.professor_id = p.professor_id
    """
    df = pd.read_sql(query, conn)
    matrix = df.pivot_table(index="student_id", columns="professor_id",
                            values="rating", aggfunc="mean").fillna(0)

    max_k = min(matrix.shape[1] - 1, 15)
    ev = []
    for k in range(1, max_k + 1):
        svd = TruncatedSVD(n_components=k, random_state=42)
        svd.fit(matrix)
        ev.append(svd.explained_variance_ratio_.sum())

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(range(1, max_k + 1), [e * 100 for e in ev],
            marker="o", color=PALETTE[0], linewidth=2, markersize=5)
    ax.axvline(2, color="#E74C3C", linestyle="--", linewidth=1.2,
               label="k=2 used (data constraint)")
    ax.set_xlabel("Number of Latent Factors (k)")
    ax.set_ylabel("Cumulative Explained Variance (%)")
    ax.set_title("Fig 5 — SVD: Cumulative Explained Variance by k\n"
                 "Low k forced by sparse matrix; more data would enable richer decomposition",
                 fontweight="bold", pad=12)
    ax.legend(fontsize=9)
    ax.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.0f%%"))
    plt.tight_layout()
    plt.savefig("figures/fig5_svd_explained_variance.png", bbox_inches="tight")
    plt.close()
    print("Saved fig5_svd_explained_variance.png")



def fig_latent_factor_scatter():
    query = """
        SELECT r.student_id, p.professor_id, r.rating
        FROM rating r
        JOIN section s ON r.section_id = s.section_id
        JOIN professor p ON s.professor_id = p.professor_id
    """
    df = pd.read_sql(query, conn)
    matrix = df.pivot_table(index="student_id", columns="professor_id",
                            values="rating", aggfunc="mean").fillna(0)
    svd = TruncatedSVD(n_components=2, random_state=42)
    coords = svd.fit_transform(matrix)

    # Color by average rating
    avg_rating = df.groupby("student_id")["rating"].mean().reindex(matrix.index)

    fig, ax = plt.subplots(figsize=(7, 5))
    sc = ax.scatter(coords[:, 0], coords[:, 1],
                    c=avg_rating, cmap="coolwarm", alpha=0.75,
                    edgecolors="white", linewidths=0.4, s=60)
    plt.colorbar(sc, ax=ax, label="Avg Rating Given by Student")
    ax.set_xlabel("Latent Factor 1")
    ax.set_ylabel("Latent Factor 2")
    ax.set_title("Fig 6 — Student Latent Factor Space (SVD, k=2)\n"
                 "Students colored by average rating they assign",
                 fontweight="bold", pad=12)
    plt.tight_layout()
    plt.savefig("figures/fig6_latent_scatter.png", bbox_inches="tight")
    plt.close()
    print("Saved fig6_latent_scatter.png")



def fig_grade_distribution():
    df = pd.read_sql("""
        SELECT final_grade, COUNT(*) AS cnt FROM enrollment
        WHERE final_grade IS NOT NULL
        GROUP BY final_grade ORDER BY cnt DESC
    """, conn)
    order = ["A", "A-", "B+", "B", "C+", "C"]
    df["final_grade"] = pd.Categorical(df["final_grade"], categories=order, ordered=True)
    df = df.sort_values("final_grade")

    fig, ax = plt.subplots(figsize=(6, 4))
    bars = ax.bar(df["final_grade"].astype(str), df["cnt"],
                  color=PALETTE[:len(df)], edgecolor="white")
    for bar, val in zip(bars, df["cnt"]):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 1,
                str(val), ha="center", fontsize=9, color="#333")
    ax.set_xlabel("Final Grade")
    ax.set_ylabel("Number of Enrollments")
    ax.set_title("Fig 7 — Grade Distribution Across Sections", fontweight="bold", pad=12)
    plt.tight_layout()
    plt.savefig("figures/fig7_grade_distribution.png", bbox_inches="tight")
    plt.close()
    print("Saved fig7_grade_distribution.png")


def fig_rating_vs_grade():
    query = """
        SELECT e.final_grade, r.rating
        FROM enrollment e
        JOIN rating r ON e.student_id = r.student_id AND e.section_id = r.section_id
        WHERE e.final_grade IS NOT NULL
    """
    df = pd.read_sql(query, conn)
    order = ["A", "A-", "B+", "B", "C+", "C"]
    df["final_grade"] = pd.Categorical(df["final_grade"], categories=order, ordered=True)
    df = df.sort_values("final_grade")

    fig, ax = plt.subplots(figsize=(7, 4))
    df.boxplot(column="rating", by="final_grade", ax=ax,
               boxprops=dict(color=PALETTE[0]),
               medianprops=dict(color="#E74C3C", linewidth=2),
               whiskerprops=dict(color=PALETTE[0]),
               capprops=dict(color=PALETTE[0]),
               flierprops=dict(marker="o", color=PALETTE[2], alpha=0.5, markersize=4))
    ax.set_xlabel("Final Grade Received")
    ax.set_ylabel("Professor Rating Given (1–5)")
    ax.set_title("Fig 8 — Professor Rating vs. Final Grade\n"
                 "Weak positive correlation suggests grade satisfaction may influence ratings",
                 fontweight="bold", pad=12)
    plt.suptitle("")  # remove default boxplot title
    plt.tight_layout()
    plt.savefig("figures/fig8_rating_vs_grade.png", bbox_inches="tight")
    plt.close()
    print("Saved fig8_rating_vs_grade.png")


def fig_rmse_vs_k():
    """
    Simulates train/test RMSE across k values for SVD.
    Uses a simple leave-some-out approach on known ratings.
    """
    query = """
        SELECT r.student_id, p.professor_id, r.rating
        FROM rating r
        JOIN section s ON r.section_id = s.section_id
        JOIN professor p ON s.professor_id = p.professor_id
    """
    df = pd.read_sql(query, conn)
    matrix = df.pivot_table(index="student_id", columns="professor_id",
                            values="rating", aggfunc="mean")

    np.random.seed(42)
    known_positions = [(i, j) for i in range(matrix.shape[0])
                       for j in range(matrix.shape[1])
                       if not np.isnan(matrix.iloc[i, j])]
    test_idx = np.random.choice(len(known_positions),
                                size=int(0.15 * len(known_positions)), replace=False)
    test_positions = [known_positions[i] for i in test_idx]

    train = matrix.copy()
    actuals = []
    for (ri, ci) in test_positions:
        actuals.append(train.iloc[ri, ci])
        train.iloc[ri, ci] = np.nan

    train_filled = train.fillna(0)

    k_values = range(1, min(matrix.shape[1] - 1, 12) + 1)
    rmse_list = []

    for k in k_values:
        svd = TruncatedSVD(n_components=k, random_state=42)
        lat = svd.fit_transform(train_filled)
        pred_matrix = pd.DataFrame(lat @ svd.components_,
                                   index=matrix.index, columns=matrix.columns)
        preds = [pred_matrix.iloc[ri, ci] for (ri, ci) in test_positions]
        rmse = np.sqrt(np.mean((np.array(preds) - np.array(actuals)) ** 2))
        rmse_list.append(rmse)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(list(k_values), rmse_list, marker="s", color=PALETTE[0],
            linewidth=2, markersize=5, label="Test RMSE")
    best_k = list(k_values)[np.argmin(rmse_list)]
    ax.axvline(best_k, color="#E74C3C", linestyle="--",
               label=f"Best k={best_k} (RMSE={min(rmse_list):.3f})")
    ax.set_xlabel("Number of Latent Factors (k)")
    ax.set_ylabel("Root Mean Square Error (RMSE)")
    ax.set_title("Fig 9 — SVD Test RMSE vs. Number of Latent Factors",
                 fontweight="bold", pad=12)
    ax.legend(fontsize=9)
    plt.tight_layout()
    plt.savefig("figures/fig9_rmse_vs_k.png", bbox_inches="tight")
    plt.close()
    print("Saved fig9_rmse_vs_k.png")
    return min(rmse_list), best_k



if __name__ == "__main__":
    fig_rating_distribution()
    fig_top_professors()
    fig_sparsity_heatmap()
    fig_ratings_per_student()
    fig_svd_explained_variance()
    fig_latent_factor_scatter()
    fig_grade_distribution()
    fig_rating_vs_grade()
    best_rmse, best_k = fig_rmse_vs_k()
    print(f"\nAll figures saved to ./figures/")
    print(f"Best SVD RMSE: {best_rmse:.4f} at k={best_k}")
    conn.close()
