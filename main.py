import discord
from discord import app_commands
from discord.ext import commands
import datetime
import json
import os
from flask import Flask
from threading import Thread

AUTHORIZED_USERS = [
    467663499074600961,
    715964316397862932,
    748599826857328710,
    397052493911293952,
    934832706167136338,
    269917464890966028
]
RELEVANT_ROLE_IDS = {
    1452776372471730234, 1452776372471730233, 1452776372471730232, 1452776372471730230,
    1452776372471730229, 1452776372471730227, 1452776372471730226, 1452776372157284397,
    1452776372157284399, 1452776372157284400, 1452776372157284398, 1452776372157284401,
    1457035483732381849, 1452776372157284393, 1452776372157284392, 1452776372131987560,
    1452776372131987559, 1452776372131987558, 1467881887501520906, 1467881861186457697,
    1452776372131987557, 1467881827761918065, 1452776372131987556, 1452776372131987554,
    1452776372131987555, 1467881689329041529, 1452776372131987553, 1452776372131987551,
    1452776372094111793, 1452776372094111792
}

# ─── Flask Keep-Alive Server ────────────────────────────────────────────────
app = Flask('discord-bot-keep-alive')

@app.route('/')
def home():
    return "Discord bot is running OK"

def run_flask():
    app.run(host="0.0.0.0", port=8080, debug=False, use_reloader=False)

def keep_alive():
    t = Thread(target=run_flask, daemon=True)
    t.start()
    print("Flask keep-alive server started on port 8080")
# ──────────────────────────────────────────────────────────────────────────────

class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        super().__init__(command_prefix='!', intents=intents)

        self.invites = {}
        self.left_members = self.load_data('left_members.json', {})
        self.config = self.load_data('config.json', {})

    def load_data(self, filename, default):
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return default

    def save_data(self):
        with open('left_members.json', 'w', encoding='utf-8') as f:
            json.dump(self.left_members, f, ensure_ascii=False, indent=2)
        with open('config.json', 'w', encoding='utf-8') as f:
            json.dump(self.config, f, ensure_ascii=False, indent=2)

    async def setup_hook(self):
        await self.tree.sync()

    async def on_ready(self):
        print(f'הבוט מחובר כ־ {self.user} ({self.user.id})')
        for guild in self.guilds:
            try:
                self.invites[guild.id] = await guild.invites()
            except Exception as e:
                print(f"לא הצלחתי לקרוא הזמנות בשרת {guild.name}: {e}")

bot = MyBot()

