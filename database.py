import psycopg2


def get_connection():
    return psycopg2.connect(
        host="localhost",
        port=5433,
        database="facial recognition",
        user="postgres",
        password="postgres123"
    )

if __name__ == "__main__":
    try:
        conn = get_connection()
        print("Database connection successful!")
        conn.close()
    except Exception as e:
        print("Database connection failed:")
        print(e)