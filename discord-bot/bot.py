import discord
from discord.ext import commands
import mafic
import yaml
import json
import sqlite3

with open('../config/config.yaml', 'r') as file:
    config = yaml.safe_load(file)

class discordBot(discord.Bot):
    def __init__(self, description=None, *args, **options):
        super().__init__(description, *args, **options)
        self.node_pool = mafic.NodePool(self)
        self.loop.create_task(self.add_nodes())
        

    async def add_nodes(self):
        await self.node_pool.create_node(
            host=config["symphsonic"]["mafic_ip"],
            port=config["symphsonic"]["mafic_port"],
            label="MAIN",
            password=config["symphsonic"]["lavalink_password"],
        )

bot: discord.Bot = discordBot(intents=discord.Intents.all())
bot.load_extension(f"music")

owner_id = config["symphsonic"]["bot_owner_id"]
if (owner_id is not None) or (owner_id.lower() == "default"):
    bot.owner_id = owner_id

@bot.event
async def on_ready():
    sqlconnection = sqlite3.connect("./data/guilds.db")
    sqlcursor = sqlconnection.cursor()
    registered_guilds = sqlcursor.execute("SELECT guild_id FROM guilds").fetchall()
    registered_guild_id_list = []
    for registered_guild in registered_guilds:
        registered_guild_id_list.append(registered_guild[0])

    for guild in bot.guilds:
        if guild.id not in registered_guild_id_list:
            sqlcursor.execute(f'INSERT INTO guilds(guild_name, guild_id) VALUES ("{guild.name}", {guild.id})')
            sqlconnection.commit()

    print(f"SymphSonic is ready. (Logged into {bot.user.name}#{bot.user.discriminator} - ID: {bot.user.id})")

print("SymphSonic is starting.")
bot.run(config["symphsonic"]["bot_token"])
