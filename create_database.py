import sqlite3
import pandas as pd

df = pd.read_csv("employees.csv")

conn = sqlite3.connect("employees.db")

df.to_sql("employees", conn, if_exists="replace", index=False)

conn.commit()
conn.close()

print("Database created")