import os
import json
import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button
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
# Pagalbinės funkcijos
# =======================
DATA_FILE = "splits.json"

def load_splits():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                content = f.read().strip()
                if not content:  # jei failas tuščias
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            return {}
    return {}

def save_splits():
    with open(DATA_FILE, "w") as f:
        json.dump(splits, f)

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

# Čia bus laikomi splits (užkraunami iš failo)
splits = load_splits()

# =======================
# Mygtukų View
# =======================
class SplitView(View):
    def __init__(self, split_id: str, starter_id: int):
        super().__init__(timeout=None)
        self.split_id = split_id
        self.starter_id = starter_id

        # Sukuriame po mygtuką kiekvienam nariui
        if split_id in splits:
            for uid in splits[split_id]["members"].keys():
                member_button = Button(label=f"Mark {uid}", style=discord.ButtonStyle.primary, custom_id=f"mark_{uid}")
                member_button.callback = self.make_callback(uid)
                self.add_item(member_button)

    def make_callback(self, uid: str):
        async def callback(interaction: discord.Interaction):
            # Tik splito kūrėjas gali spausti mygtukus
            if interaction.user.id != self.starter_id:
                await interaction.response.send_message("❌ Only the split creator can use these buttons!", ephemeral=True)
                return

            split = splits.get(self.split_id)
            if not split:
                await interaction.response.send_message("❌ Split not found!", ephemeral=True)
                return

            # Pakeičiam statusą į ✅
            split["members"][uid] = True

            # Paimam seną žinutę
            channel = bot.get_channel(split["channel_id"])
            msg = await channel.fetch_message(split["message_id"])
            embed = msg.embeds[0]

            new_value = ""
            for member_id, taken in split["members"].items():
                member = channel.guild.get_member(int(member_id))
                status = "✅" if taken else "❌"
                new_value += f"**{member.display_name if member else member_id}**\nShare: {split['each']}M | Status: {status}\n"

            embed.set_field_at(index=3, name="Players", value=new_value, inline=False)
            await msg.edit(embed=embed, view=SplitView(self.split_id, self.starter_id))

            save_splits()

            # Patikrinam ar visi paėmė
            if all(split["members"].values()):
                await channel.send("✅ All players have taken their split, this split is now closed!")
                del splits[self.split_id]
                save_splits()

            await interaction.response.defer()  # paslepia „thinking...“

        return callback

# =======================
# Įvykiai
# =======================
@bot.event
async def on_ready():
    print(f"Joined as {bot.user}")
    try:
        synced = await tree.sync()
        print(f"Slash commands synchronized ({len(synced)})")
    except Exception as e:
        print(e)

# =======================
# Komandos
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

    splits[str(msg.id)] = {
        "members": {str(m.id): False for m in selected_members},
        "amount": amount,
        "each": per_share,
        "message_id": msg.id,
        "channel_id": msg.channel.id,
        "starter": interaction.user.id
    }
    save_splits()

    # Redaguojam žinutę, kad pridėtume mygtukus
    await msg.edit(view=SplitView(str(msg.id), interaction.user.id))

    await interaction.response.send_message("✅ Split created!", ephemeral=True)

@bot.event
async def on_message(message):
    await bot.process_commands(message)

    if message.author.bot or not message.attachments:
        return

    for msg_id, data in list(splits.items()):
        if message.channel.id != data["channel_id"]:
            continue
        if str(message.author.id) in data["members"] and not data["members"][str(message.author.id)]:
            data["members"][str(message.author.id)] = True
            await message.add_reaction("✅")

            # Paimam seną žinutę
            msg = await message.channel.fetch_message(data["message_id"])
            embed = msg.embeds[0]

            new_value = ""
            for uid, taken in data["members"].items():
                member = message.guild.get_member(int(uid))
                status = "✅" if taken else "❌"
                new_value += f"**{member.display_name if member else uid}**\nShare: {data['each']}M | Status: {status}\n"

            embed.set_field_at(index=3, name="Players", value=new_value, inline=False)
            await msg.edit(embed=embed, view=SplitView(msg_id, data["starter"]))

            save_splits()

            if all(data["members"].values()):
                await message.channel.send("✅ All players have taken their split, this split is now closed!")
                del splits[msg_id]
                save_splits()

# =======================
# Paleidimas
# =======================
if __name__ == "__main__":
    Thread(target=run_flask).start()
    bot.run(os.environ["DISCORD_TOKEN"])
