from discord.ext import commands as cmds
from typing import Optional, Union

from .rpgcore import OptionsConverter, ModifierConverter, DiceConverter, Dice, SwEnum, SwDie

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

	@cmds.command(aliases=["starwars"], brief="Roll Star Wars dice")
	async def sw(self, ctx, *, dice: str):
		"""
		Simulate the result of rolling dice for the Fantasy Flight Games Star Wars RPG. The dice pool is constructed by listing pairs of number, dice combos. For example:
		3 boost, 2 green, 1 prof, 3 difficulty, 1 force

		Dice names can be given in many forms, as seen above. The real name of the die can be used (such as "boost" or "difficulty"), or the color of the die (like "green" or "red"), or some substring of those names (such as "prof" being short for "proficiency", or "purp" short for "purple").
		Shortened names only work if they're unique (for example, "bl" could be for "blue" or "black", so is invalid). 
		The number of those dice to roll must be a numeric value. So "3" is valid, but "three" is not. Additionally, the value is required, even if it's only one of that die.
		Lastly, any non-alpha-numeric characters are ignored. So feel free to separate the list by commas, or ampersands, or nothing, at your leisure.
		For example, "1g1y2d1f" is a valid command, though not advised, as it's harder for a human to see that you wanted to roll 1 green, 1 yellow, 2 difficulty, and 1 force die.
		"""
		# remove all non-alpha-numeric characters
		dice = "".join(filter(str.isalnum, dice))
		cval = ""
		ctype = str
		tokens = []
		for c in dice:
			if ctype is int and c.isdigit()\
			or ctype is str and c.isalpha():
				cval += c
			else:
				tokens.append(cval)
				cval = ""
				ctype = int if ctype is str else str

		print(tokens)
