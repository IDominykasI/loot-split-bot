import os
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
from threading import Thread
from flask import Flask

# =======================
# Flask dalis
# =======================
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# =======================
# Discord dalis
# =======================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

splits = {}

# =======================
# Split valdymas
# =======================
class SplitView(View):
    def __init__(self, split_id: str, starter_id: int, guild: discord.Guild):
        super().__init__(timeout=None)
        self.split_id = split_id
        self.starter_id = starter_id

        if split_id in splits:
            # Dropdown su dalyviais
            options = []
            for uid in splits[split_id]["members"].keys():
                member = guild.get_member(int(uid))
                if member:
                    options.append(discord.SelectOption(label=member.display_name, value=str(uid)))

            self.select = Select(
                placeholder="Choose player...",
                options=options,
                custom_id=f"select_{split_id}"
            )
            self.add_item(self.select)

            # Mygtukas Check
            check_btn = Button(label="Check", style=discord.ButtonStyle.success, custom_id=f"check_{split_id}")
            check_btn.callback = self.check_callback
            self.add_item(check_btn)

    async def check_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.starter_id:
            await interaction.response.send_message("❌ Only split creator can use this!", ephemeral=True)
            return

        split = splits.get(self.split_id)
        if not split:
            await interaction.response.send_message("❌ Split not found!", ephemeral=True)
            return

        selected_uid = self.select.values[0]
        split["members"][selected_uid] = True

        channel = bot.get_channel(split["channel_id"])
        msg = await channel.fetch_message(split["message_id"])
        embed = msg.embeds[0]

        new_value = ""
        for uid, taken in split["members"].items():
            member = channel.guild.get_member(int(uid))
            status = "✅" if taken else "❌"
            new_value += f"**{member.display_name if member else uid}**\nShare: {split['each']}M | Status: {status}\n"

        embed.set_field_at(index=3, name="Players", value=new_value, inline=False)
        await msg.edit(embed=embed, view=SplitView(self.split_id, self.starter_id, channel.guild))

        if all(split["members"].values()):
            await channel.send("✅ All players have taken their split, this split is now closed!")
            del splits[self.split_id]

        await interaction.response.defer()

# =======================
# Įvykiai
# =======================
@bot.event
async def on_ready():
    print(f"Joined as {bot.user}")
    await tree.sync()

# =======================
# Split komanda
# =======================
@tree.command(name="split", description="Start loot split")
async def split(interaction: discord.Interaction, amount: float, members: str):
    guild = interaction.guild
    user_mentions = [m.strip() for m in members.split()]
    selected_members = []

    for m in user_mentions:
        if m.startswith("<@") and m.endswith(">"):
            user_id = int(m[2:-1].replace("!", ""))
            member = guild.get_member(user_id)
            if member:
                selected_members.append(member)

    if not selected_members:
        await interaction.response.send_message("No valid members!", ephemeral=True)
        return

    per_share = round(amount / len(selected_members), 2)

    embed = discord.Embed(title="💰 Loot Distribution in Progress 💰", color=discord.Color.gold())
    embed.add_field(name="Total split amount", value=f"💰 {amount}M", inline=False)
    embed.add_field(name="Each player's share", value=f"💰 {per_share}M", inline=False)
    embed.add_field(name="📣 Started by", value=interaction.user.mention, inline=False)

    status_text = ""
    for m in selected_members:
        status_text += f"**{m.display_name}**\nShare: {per_share}M | Status: ❌\n"

    embed.add_field(name="Players", value=status_text, inline=False)
    embed.set_footer(text="📸 Submit loot screenshots to confirm participation!")

    msg = await interaction.channel.send(
        content=f"Hello {' '.join(m.mention for m in selected_members)}, you are part of this loot split.",
        embed=embed
    )

    splits[str(msg.id)] = {
        "members": {str(m.id): False for m in selected_members},
        "amount": amount,
        "each": per_share,
        "message_id": msg.id,
        "channel_id": msg.channel.id,
        "starter": interaction.user.id
    }

    await msg.edit(view=SplitView(str(msg.id), interaction.user.id, guild))
    await interaction.response.send_message("✅ Split created!", ephemeral=True)

# =======================
# Paleidimas
# =======================
if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.run(os.environ["DISCORD_TOKEN"])
