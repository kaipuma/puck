from typing import Optional, Union
from random import shuffle
import re

from discord.ext import commands as cmds
import discord.utils as utils
from discord import Embed, Color

from .modules import RollConverter, BasicEntry, NumberEntry, SignEntry, TagEntry

class RPG(cmds.Cog):
	# compile the regex for discord emoji
	emoji_exp = re.compile(r":(\w+?):")

	def __init__(self, bot):
		self.bot = bot

	def _parse_emoji(self, ctx, text):
		for name in set(self.emoji_exp.findall(text)):
			emoji = utils.get(ctx.guild.emojis, name=name)
			if emoji is None: continue
			text = text.replace(f":{name}:", str(emoji))
		return text

	@cmds.command(aliases=["r"], brief="Roll some dice")
	async def roll(self, ctx, entries: cmds.Greedy[RollConverter]):
		# first, loop over all the entries, inverting any that 
		# come after a bare "-", and categorizing them all
		categorized = {"numeric":[], "tags":[]}
		invert_next = False
		for entry in entries:
			if isinstance(entry, BasicEntry) or isinstance(entry, NumberEntry):
				if invert_next:
					entry.invert()
					invert_next = False
				categorized["numeric"].append(entry)

			elif isinstance(entry, TagEntry):
				categorized["tags"].append(entry)

			elif isinstance(entry, SignEntry) and entry.sign == -1:
				invert_next = not invert_next

		# next, generate the embed title. Either the supplied text, or a generic
		# "Rolling: [dice]" using the entries' .invoke props (ignoring signs and tags)
		excl = (TagEntry, SignEntry)
		if categorized["tags"]:
			title = " ".join(map(str, categorized["tags"]))
		else:
			title = f"Rolling: {', '.join(e.invoke for e in entries if e.__class__ not in excl)}"

		# gather the results list (ignoring tags and signs), and the totals list
		results = []
		results = "\n".join(f"{e.invoke}: {e.result}" for e in entries if e.__class__ not in excl)
		totals = dict()
		totals["numeric"] = sum(e.total for e in categorized["numeric"])

		# create the embed and add the lists
		ebd = Embed(
			color = Color.from_rgb(0, 0, 255),
			title = self._parse_emoji(ctx, title),
		).add_field(
			name = f"Result{'' if len(entries) == 1 else 's'}:",
			value = self._parse_emoji(ctx, results),
			inline = False
		).add_field(
			name = f"Total{'' if len(totals) == 1 else 's'}:",
			value = self._parse_emoji(ctx, ", ".join(map(str, totals.values()))),
			inline = False
		)

		# and send
		await ctx.send(embed=ebd)


# class RPG(cmds.Cog):
# 	# compile the regex for discord emoji
# 	emoji_exp = re.compile(r":(\w+?):")
# 	# compile the regex for multiplying e.g. "thisx5"
# 	# match only positive numbers, otherwise match all as group 1
# 	mult_exp = re.compile(r"(.*?)(?:[xX](?=(?!0))(\d+))?$")

# 	def __init__(self, bot):
# 		self.bot = bot

# 	def _parse_emoji(self, ctx, text):
# 		for name in set(self.emoji_exp.findall(text)):
# 			emoji = utils.get(ctx.guild.emojis, name=name)
# 			if emoji is None: continue
# 			text = text.replace(f":{name}:", str(emoji))
# 		return text

# 	def _gencard(self, cardtype, tag = ""):
# 		"""Generates the message and embed for an x- or o-card invoke"""
# 		if cardtype == "x":
# 			title = "Someone has tapped the X card!"
# 			desc = "Please cease the current topic of conversation."
# 			color = Color.from_rgb(255, 0, 0)
# 		elif cardtype == "o":
# 			title = "Someone has tapped the O card!"
# 			desc = "Keep up the good work!"
# 			color = Color.from_rgb(0, 255, 0)

# 		if tag:
# 			desc += f"\nSpecifically they mentioned \"{tag}\"."

# 		return ("@here", Embed(color = color, title = title, description = desc))

# 	def _getshared(self, ctx):
# 		"""Gets a list of spam channels shared by the ctx.author and the bot"""
# 		channels = []
# 		data = ctx.bot.data
# 		# for any guild the bot is in
# 		for guild in ctx.bot.guilds:
# 			# skip any guild the sender isn't in
# 			if not guild.get_member(ctx.author.id): continue

# 			# find the channel in any shared guilds to send msg to
# 			if str(guild.id) in data and "spam" in data[str(guild.id)]:
# 				# if a bot spam channel has been set, send it there
# 				channel_id = int(ctx.bot.data[str(guild.id)]["spam"])
# 				channels.append(guild.get_channel(channel_id))
# 			else:
# 				# otherwise, send it to the system channel
# 				syschan = guild.system_channel
# 				# last ditch, send it to the first channel listed
# 				channels.append(syschan or guild.text_channels[0])

# 		return channels

# 	@cmds.command(aliases=["r"], brief="Roll some dice")
# 	async def roll(
# 			self, 
# 			ctx, 
# 			options: cmds.Greedy[OptionsConverter(["x", "xx"])], 
# 			entries: cmds.Greedy[Union[DiceConverter]], 
# 			*, 
# 			tag: str = ""
# 		):
# 		"""
# 		Simulate the rolling of some dice.

