from discord.ext import commands as cmds
from typing import Optional, Union

from .rpgcore import OptionsConverter, ModifierConverter, DiceConverter, Dice

class RPG(cmds.Cog):
	def __init__(self, bot):
		self.bot = bot

	@cmds.command(aliases=["r"], brief="Roll some dice")
	async def roll(
			self, 
			ctx, 
			options: cmds.Greedy[OptionsConverter(["x", "xx"])], 
			entries: cmds.Greedy[Union[ModifierConverter, DiceConverter]], 
			*, 
			tag: str = ""
		):
		"""
		Simulate the rolling of some dice.

		Supply a list of space-separated entries that are either dice, or flat numbers to add/subtract. Dice entries are in the form "XdY", where "X" is the number of dice to roll, and "Y" is the number of sides those dice have. If "X" is omitted, it defaults to 1. If "Y" is omitted, it defaults to 6. Both dice and flat number entries may contain signs ("+" or "-"). Any text after the list will be a title for the response.

		Supplying "F" or "Fate" as the dice's "size" will roll fate dice. These are six sided dice with "0"s on two faces, "+"s on two faces, and "-"s on the last two. These can't be exploded.

		Allowed options:
		-x Dice will explode (for every max result, a bonus (non-exploding) die is rolled)
		-xx Dice will explode, and those bonus dice will explode too, etc.
		"""

		for entry in entries:
			if isinstance(entry, Dice):
				if "xx" in options:
					entry.exexplode()
				elif "x" in options:
					entry.explode()

		# the message to be sent
		msg = ''

		# add tag if supplied
		if tag: msg += tag

		# open code block
		msg += "```\n"

		# add note if dice are exploding
		if "xx" in options:
			msg += f"* Dice are exploding recursively\n"
		elif "x" in options:
			msg += f"* Dice are exploding\n"

		# add entries list
		msg += "\n".join(map(str, entries))

		# add total
		msg += f"\n\nTotal: {sum(map(int, entries))}"

		# close code block
		msg += "\n```"

		await ctx.send(msg)

	@cmds.group(brief="gm commands")
	async def gm(self):
		"""
		A series of subcommands for gm use. 
		Only those with the gm role can use these.
		"""
		pass

	@gm.command(name="claim", brief="Claim to be the active gm")
	async def gm_claim(self):
		"""
		This command will claim you as the current active gm. 
		This is relevant to things such as getting the private x-card alerts.
		"""
		pass

	@cmds.group(invoke_without_command=True, aliases=["x"], brief="X-Card commands")
	async def xcard(self):
		"""
		Invokes the x-card. This indicates to the gm (and anyone else who's subscribed to x-card alerts) that the current topic of conversation is uncomfortable for you. 
		This is anonymous by default, and ought to be invoked from a direct message to me (the bot) to keep that anonymity.
		"""
		pass

	@xcard.command(name="public", brief="Make x-card invoke public")
	async def xcard_public(self):
		"""
		Makes an invocation of the x-card public. 
		This adds your username to the x-card announcement.
		Know that anyone can subscribe to these announcements, so more than just the gm may see your name. If you want to make your identity known only to the gm, use the "private" subcommand.
		"""
		pass

	@xcard.command(name="private", brief="Show the gm your identity")
	async def xcard_private(self):
		"""
		Make a normal, anonymous announcement of an x-card trigger, but also send a direct message to the active gm with your username.
		The gm will claim to be the active gm with the "gm claim" command. Anyone with the gm role can claim active gm. Nobody without that role can claim it.
		"""
		pass

	@xcard.command(name="subscribe", aliases=["sub"], brief="Subscribe to x-card alerts")
	async def xcard_subscribe(self):
		"""
		Gain access to the channel where alerts are sent whenever someone activates the x-card. These are usually anonymous.
		Note, this channel will mention everyone in it whenever the x-card is triggered.
		"""
		pass

	@xcard.command(name="unsubscribe", aliases=["unsub"], brief="Unsubscribe from x-card alerts")
	async def xcard_unsubscribe(self):
		"""
		Lose access to the x-card alert channel. See the documentation of the "subscribe" subcommand for more.
		"""
		pass