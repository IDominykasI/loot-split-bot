import os
import discord
from discord.ext import commands
from discord import app_commands
from threading import Thread
from flask import Flask

# =======================
# Flask dalis (Web service)
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
intents.messages = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
splits = {}

@bot.event
async def on_ready():
    print(f"Joined as {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Slash commands synchronized ({len(synced)})")
    except Exception as e:
        print(e)

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
        await interaction.response.send_message("No valid members specified!", ephemeral=True)
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

    splits[msg.id] = {
        "members": {m.id: False for m in selected_members},
        "amount": amount,
        "each": per_share,
        "message": msg,
        "starter": interaction.user.id
    }

    await interaction.response.send_message("✅ Split created!", ephemeral=True)

@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.author.bot or not message.attachments:
        return

    for msg_id, data in splits.items():
        if message.channel.id != data["message"].channel.id:
            continue
        if message.author.id in data["members"] and not data["members"][message.author.id]:
            data["members"][message.author.id] = True
            await message.add_reaction("✅")

            embed = data["message"].embeds[0]
            new_value = ""
            for uid, taken in data["members"].items():
                member = message.guild.get_member(uid)
                status = "✅" if taken else "❌"
                new_value += f"**{member.display_name}**\nShare: {data['each']}M | Status: {status}\n"

            embed.set_field_at(index=3, name="Players", value=new_value, inline=False)
            await data["message"].edit(embed=embed)

            if all(data["members"].values()):
                await message.channel.send("✅ All players have taken their split, this split is now closed!")

# =======================
# Paleidimas
# =======================
if __name__ == "__main__":
    # Paleidžiam Flask serverį atskirame threade
    Thread(target=run_flask).start()
    # Paleidžiam Discord botą
    bot.run(os.environ["DISCORD_TOKEN"])
