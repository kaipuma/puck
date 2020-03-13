from discord.ext import commands as cmds
import discord.utils as utils
from discord import Embed, Color
from typing import Optional, Union
import re

from .rpgcore import OptionsConverter, DiceConverter, Standard

class RPG(cmds.Cog):
	# compile the regex for discord emoji
	emoji_exp = re.compile(r":(\w+?):")

	def __init__(self, bot):
		self.bot = bot

	def parse_emoji(self, ctx, text):
		for name in set(self.emoji_exp.findall(text)):
			emoji = utils.get(ctx.guild.emojis, name=name)
			if emoji is None: continue
			text = text.replace(f":{name}:", str(emoji))
		return text

	@cmds.command(aliases=["r"], brief="Roll some dice")
	async def roll(
			self, 
			ctx, 
			options: cmds.Greedy[OptionsConverter(["x", "xx"])], 
			entries: cmds.Greedy[Union[DiceConverter]], 
			*, 
			tag: str = ""
		):
		"""
		Simulate the rolling of some dice.

		Supply a list of space-separated entries that are either dice, or flat numbers to add/subtract. Dice entries are in the form "XdY", where "X" is the number of dice to roll, and "Y" is the sides those dice have. Both standard dice and flat number entries may contain signs ("+" or "-"). Any text after the list will be a title for the response.

		Some special dice are also usable. These are accessed by replacing the "d" in "XdY" with something else. The options are listed here:
		f - Fate dice. These are d6s with 2 faces each of "+", "-", and "0". the "Y" part of "XdY" for these are ignored
		s - Special dice for the Spectaculars rpg system. The options for "Y" are "advantage" and "challenge", or "a" and "c" for short.
		Note, none of these are case sensitive.

		Allowed options:
		-x standard dice will explode (for every max result, a bonus (non-exploding) die is rolled)
		-xx standard dice will explode, and those bonus dice will explode too, etc.
		"""

		for entry in entries:
			if isinstance(entry, Standard):
				if "xx" in options:
					entry.exexplode()
				elif "x" in options:
					entry.explode()

		desc = ""
		if "xx" in options:
			desc += f"* Dice are exploding recursively\n"
		elif "x" in options:
			desc += f"* Dice are exploding\n"

		msg = Embed(
			color = Color.from_rgb(0, 255, 0),
			title = f"Rolling: {ctx.message.content[len(ctx.invoked_with)+2:]}",
			description = desc or None
		)

		msg.add_field(
			name = f"Result{'s' if len(entries) > 1 else ''}:",
			value = self.parse_emoji(ctx, "\n".join(map(str, entries))),
			inline = False
		)

		# organize dice by their categories
		categorized = dict()
		for e in entries:
			if e.type not in categorized:
				categorized[e.type] = []
			categorized[e.type].append(e)

		# add total(s)
		totals = []
		for cat in categorized.values():
			total = cat[0]
			for val in cat[1:]:
				total += val

			totals.append(total.total())

		msg.add_field(
			name = f"Total{'s' if len(categorized) > 1 else ''}:",
			value = self.parse_emoji(ctx, ", ".join(totals)),
			inline = False
		)

		await ctx.send(tag, embed=msg)