import aiosqlite
import logging

logger = logging.getLogger(__name__)

DB_PATH = "uma.db"


class Database:
    def __init__(self):
        self._db: aiosqlite.Connection | None = None

    async def connect(self):
        self._db = await aiosqlite.connect(DB_PATH)
        self._db.row_factory = aiosqlite.Row
        await self._init_schema()
        logger.info("Database connected")

    async def disconnect(self):
        if self._db:
            await self._db.close()

    async def _init_schema(self):
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS clubs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id    TEXT    NOT NULL,
                name        TEXT    NOT NULL,
                circle_id   TEXT    NOT NULL,
                daily_goal  INTEGER NOT NULL DEFAULT 0,
                UNIQUE(guild_id, name)
            )
        """)
        await self._db.commit()

    # --- clubs ---

    async def add_club(self, guild_id: str, name: str, circle_id: str, daily_goal: int) -> bool:
        try:
            await self._db.execute(
                "INSERT INTO clubs (guild_id, name, circle_id, daily_goal) VALUES (?, ?, ?, ?)",
                (guild_id, name, circle_id, daily_goal),
            )
            await self._db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False

    async def get_clubs(self, guild_id: str) -> list:
        async with self._db.execute(
            "SELECT * FROM clubs WHERE guild_id = ? ORDER BY name", (guild_id,)
        ) as cur:
            return await cur.fetchall()

    async def get_club(self, guild_id: str, name: str):
        async with self._db.execute(
            "SELECT * FROM clubs WHERE guild_id = ? AND name = ?", (guild_id, name)
        ) as cur:
            return await cur.fetchone()

    async def set_goal(self, guild_id: str, name: str, daily_goal: int) -> bool:
        cur = await self._db.execute(
            "UPDATE clubs SET daily_goal = ? WHERE guild_id = ? AND name = ?",
            (daily_goal, guild_id, name),
        )
        await self._db.commit()
        return cur.rowcount > 0

    async def remove_club(self, guild_id: str, name: str) -> bool:
        cur = await self._db.execute(
            "DELETE FROM clubs WHERE guild_id = ? AND name = ?", (guild_id, name)
        )
        await self._db.commit()
        return cur.rowcount > 0


db = Database()
