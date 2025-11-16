import os
import threading
import discord
from discord.ext import commands
from discord.ui import View, Button, Modal, TextInput
from fastapi import FastAPI
import uvicorn

# =======================
# Minimalus HTTP serveris Render
# =======================
app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok"}

def run_server():
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

# =======================
# Intents ir bot
# =======================
intents = discord.Intents.default()
intents.message_content = True  # reikalinga interakcijoms su mygtukais/modalu

bot = commands.Bot(command_prefix="!", intents=intents)

# =======================
# Globalūs duomenys
# =======================
applications_data = {}  # Laikys atsakymus laikinas: {user_id: {Q1: answer,...}}

# =======================
# Modal – klausimai
# =======================
class ApplicationModal(Modal):
    def __init__(self, user_id):
        super().__init__(title="Guild Application Survey")
        self.user_id = user_id

        for i in range(1, 11):
            self.add_item(TextInput(
                label=f"Question {i}",
                style=discord.TextStyle.paragraph,
                placeholder=f"Answer for question {i}"
            ))

    async def on_submit(self, interaction: discord.Interaction):
        applications_data[self.user_id] = {f"Q{i+1}": field.value for i, field in enumerate(self.children)}

        await interaction.response.send_message(
            "✅ Survey submitted! Your application has been sent.",
            ephemeral=True
        )

        guild = interaction.guild
        channel = discord.utils.get(guild.text_channels, name="applications")
        if channel:
            thread = await channel.create_thread(
                name=f"Application - {interaction.user.display_name}",
                type=discord.ChannelType.public_thread,
                auto_archive_duration=1440
            )

            embed = discord.Embed(
                title=f"Application from {interaction.user}",
                color=discord.Color.blue()
            )
            for i, field in enumerate(self.children):
                embed.add_field(name=f"Q{i+1}", value=field.value, inline=False)

            await thread.send(embed=embed)

# =======================
# Mygtukas embed žinutėje
# =======================
class ApplyButtonView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Apply Now", style=discord.ButtonStyle.green)
    async def apply_button(self, interaction: discord.Interaction, button: Button):
        try:
            await interaction.user.send_modal(ApplicationModal(interaction.user.id))
            await interaction.response.send_message(
                "📬 Check your DMs to fill the application.",
                ephemeral=True
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I cannot DM you. Please enable DMs from server members.",
                ephemeral=True
            )

# =======================
# Slash komanda /send_application_embed
# =======================
@bot.tree.command(name="send_application_embed", description="Send the application embed to channel")
async def send_application_embed(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_messages:
        await interaction.response.send_message(
            "❌ You don't have permission to use this command.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="Guild Application",
        description="Click the button below to start your application!",
        color=discord.Color.green()
    )

    view = ApplyButtonView()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Application embed sent!", ephemeral=True)

# =======================
# Įvykiai
# =======================
@bot.event
async def on_ready():
    print(f"Bot logged in as {bot.user}")
    await bot.tree.sync()
    print("Slash commands synchronized.")

# =======================
# Paleidimas
# =======================
if __name__ == "__main__":
    # Paleidžiam minimalų HTTP serverį Render fone
    threading.Thread(target=run_server, daemon=True).start()

    # Paleidžiam Discord botą
    bot.run(os.environ["DISCORD_TOKEN"])