# 		Supply a list of space-separated entries that are either dice, or flat numbers to add/subtract. Dice entries are in the form "XdY", where "X" is the number of dice to roll, and "Y" is the sides those dice have. Both standard dice and flat number entries may contain signs ("+" or "-"). Any text after the list will be a title for the response.

# 		Some special dice are also usable. These are accessed by replacing the "d" in "XdY" with something else. The options are listed here:
# 		f - Fate dice. These are d6s with 2 faces each of "+", "-", and "0". the "Y" part of "XdY" for these are ignored
# 		s - Special dice for the Spectaculars rpg system. The options for "Y" are "advantage" and "challenge", or "a" and "c" for short.
# 		Note, none of these are case sensitive.

# 		Allowed options:
# 		-x standard dice will explode (for every max result, a bonus (non-exploding) die is rolled)
# 		-xx standard dice will explode, and those bonus dice will explode too, etc.
# 		"""

# 		for entry in entries:
# 			if isinstance(entry, Standard):
# 				if "xx" in options:
# 					entry.exexplode()
# 				elif "x" in options:
# 					entry.explode()

# 		desc = ""
# 		if "xx" in options:
# 			desc += f"* Dice are exploding recursively\n"
# 		elif "x" in options:
# 			desc += f"* Dice are exploding\n"

# 		msg = Embed(
# 			color = Color.from_rgb(0, 0, 255),
# 			title = f"Rolling: {ctx.message.content[len(ctx.invoked_with)+2:]}",
# 			description = desc or None
# 		)

# 		msg.add_field(
# 			name = f"Result{'s' if len(entries) > 1 else ''}:",
# 			value = self._parse_emoji(ctx, "\n".join(map(str, entries))),
# 			inline = False
# 		)

# 		# organize dice by their categories
# 		categorized = dict()
# 		for e in entries:
# 			if e.type not in categorized:
# 				categorized[e.type] = []
# 			categorized[e.type].append(e)

# 		# add total(s)
# 		totals = []
# 		for cat in categorized.values():
# 			total = cat[0]
# 			for val in cat[1:]:
# 				total += val

# 			totals.append(total.total())

# 		msg.add_field(
# 			name = f"Total{'s' if len(categorized) > 1 else ''}:",
# 			value = self._parse_emoji(ctx, ", ".join(totals)),
# 			inline = False
# 		)

# 		await ctx.send(tag, embed=msg)

# 	@cmds.command(aliases=["x"], brief="Invoke the x-card")
# 	async def xcard(self, ctx, *, tag: Optional[str] = ""):
# 		"""
# 		Invokes the x-card. The x-card is a device used to indicate that the current topic of conversation is making you uncomfortable. Please don't be embarrassed to use it, especially since it can be used anonymously (by sending the command to the bot in a direct message). It will send a message to the designated spam channel announcing that someone anonymous has invoked the x-card.
# 		"""

# 		msg, ebd = self._gencard("x", tag)
# 		for channel in self._getshared(ctx):
# 			await channel.send(msg, embed = ebd)

# 	@cmds.command(aliases=["o"], brief="Invoke the o-card")
# 	async def ocard(self, ctx, *, tag: Optional[str] = ""):
# 		"""
# 		Invokes the o-card. This is the inverse of the x-card. Using this indicates that you're loving the current role-play, as an encouragement. This sends a message to the designated spam channel announcing that someone anonymous has invoked the o-card.
# 		"""

# 		msg, ebd = self._gencard("o", tag)
# 		for channel in self._getshared(ctx):
# 			await channel.send(msg, embed = ebd)

# 	@cmds.group(invoke_without_command=True, aliases=["spectaculars", "spectacular"], brief="Commands for Spectaculars")
# 	async def spec(self, ctx):
# 		"""The group of commands for the Spectaculars tabletop rpg."""
# 		pass

# 	@spec.command(name="i", aliases=["init", "initiative"], brief="Randomize initiative")
# 	async def initiative(self, ctx, *choices: str):
# 		"""
# 		Given a list of names, output that list shuffled.
# 		Allows options to be given in the form "thisXnum", which will add "num" instances of "this" to the pool.
# 		For example, "Crash Paragon Nautica villainX3" would output a list six people long.
# 		Of note:
# 		- "X" isn't case sensitive
# 		- The number must be positive
# 		- Multi-word names can be accomplished by surrounding the whole choice in quotes (e.g. "Death Bladex4" would put four "Death Blade"s on the list).
# 		"""
# 		final = []
# 		for c in choices:
# 			# split all in form thingXnum 
# 			base, mult = self.mult_exp.match(c).groups()
# 			# int(mult), or 1 if mult is None
# 			mult = mult and int(mult) or 1
# 			for _ in range(mult):
# 				final.append(base)

# 		shuffle(final)
# 		ebd = Embed(
# 			color = Color.from_rgb(0, 0, 255),
# 			title = "Your shuffled initiative is:",
# 			description = "\n".join(final)
# 		)

# 		await ctx.send(embed=ebd)
