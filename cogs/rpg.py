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

	def _parse_emoji(self, ctx, text):
		for name in set(self.emoji_exp.findall(text)):
			emoji = utils.get(ctx.guild.emojis, name=name)
			if emoji is None: continue
			text = text.replace(f":{name}:", str(emoji))
		return text

	def _gencard(self, cardtype, tag = ""):
		"""Generates the message and embed for an x- or o-card invoke"""
		if cardtype == "x":
			title = "Someone has tapped the X card!"
			desc = "Please cease the current topic of conversation."
			color = Color.from_rgb(255, 0, 0)
		elif cardtype == "o":
			title = "Someone has tapped the O card!"
			desc = "Keep up the good work!"
			color = Color.from_rgb(0, 255, 0)

		if tag:
			desc += f"\nSpecifically they mentioned \"{tag}\"."

		return ("@here", Embed(color = color, title = title, description = desc))

	def _getshared(self, ctx):
		"""Gets a list of spam channels shared by the ctx.author and the bot"""
		channels = []
		data = ctx.bot.data
		# for any guild the bot is in
		for guild in ctx.bot.guilds:
			# skip any guild the sender isn't in
			if not guild.get_member(ctx.author.id): continue

			# find the channel in any shared guilds to send msg to
			if str(guild.id) in data and "spam" in data[str(guild.id)]:
				# if a bot spam channel has been set, send it there
				channel_id = int(ctx.bot.data[str(guild.id)]["spam"])
				channels.append(guild.get_channel(channel_id))
			else:
				# otherwise, send it to the system channel
				syschan = guild.system_channel
				# last ditch, send it to the first channel listed
				channels.append(syschan or guild.text_channels[0])

		return channels

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
			color = Color.from_rgb(0, 0, 255),
			title = f"Rolling: {ctx.message.content[len(ctx.invoked_with)+2:]}",
			description = desc or None
		)

		msg.add_field(
			name = f"Result{'s' if len(entries) > 1 else ''}:",
			value = self._parse_emoji(ctx, "\n".join(map(str, entries))),
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
			value = self._parse_emoji(ctx, ", ".join(totals)),
			inline = False
		)

		await ctx.send(tag, embed=msg)

	@cmds.command(aliases=["x"], brief="Invoke the x-card")
	async def xcard(self, ctx, tag: Optional[str] = ""):
		"""
		Invokes the x-card. The x-card is a device used to indicate that the current topic of conversation is making you uncomfortable. Please don't be embarrassed to use it, especially since it can be used anonymously (by sending the command to the bot in a direct message). It will send a message to the designated spam channel announcing that someone anonymous has invoked the x-card.
		"""

		msg, ebd = self._gencard("x", tag)
		for channel in self._getshared(ctx):
			await channel.send(msg, embed = ebd)

	@cmds.command(aliases=["o"], brief="Invoke the o-card")
	async def ocard(self, ctx, tag: Optional[str] = ""):
		"""
		Invokes the o-card. This is the inverse of the x-card. Using this indicates that you're loving the current role-play, as an encouragement. This sends a message to the designated spam channel announcing that someone anonymous has invoked the o-card.
		"""

		msg, ebd = self._gencard("o", tag)
		for channel in self._getshared(ctx):
			await channel.send(msg, embed = ebd)