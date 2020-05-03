from asyncio import Lock
import json
import os
import shelve

from discord.ext import commands as cmds

from cogs.rpg import RPG
from cogs.other import Other

puck = cmds.Bot(command_prefix = "!")
puck.add_cog(Other())
puck.add_cog(RPG())
puck.help_command.cog = puck.cogs["Other"]

@puck.command(aliases=["stop", "exit"], hidden=True)
@cmds.is_owner()
async def quit(ctx):
	await puck.close()

@puck.event
async def on_ready():
	# read the emoji config
	with open("./configs/emoji.json", "r") as file:
		emojis = json.load(file)

	# upload any required emoji not already existing
	for guild in puck.guilds:
		for path, name in emojis.items():
			if any(e.name == name for e in guild.emojis): continue
			with open(path, "rb") as file:
				try:
					print("Uploading emoji:", name)
					await guild.create_custom_emoji(
						name=name,
						image=file.read(),
						reason="required emoji"
					)
				except BaseException as e:
					print(e)
	print("Done updating emoji")

	# clear the timers data file on reboot
	if os.path.isfile("data/timers.shelf"):
		os.remove("data/timers.shelf")

# change the working directory to the bot root directory
os.chdir(os.path.dirname(__file__))
# get the token from the config file
try:
	with open("configs/token.txt", "r") as file:
		token = file.readline()
# if no token has been set, tell the user
except:
	print("Please create the file \"configs/token.txt\", and place the bot token within it.")
# if the token is gathered successfully, run the bot
else:
	puck.run(token)
