from typing import Optional, Union
from random import shuffle
import json
import re

from discord.ext import commands as cmds
import discord.utils as utils
from discord import Embed, Color

from .modules.dice import RollConverter, BasicEntry, NumberEntry, SignEntry, TagEntry, SpecialEntry
from .modules.configs import color_config as colcon

class RPG(cmds.Cog):
	def _parse_emoji(self, ctx, text):
		for name in set(re.findall(r":(\w+?):", text)):
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
			desc = f"They specifically mentioned \"{tag}\"\n{desc}"

		return ("@here", Embed(color = color, title = title, description = desc))

	def _getshared(self, ctx):
		"""Gets a list of xcard channels shared by the ctx.author and the bot"""
		channels = []
		with open("./data/xcard.json", "r") as file:
			data = json.load(file)
		# for any guild the bot is in
		for guild in ctx.bot.guilds:
			# skip any guild the sender isn't in
			if not guild.get_member(ctx.author.id): continue

			# find the channel in any shared guilds to send msg to
			if str(guild.id) in data and "general" in data[str(guild.id)]:
				# if a bot spam channel has been set, send it there
				channel_id = int(data[str(guild.id)]["general"])
				channels.append(guild.get_channel(channel_id))
			else:
				# otherwise, send it to the system channel
				syschan = guild.system_channel
				# last ditch, send it to the first channel listed
				channels.append(syschan or guild.text_channels[0])

		return channels

	@cmds.command(aliases=["r"], brief="Roll some dice")
	async def roll(self, ctx, entries: cmds.Greedy[RollConverter]):
		# first, loop over all the entries, inverting any that 
		# come after a bare "-", and categorizing them all
		categorized = {"numeric":[], "tags":[], "special":{}}
		invert_next = False
		for entry in entries:
			if isinstance(entry, BasicEntry) or isinstance(entry, NumberEntry):
				if invert_next:
					entry.invert()
					invert_next = False
				categorized["numeric"].append(entry)

			elif isinstance(entry, TagEntry):
				categorized["tags"].append(entry)

			elif isinstance(entry, SpecialEntry):
				if entry.category not in categorized["special"]:
					categorized["special"][entry.category] = []
				categorized["special"][entry.category].append(entry)

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
		totals = []
		if categorized["numeric"]:
			totals.append(sum(e.total for e in categorized["numeric"]))
		if categorized["special"]:
			for value in categorized["special"].values():
				subtotal = value[0].total
				for v in value[1:]:
					subtotal += v.total
				totals.append(subtotal.total)

		# create the embed and add the lists
		ebd = Embed(
			color = Color.from_rgb(*colcon["roll"]),
			title = self._parse_emoji(ctx, title),
		).add_field(
			name = f"Result{'' if len(entries) == 1 else 's'}:",
			value = self._parse_emoji(ctx, results),
			inline = False
		).add_field(
			name = f"Total{'' if len(totals) == 1 else 's'}:",
			value = self._parse_emoji(ctx, ", ".join(map(str, totals) or "0")),
			inline = False
		)

		# and send
		await ctx.send(embed=ebd)

	@cmds.command(aliases=["x"], brief="Invoke the x-card")
	async def xcard(self, ctx, *, tag: Optional[str] = ""):
		"""
		Invokes the x-card. The x-card is a device used to indicate that the current topic of conversation is making you uncomfortable. Please don't be embarrassed to use it, especially since it can be used anonymously (by sending the command to the bot in a direct message). It will send a message to the designated spam channel announcing that someone anonymous has invoked the x-card.
		"""

		msg, ebd = self._gencard("x", tag)
		for channel in self._getshared(ctx):
			await channel.send(msg, embed = ebd)

	@cmds.command(aliases=["o"], brief="Invoke the o-card")
	async def ocard(self, ctx, *, tag: Optional[str] = ""):
		"""
		Invokes the o-card. This is the inverse of the x-card. Using this indicates that you're loving the current role-play, as an encouragement. This sends a message to the designated spam channel announcing that someone anonymous has invoked the o-card.
		"""

		msg, ebd = self._gencard("o", tag)
		for channel in self._getshared(ctx):
			await channel.send(msg, embed = ebd)

	@cmds.group(invoke_without_command=True, aliases=["spectaculars", "spectacular"], brief="Commands for Spectaculars")
	async def spec(self, ctx):
		"""The group of commands for the Spectaculars tabletop rpg."""
		pass

	@spec.command(name="i", aliases=["init", "initiative"], brief="Randomize initiative")
	async def initiative(self, ctx, *choices: str):
		"""
		Given a list of names, output that list shuffled.
		Allows options to be given in the form "thisXnum", which will add "num" instances of "this" to the pool.
		For example, "Crash Paragon Nautica villainX3" would output a list six people long.
		Of note:
		- "X" isn't case sensitive
		- The number must be positive
		- Multi-word names can be accomplished by surrounding the whole choice in quotes (e.g. "Death Bladex4" would put four "Death Blade"s on the list).
		"""
		final = []
		for c in choices:
			# split all in the form thingXnum 
			base, mult = re.match(r"(.*?)(?:x(\d+)?$", c, flags=re.I).groups()
			# int(mult), or 1 if mult is None
			mult = int(mult or 1)
			for _ in range(mult):
				final.append(base)

		shuffle(final)
		ebd = Embed(
			color = Color.from_rgb(0, 0, 255),
			title = "Your shuffled initiative is:",
			description = "\n".join(final)
		)

		await ctx.send(embed=ebd)
