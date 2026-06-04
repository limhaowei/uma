import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands

from database import db
from scraper import fetch_club_data

logger = logging.getLogger(__name__)

# ANSI colour codes (supported in ```ansi code blocks)
_YELLOW = "\033[33m"
_RESET  = "\033[0m"

# Column widths — plain message code block, no embed width constraint.
_W_RANK    = 3
_W_NAME    = 16   # fits longest Umamusume trainer names (~15 chars)
_W_DAILY   = 6
_W_SURPLUS = 7
_W_TARGET  = 6
_W_TOTAL   = 6

_HEADER = (
    f"{'#':>{_W_RANK}} | "
    f"{'Name':<{_W_NAME}} | "
    f"{'Daily':>{_W_DAILY}} | "
    f"{'Surplus':>{_W_SURPLUS}} | "
    f"{'Target':>{_W_TARGET}} | "
    f"{'Total':>{_W_TOTAL}}"
)
_ROW_WIDTH = len(_HEADER)
_SEP_LINE  = "-" * _ROW_WIDTH


def _fmt(n: int, sign: bool = False) -> str:
    prefix = ("+" if n >= 0 else "-") if sign else ("" if n >= 0 else "-")
    a = abs(n)
    if a >= 1_000_000:
        return f"{prefix}{a / 1_000_000:.1f}M"
    if a >= 1_000:
        return f"{prefix}{a // 1_000}K"
    return f"{prefix}{a}"


def _row(rank: int, name: str, daily: int, surplus: int, target: int, total: int) -> str:
    return (
        f"{f'{rank}.':>{_W_RANK}} | "
        f"{name[:_W_NAME]:<{_W_NAME}} | "
        f"{_fmt(daily, sign=True):>{_W_DAILY}} | "
        f"{_fmt(surplus, sign=True):>{_W_SURPLUS}} | "
        f"{_fmt(target):>{_W_TARGET}} | "
        f"{_fmt(total):>{_W_TOTAL}}"
    )


def _divider(label: str) -> str:
    side = (_ROW_WIDTH - len(label) - 2) // 2
    return "-" * side + f" {label} " + "-" * side


def _build_table(members: list, data_day: int, daily_goal: int) -> str:
    lines = [_HEADER, _SEP_LINE]

    above, below = [], []
    for m in members:
        days_active = data_day - m["join_day"] + 1
        target  = daily_goal * days_active
        surplus = m["monthly_earned"] - target
        (above if surplus >= 0 else below).append((m, target, surplus))

    rank = 1
    for m, target, surplus in above:
        lines.append(_row(rank, m["trainer_name"], m["daily_earned"], surplus, target, m["monthly_earned"]))
        rank += 1

    if below:
        lines.append(_divider("Players Behind Quota"))
        for m, target, surplus in below:
            lines.append(f"{_YELLOW}{_row(rank, m['trainer_name'], m['daily_earned'], surplus, target, m['monthly_earned'])}{_RESET}")
            rank += 1

    return "```ansi\n" + "\n".join(lines) + "\n```"


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

        members      = result["members"]
        data_day     = result["data_day"]
        monthly_rank = result.get("monthly_rank")
        daily_goal   = club_row["daily_goal"]

        rank_str  = f" — Global Ranking #{monthly_rank}" if monthly_rank else ""
        timestamp = datetime.now().strftime("%B %d, %Y")
        title     = f"🏆 **Leaderboard (Club: {club} — Day {data_day}{rank_str})**"
        strip     = discord.Embed(color=discord.Color.gold())
        strip.set_footer(text=f"Data retrieved from Uma.moe API  •  {timestamp}")

        if not members:
            await interaction.followup.send(content=f"{title}\nNo active members found.", embed=strip)
            return

        if daily_goal <= 0:
            lines = "\n".join(
                f"{i:>2}. {m['trainer_name']:<16}  {_fmt(m['monthly_earned'])}"
                for i, m in enumerate(members, 1)
            )
            await interaction.followup.send(
                content=f"{title}\n⚠️ No daily goal set — use `/set_goal` first.\n```\n{lines}\n```",
                embed=strip,
            )
        else:
            table = _build_table(members, data_day, daily_goal)
            await interaction.followup.send(content=f"{title}\n{table}", embed=strip)


async def setup(bot: commands.Bot):
    await bot.add_cog(FancountCog(bot))
