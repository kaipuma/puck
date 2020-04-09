import json

from discord.ext import commands as cmds

from cogs import Other, RPG

puck = cmds.Bot(command_prefix = "!")
puck.add_cog(Other(puck))
puck.add_cog(RPG(puck))
puck.help_command.cog = puck.cogs["Other"]

@puck.command(aliases=["stop", "exit"], hidden=True)
@cmds.is_owner()
async def quit(ctx):
	await puck.close()

@puck.event
async def on_ready():
	with open("./configs/emoji.json", "r") as file:
		emojis = json.load(file)

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

if __name__ == '__main__':
	with open("configs/data.json", "r") as file:
		puck.data = json.load(file)

	with open("configs/token.txt", "r") as file:
		token = file.readline()
		
	puck.run(token)
