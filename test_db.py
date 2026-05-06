import sqlite3
import pandas as pd
from sklearn.decomposition import TruncatedSVD

conn=sqlite3.connect("profmatch.db")

row = pd.read_sql(
    """SELECT student_id, rating, professor_name FROM rating 
        JOIN Section s ON rating.section_id = s.section_id
        JOIN Professor p ON s.professor_id = p.professor_id
        WHERE student_id = 80
        ORDER BY rating DESC
        
""", conn)
prof_name = row.loc[0, "professor_name"]

prof_data = pd.read_csv("Data/rutgers_cs_rmp_ratings.csv")

print(prof_data[prof_data["rmp_name"] == prof_name][["difficulty","quality", "would_take_again_pct"]])