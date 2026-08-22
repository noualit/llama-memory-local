import asyncio
import asyncpg


async def create_db():
    conn = await asyncpg.connect(
        user="postgres",
        password="yourpassword",
        host="localhost"
    )

    exists = await conn.fetchval(
        "SELECT 1 FROM pg_database WHERE datname = 'llamamem'"
    )

    if not exists:
        await conn.execute("CREATE DATABASE llamamem;")
        print("Database llamamem created.")
    else:
        print("Database llamamem already exists.")

    await conn.close()


asyncio.run(create_db())
