import os
import discord
from discord.ext import commands
from discord import app_commands
from threading import Thread
from flask import Flask

# =======================
# Flask (kad Render laikytų gyvą)
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

# Splitai saugomi atmintyje
splits = {}

# =======================
# Atkurti splitus iš forumo
# =======================
async def restore_splits():
    forum_channel = discord.utils.get(bot.get_all_channels(), name="lootsplits")
    if not forum_channel:
        print("❌ Nerastas forum kanalas Lootsplits")
        return

    async for thread in forum_channel.active_threads():
        try:
            first_msg = await thread.fetch_message(thread.id)  # Thread starter
            if not first_msg.embeds:
                continue

            embed = first_msg.embeds[0]
            if embed.title != "💰 Loot Distribution in Progress 💰":
                continue

            # Ištraukiam amount, each ir statusus
            amount = None
            each = None
            members = {}

            for field in embed.fields:
                if field.name == "Total split amount":
                    amount = field.value.replace("💰 ", "").replace("M", "").strip()
                if field.name == "Each player's share":
                    each = field.value.replace("💰 ", "").replace("M", "").strip()
                if field.name == "Players":
                    for line in field.value.split("\n"):
                        if not line.strip():
                            continue
                        if "Share:" in line and "Status:" in line:
                            name = line.split("**")[1]  # display_name
                            status = "✅" in line
                            members[name] = status

            splits[str(first_msg.id)] = {
                "channel_id": thread.id,
                "message_id": first_msg.id,
                "amount": amount,
                "each": each,
                "members": members
            }

            print(f"✅ Atkurtas splitas iš gijos: {thread.name}")

        except Exception as e:
            print(f"Klaida atkuriant splitą: {e}")

# =======================
# Bot eventai
# =======================
@bot.event
async def on_ready():
    print(f"✅ Prisijungė kaip {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Slash komandos sinchronizuotos ({len(synced)})")
    except Exception as e:
        print(e)

    # Atkurti splitus
    await restore_splits()

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

    # Sukuriam naują forum thread
    forum_channel = discord.utils.get(guild.channels, name="Lootsplits")
    thread = await forum_channel.create_thread(name=f"Lootsplit {amount}M", content="Split started!", embed=embed)

    splits[str(thread.id)] = {
        "channel_id": thread.id,
        "message_id": thread.id,
        "amount": amount,
        "each": per_share,
        "members": {m.display_name: False for m in selected_members}
    }

    await interaction.response.send_message("✅ Split created!", ephemeral=True)

@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.author.bot or not message.attachments:
        return

    for msg_id, data in list(splits.items()):
        if message.channel.id != data["channel_id"]:
            continue

        if message.author.display_name in data["members"] and not data["members"][message.author.display_name]:
            data["members"][message.author.display_name] = True
            await message.add_reaction("✅")

            # Paimam seną žinutę (thread starter)
            msg = await message.channel.fetch_message(data["message_id"])
            embed = msg.embeds[0]

            new_value = ""
            for name, taken in data["members"].items():
                status = "✅" if taken else "❌"
                new_value += f"**{name}**\nShare: {data['each']}M | Status: {status}\n"

            embed.set_field_at(index=3, name="Players", value=new_value, inline=False)
            await msg.edit(embed=embed)

            if all(data["members"].values()):
                await message.channel.send("✅ All players have taken their split, this split is now closed!")
                del splits[msg_id]

# =======================
# Paleidimas
# =======================
if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.run(os.environ["DISCORD_TOKEN"])

