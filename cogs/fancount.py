import logging

import discord
from discord import app_commands
from discord.ext import commands

from database import db
from scraper import fetch_club_data

logger = logging.getLogger(__name__)


def _fmt(n: int) -> str:
    """Format a fan count into a compact string (e.g. 1234567 → 1.23M)."""
    if abs(n) >= 1_000_000:
        return f"{n / 1_000_000:.2f}M"
    if abs(n) >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


class FancountCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _club_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        clubs = await db.get_clubs(str(interaction.guild_id))
        return [
            app_commands.Choice(name=c["name"], value=c["name"])
            for c in clubs
            if current.lower() in c["name"].lower()
        ][:25]

    @app_commands.command(
        name="fancount",
        description="Show this month's fan counts vs daily target for a club",
    )
    @app_commands.describe(club="Club name")
    @app_commands.autocomplete(club=_club_autocomplete)
    async def fancount(self, interaction: discord.Interaction, club: str):
        await interaction.response.defer()

        club_row = await db.get_club(str(interaction.guild_id), club)
        if not club_row:
            await interaction.followup.send(
                f"❌ Club **{club}** not found. Use `/list_clubs` to see registered clubs.",
                ephemeral=True,
            )
            return

        try:
            result = await fetch_club_data(club_row["circle_id"])
        except Exception as exc:
            logger.error(f"Scrape failed for {club}: {exc}")
            await interaction.followup.send(
                f"❌ Failed to fetch data from Uma.moe: {exc}", ephemeral=True
            )
            return

        members = result["members"]
        data_day = result["data_day"]
        daily_goal = club_row["daily_goal"]

        embed = discord.Embed(
            title=f"📊 {club}  —  Day {data_day}",
            color=discord.Color.purple(),
        )

        if not members:
            embed.description = "No active members found in the API response."
            await interaction.followup.send(embed=embed)
            return

        lines = []
        for rank, member in enumerate(members, start=1):
            name = member["trainer_name"]
            earned = member["monthly_earned"]
            join_day = member["join_day"]

            # Days this member has been active this month
            days_active = data_day - join_day + 1

            if daily_goal > 0:
                target = daily_goal * days_active
                diff = earned - target
                sign = "+" if diff >= 0 else ""
                diff_str = f"{sign}{_fmt(diff)}"
                indicator = "🟢" if diff >= 0 else "🔴"

                joined_note = f" *(joined d{join_day})*" if join_day > 1 else ""
                lines.append(
                    f"`{rank:>2}.` {indicator} **{name}**{joined_note}\n"
                    f"       {_fmt(earned)} / {_fmt(target)}  `{diff_str}`"
                )
            else:
                lines.append(f"`{rank:>2}.` **{name}** — {_fmt(earned)}")

        embed.description = "\n".join(lines)

        if daily_goal > 0:
            embed.set_footer(
                text=f"earned / target  •  daily goal: {_fmt(daily_goal)}/day  •  data day {data_day}"
            )
        else:
            embed.set_footer(text=f"data day {data_day}  •  no daily goal set — use /set_goal")

        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(FancountCog(bot))
