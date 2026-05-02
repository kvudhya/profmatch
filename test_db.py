import psycopg
import pandas as pd
from sklearn.decomposition import TruncatedSVD

conn = psycopg.connect(
    dbname="profmatch_db",
    user="parvezabdul",
    host="localhost",
    port=5432
)

query = """
SELECT
    r.student_id,
    s.professor_id,
    r.rating
FROM rating r
JOIN section s
    ON r.section_id = s.section_id
ORDER BY r.student_id, s.professor_id;
"""

df = pd.read_sql(query, conn)

print("Joined data:")
print(df)

interaction_matrix = df.pivot_table(
    index="student_id",
    columns="professor_id",
    values="rating"
)

print("\nInteraction matrix:")
print(interaction_matrix)

interaction_matrix_filled = interaction_matrix.fillna(0)

print("\nFilled interaction matrix:")
print(interaction_matrix_filled)

interaction_matrix_filled.to_csv("interaction_matrix.csv")
print("\nSaved interaction_matrix.csv")

svd = TruncatedSVD(n_components=2, random_state=42)
latent_matrix = svd.fit_transform(interaction_matrix_filled)

latent_df = pd.DataFrame(
    latent_matrix,
    index=interaction_matrix_filled.index,
    columns=["latent_feature_1", "latent_feature_2"]
)

print("\nLatent matrix:")
print(latent_df)

latent_df.to_csv("latent_matrix.csv")
print("\nSaved latent_matrix.csv")

conn.close()