@bot.event
async def on_member_join(member: discord.Member):
    guild = member.guild
    invites_before = bot.invites.get(guild.id, [])
    try:
        invites_after = await guild.invites()
        bot.invites[guild.id] = invites_after
    except Exception as e:
        print(f"שגיאה בקריאת הזמנות: {e}")
        invites_after = invites_before

    invite = None
    inviter = None
    invites_count = 0

    for inv in invites_after:
        before_inv = next((i for i in invites_before if i.id == inv.id), None)
        if before_inv and inv.uses > before_inv.uses:
            invite = inv
            inviter = invite.inviter
            break

    if inviter:
        inviter_invites = [i for i in invites_after if i.inviter and i.inviter.id == inviter.id]
        invites_count = sum(i.uses or 0 for i in inviter_invites)

    guild_id = str(guild.id)
    if guild_id not in bot.left_members:
        bot.left_members[guild_id] = {}
    was_before = str(member.id) in bot.left_members[guild_id]

    config = bot.config.get(guild_id, {})
    channel_id = config.get('welcome')
    if not channel_id:
        return

    channel = guild.get_channel(int(channel_id))
    if not channel:
        return

    embed = discord.Embed(
        title="שוטר חדש נכנס!",
        color=0x00ff00
    )
    embed.description = (
        f"**חבר חדש:** {member.mention}\n"
        f"**שם משתמש:** {member.name}\n"
        f"**מי הזמין:** {inviter.mention if inviter else 'לא ידוע'}\n"
        f"**כמות הזמנות של המזמין:** {invites_count}\n"
        f"**היה בשרת בעבר?** {'כן' if was_before else 'לא'}"
    )
    embed.set_thumbnail(url=member.display_avatar.url)

    view = None
    if was_before:
        class RestoreView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)

            @discord.ui.button(label="החזר רולים", style=discord.ButtonStyle.green)
            async def restore(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user.id not in AUTHORIZED_USERS:
                    await interaction.response.send_message("רק צוות מורשה יכול להחזיר רולים", ephemeral=True)
                    return

                user_id_str = str(member.id)
                roles_data = bot.left_members.get(guild_id, {}).get(user_id_str, {}).get('roles', [])
                roles = [guild.get_role(rid) for rid in roles_data if guild.get_role(rid)]
                if roles:
                    await member.add_roles(*roles)
                    if guild_id in bot.left_members and user_id_str in bot.left_members[guild_id]:
                        del bot.left_members[guild_id][user_id_str]
                    bot.save_data()
                    await interaction.response.send_message("הרולים הוחזרו בהצלחה!", ephemeral=False)
                    button.disabled = True
                    await interaction.message.edit(view=self)
                else:
                    await interaction.response.send_message("לא נמצאו רולים לשחזור", ephemeral=True)

        view = RestoreView()

    await channel.send(embed=embed, view=view)

@bot.event
async def on_member_remove(member: discord.Member):
    guild = member.guild
    guild_id = str(guild.id)
    if guild_id not in bot.left_members:
        bot.left_members[guild_id] = {}

    bot.left_members[guild_id][str(member.id)] = {
        'roles': [role.id for role in member.roles if not role.is_default()],
        'joined_at': member.joined_at.isoformat() if member.joined_at else None
    }
    bot.save_data()

    config = bot.config.get(guild_id, {})
    channel_id = config.get('leave')
    if not channel_id:
        return

    channel = guild.get_channel(int(channel_id))
    if not channel:
        return

    now = datetime.datetime.now(datetime.UTC)
    joined = member.joined_at
    if not joined:
        time_str = "לא ידוע"
    else:
        diff = now - joined
        if diff.days >= 7:
            time_str = f"{diff.days} ימים"
        else:
            hours = int(diff.total_seconds() // 3600)
            time_str = f"{hours} שעות"

    embed = discord.Embed(
        title="שוטר עזב!",
        color=0xff0000
    )
    relevant_roles = [role for role in member.roles if role.id in RELEVANT_ROLE_IDS]
    if relevant_roles:
        roles_mentions = ", ".join([f"<@&{role.id}>" for role in relevant_roles])
    else:
        roles_mentions = "ללא רולים של יחידות או דרגות"

    embed.description = (
        f"**חבר:** {member.mention}\n"
        f"**שם משתמש:** {member.name}\n"
        f"**כינוי:** {member.nick or 'ללא'}\n"
        f"**רולים:** {roles_mentions}\n"
        f"**זמן בשרת:** {time_str}"
    )

    if member.avatar:
        embed.set_thumbnail(url=member.avatar.url)

    class ClaimView(discord.ui.View):
        claimed = False

        @discord.ui.button(label="Claim Exit", style=discord.ButtonStyle.red)
        async def claim(self, interaction: discord.Interaction, button: discord.ui.Button):
            if self.claimed:
                await interaction.response.send_message("העזיבה כבר נתבעה", ephemeral=True)
                return
            self.claimed = True
            button.disabled = True
            await interaction.message.edit(view=self)
            await interaction.response.send_message(f"{interaction.user.mention} has claimed the exit")

    await channel.send(embed=embed, view=ClaimView())

@bot.tree.command(name="welcome-setup", description="הגדרת ערוץ הודעות כניסה")
@app_commands.describe(channel="הערוץ שיקבל הודעות כניסה")
async def welcome_setup(interaction: discord.Interaction, channel: discord.TextChannel):
    if interaction.user.id not in AUTHORIZED_USERS:
        await interaction.response.send_message("אין לך הרשאה להשתמש בפקודה זו", ephemeral=True)
        return

    guild_id = str(interaction.guild_id)
    if guild_id not in bot.config:
        bot.config[guild_id] = {}
    bot.config[guild_id]['welcome'] = channel.id
    bot.save_data()
    await interaction.response.send_message(f"ערוץ קבלת פנים הוגדר: {channel.mention}", ephemeral=True)

@bot.tree.command(name="leave-setup", description="הגדרת ערוץ הודעות עזיבה")
@app_commands.describe(channel="הערוץ שיקבל הודעות עזיבה")
async def leave_setup(interaction: discord.Interaction, channel: discord.TextChannel):
    if interaction.user.id not in AUTHORIZED_USERS:
        await interaction.response.send_message("אין לך הרשאה להשתמש בפקודה זו", ephemeral=True)
        return

    guild_id = str(interaction.guild_id)
    if guild_id not in bot.config:
        bot.config[guild_id] = {}
    bot.config[guild_id]['leave'] = channel.id
    bot.save_data()
    await interaction.response.send_message(f"ערוץ עזיבות הוגדר: {channel.mention}", ephemeral=True)
if __name__ == "__main__":
    keep_alive()

    token = os.getenv("discordkey")

    if not token:
        raise ValueError("discordkey environment variable not found")

    bot.run(token)

