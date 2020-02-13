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
			options: cmds.Greedy[OptionsConverter], 
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