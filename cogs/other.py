from discord.ext import commands as cmds
import json

class Other(cmds.Cog):
	@cmds.group(name="set", brief="set various variables")
	async def cmd_set(self, ctx):
		"""
		Set one of the following variables for the bot:
		*spam - set this channel as the one to send general messages to. 

		* Server owner only.
		"""
		pass

	@cmd_set.command(name="spam", brief="set the spam channel")
	@cmds.is_owner()
	async def cmd_set_spam(self, ctx):
		"""
		Set this channel as the one the bot will post in.
		"""
		guild = str(ctx.guild.id)
		channel = str(ctx.channel.id)

		if channel not in ctx.bot.data:
			ctx.bot.data[guild] = dict()

		ctx.bot.data[guild]["spam"] = channel

		with open("configs/data.json", "w") as file:
			json.dump(ctx.bot.data, file)
