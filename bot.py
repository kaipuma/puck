from discord.ext import commands as cmds
from cogs import Other, RPG
import json

puck = cmds.Bot(command_prefix = "!")
puck.add_cog(Other(puck))
puck.add_cog(RPG(puck))
puck.help_command.cog = puck.cogs["Other"]

@puck.command(aliases=["stop", "exit"], hidden=True)
@cmds.is_owner()
async def quit(ctx):
	await puck.close()

if __name__ == '__main__':
	with open("configs/data.json", "r") as file:
		puck.data = json.load(file)

	with open("configs/token.txt", "r") as file:
		token = file.readline()
		
	puck.run(token)
