import psycopg2

conn = psycopg2.connect(
    host="localhost",
    port=5432,
    database="classicmodels",
    user="postgres",
    password="postgres"
)

cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM customers;")
result = cursor.fetchone()
print(f"Total customers: {result[0]}")
cursor.close()
conn.close()