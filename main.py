import asyncio
import logging
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import db

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

COGS = ["cogs.admin", "cogs.fancount"]


async def main():
    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN is not set — add it to your .env file")
        return

    await db.connect()

    intents = discord.Intents.default()
    bot = commands.Bot(command_prefix="!", intents=intents)

    @bot.event
    async def on_ready():
        logger.info(f"Logged in as {bot.user} ({bot.user.id})")
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash command(s)")

    for cog in COGS:
        await bot.load_extension(cog)
        logger.info(f"Loaded {cog}")

    try:
        await bot.start(token)
    except KeyboardInterrupt:
        pass
    finally:
        await db.disconnect()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
