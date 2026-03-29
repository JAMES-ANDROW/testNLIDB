from dotenv import load_dotenv
import os
import psycopg2
from psycopg2.extras import execute_values

load_dotenv()

NEW_PETS = [
    ("Bella", "dog", 4),
    ("Charlie", "dog", 2),
    ("Max", "dog", 5),
    ("Lucy", "cat", 1),
    ("Daisy", "cat", 3),
    ("Rocky", "dog", 6),
    ("Molly", "rabbit", 2),
    ("Coco", "bird", 1),
    ("Bailey", "dog", 7),
    ("Nala", "cat", 4),
    ("Simba", "cat", 5),
    ("Loki", "dog", 2),
    ("Zoe", "dog", 3),
    ("Leo", "hamster", 1),
    ("Mochi", "rabbit", 2),
    ("Poppy", "dog", 4),
    ("Toby", "dog", 8),
    ("Rosie", "cat", 3),
    ("Jasper", "dog", 1),
    ("Willow", "cat", 6),
    ("Pepper", "bird", 2),
    ("Biscuit", "dog", 5),
    ("Pumpkin", "cat", 2),
    ("Scout", "dog", 3),
    ("Clover", "rabbit", 1),
    ("Oreo", "cat", 4),
    ("Hazel", "dog", 2),
    ("Finn", "dog", 6),
    ("Sunny", "bird", 1),
    ("Maple", "cat", 5),
]


def main() -> None:
    conn = psycopg2.connect(
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
    )
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public.pets (
                        id SERIAL PRIMARY KEY,
                        name TEXT NOT NULL,
                        species TEXT NOT NULL,
                        age INT
                    )
                    """
                )
                execute_values(
                    cur,
                    "INSERT INTO public.pets (name, species, age) VALUES %s",
                    NEW_PETS,
                )
                cur.execute("SELECT COUNT(*) FROM public.pets")
                total = cur.fetchone()[0]

        with open("seed_result.txt", "w", encoding="utf-8") as f:
            f.write(f"INSERTED={len(NEW_PETS)}\nTOTAL={total}\n")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
