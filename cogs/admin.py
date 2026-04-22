import discord
from discord import app_commands
from discord.ext import commands

from database import db


class AdminCog(commands.Cog):
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

    @app_commands.command(name="add_club", description="Register a new club")
    @app_commands.describe(
        name="Display name for the club",
        circle_id="Uma.moe circle ID",
        daily_goal="Daily fan goal (e.g. 850000)",
    )
    @app_commands.default_permissions(administrator=True)
    async def add_club(
        self,
        interaction: discord.Interaction,
        name: str,
        circle_id: str,
        daily_goal: int,
    ):
        success = await db.add_club(
            str(interaction.guild_id), name, circle_id, daily_goal
        )
        if success:
            await interaction.response.send_message(
                f"✅ **{name}** registered — circle ID `{circle_id}`, daily goal **{daily_goal:,}** fans.",
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                f"❌ A club named **{name}** already exists in this server.", ephemeral=True
            )

    @app_commands.command(name="set_goal", description="Update the daily fan goal for a club")
    @app_commands.describe(club="Club name", daily_goal="New daily fan goal")
    @app_commands.default_permissions(administrator=True)
    @app_commands.autocomplete(club=_club_autocomplete)
    async def set_goal(
        self, interaction: discord.Interaction, club: str, daily_goal: int
    ):
        success = await db.set_goal(str(interaction.guild_id), club, daily_goal)
        if success:
            await interaction.response.send_message(
                f"✅ Daily goal for **{club}** updated to **{daily_goal:,}** fans.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Club **{club}** not found.", ephemeral=True
            )

    @app_commands.command(name="remove_club", description="Remove a club from tracking")
    @app_commands.describe(club="Club name")
    @app_commands.default_permissions(administrator=True)
    @app_commands.autocomplete(club=_club_autocomplete)
    async def remove_club(self, interaction: discord.Interaction, club: str):
        success = await db.remove_club(str(interaction.guild_id), club)
        if success:
            await interaction.response.send_message(
                f"✅ **{club}** removed.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                f"❌ Club **{club}** not found.", ephemeral=True
            )

    @app_commands.command(name="list_clubs", description="List all registered clubs")
    async def list_clubs(self, interaction: discord.Interaction):
        clubs = await db.get_clubs(str(interaction.guild_id))
        if not clubs:
            await interaction.response.send_message(
                "No clubs registered yet. Use `/add_club` to add one.", ephemeral=True
            )
            return

        embed = discord.Embed(title="Registered Clubs", color=discord.Color.blurple())
        for club in clubs:
            goal = club["daily_goal"]
            goal_str = f"{goal:,}" if goal > 0 else "not set"
            embed.add_field(
                name=club["name"],
                value=f"Circle ID: `{club['circle_id']}`\nDaily goal: **{goal_str}**",
                inline=True,
            )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
