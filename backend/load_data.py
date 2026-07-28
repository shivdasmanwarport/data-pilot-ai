import pandas as pd
from sqlalchemy import create_engine

# Read CSV
df = pd.read_csv(r"C:\Users\91930\Downloads\organizations-100000.csv")

# MySQL connection
engine = create_engine(
    "mysql+pymysql://root:Shiv%402001@localhost:3306/datapilot"
)

# Create table and insert data
df.to_sql(
    name="organization",
    con=engine,
    if_exists="replace",   # replace | append | fail
    index=False
)

print("Data imported successfully!")