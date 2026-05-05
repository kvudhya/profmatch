import sqlite3
import pandas as pd
from sklearn.decomposition import TruncatedSVD


conn = sqlite3.connect("../profmatch.db")

query = """
SELECT
    r.student_id,
    p.professor_id,
    p.professor_name,
    r.rating
FROM rating r
JOIN section s
    ON r.section_id = s.section_id
JOIN professor p
    ON s.professor_id = p.professor_id
ORDER BY r.student_id, p.professor_id;
"""

df = pd.read_sql(query, conn)

print("Joined rating data:")
print(df.head())

interaction_matrix = df.pivot_table(
    index="student_id",
    columns="professor_id",
    values="rating",
    aggfunc="mean"
)

print("\nInteraction matrix:")
print(interaction_matrix.head())

interaction_filled = interaction_matrix.fillna(0)

n_components = min(2, interaction_filled.shape[1] - 1)

svd = TruncatedSVD(n_components=n_components, random_state=42)
student_latent = svd.fit_transform(interaction_filled)

predicted_ratings = student_latent @ svd.components_

predicted_df = pd.DataFrame(
    predicted_ratings,
    index=interaction_matrix.index,
    columns=interaction_matrix.columns
)

professor_lookup = dict(
    pd.read_sql("SELECT professor_id, professor_name FROM professor", conn)
    .values
)


def recommend_professors(student_id, top_n=5):
    if student_id not in predicted_df.index:
        return pd.DataFrame()

    student_actual = interaction_matrix.loc[student_id]
    student_predictions = predicted_df.loc[student_id]

    unrated_professors = student_actual[student_actual.isna()].index

    recommendations = student_predictions[unrated_professors].sort_values(ascending=False)

    rec_df = pd.DataFrame({
        "professor_id": recommendations.index,
        "predicted_rating": recommendations.values
    })

    rec_df["professor_name"] = rec_df["professor_id"].map(professor_lookup)

    return rec_df[["professor_id", "professor_name", "predicted_rating"]].head(top_n)


print("\nRecommendations for student 1:")
print(recommend_professors(1, top_n=5))

conn.close()