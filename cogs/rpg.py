from typing import Optional, Union
import json
import re

from discord.ext import commands as cmds
import discord.utils as utils
from discord import Embed, Color

from .modules.dice import RollConverter, BasicEntry, NumberEntry, SignEntry, TagEntry, SpecialEntry
from .modules.configs import color_config as colcon
from .modules.configs import dice_config as dcon

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
			color = Color.from_rgb(*colcon["xcard"])
		elif cardtype == "o":
			title = "Someone has tapped the O card!"
			desc = "Keep up the good work!"
			color = Color.from_rgb(*colcon["ocard"])

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

	@cmds.group(aliases=["r"], brief="Roll some dice", invoke_without_command=True)
	async def roll(self, ctx, entries: cmds.Greedy[RollConverter]):
		"""
		Roll some number of dice with potential modifiers.
		The documentation for this command is quite long, detailing exactly what can and cannot be supplied as an argument. As such, it has been moved to the "roll docs" subcommand. Either call that command, or call the help command on it to read the documentation. Please consider doing so in direct messages with me if you wish not to have long messages in this channel.
		"""
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

	@roll.command(name="docs", aliases=["doc"], brief="docs for the roll command")
	async def roll_docs(self, ctx):
		"""
		Roll some number of dice with potential modifiers.
		Each entry is separated by a space. The core of an entry is the dice. This is in the form "XdY", where X and Y are numbers. This will roll X dice with sides numbered 1 through Y.
		Alternatively, the entry core could be in the form "XdM-Y", where X and Y are the same, but M specifies a different minimum value. For example, "3d4-6" will roll three dice, each with faces of 4, 5, and 6. Lastly, a "-" may be placed immediately before the entry to negate the result. If the value for X is omitted, the default is 1

		An entry can also have modifiers applied to it. Each modifier must be typed IMMEDIATELY after the core, with no spaces in between. The exception to this is if you put the whole entry in quotes. Some examples of this are shown below in the Examples section. Most modifiers have the option to have a number value afterwards. This follows the same rules for spaces noted above. Most of these values default to 1 if not supplied. Any exceptions are noted. The possible modifiers are described here:

		min : Accept only the smallest roll. A supplied value states how many minimum values to accept.
		max : Accept only the largest roll. A supplied value states how many maximum values to accept.
		< : Accept any roll less than (but not equal to) the supplied value.
		> : Accept any roll greater than (but not equal to) the supplied value.
		= : Accept any roll exactly equal to the supplied value.
		<= : Accept any roll less than or equal to the supplied value.
		>= : Accept any roll greater than or equal to the supplied value.
		x : Dice will explode. This rolls an additional die of the same type for every result that is equal to the maximum result. The supplied value can change how many values will explode. For example, a value of 2 will make dice explode on a roll of any of the top 2 possible results.
		xx : Dice will explode, and those dice can explode, as could those, etc. Besides the recursive behavior, this is identical to the "x" modifier.
		num : Instead of summing all the valid results, this will count how many results are valid and use that as the total. This does not accept a value.
		+ : This will add the supplied value to the roll as a flat modifier.
		- : This will subtract the supplied value from the roll as a flat modifier.

		In addition to standard rolls, entries can be some special values. An entry consisting of just a number, with an optional "+" or "-" in front is added (or subtracted) from the total as a flat modifier. Additionally, any entry of just a sign will apply that sign to the next entry (this is an option to cover cases when extra spaces are added. i.e. "- 3d6" is the same as "-3d6", as "-4" and "- 4" are too).
		The last variety of roll is of special dice. These are specified in a configuration file, and may vary. They always come in the form "XdY", however the "d" is some other character(s), and Y may be non-numeric, depending on the special dice used. Results from these dice are summed and displayed separately from the numeric dice and modifiers. No special dice can take any of the above modifiers that numeric dice can.

		Any entry not matching one of the above types is considered a tag. All tags will be put together and displayed at the top of the response.

		Examples:
		2d6 : roll two six sided dice.
		d6 : roll one six sided dice (the first value defaults to 1).
		2d6x : roll 2d6. for every 6 rolled in the initial two dice, roll another d6.
		2d6xx : roll 2d6. for every 6 rolled, roll another d6. if any more 6's are rolled, repeat.
		2d6x3 : same as 2d6x, but roll another d6 for each 6, 5, or 4 rolled.
		2d6max : roll 2d6, but only keep the maximum result.
		4d6max2 : roll 4d6, but only keep the top 2 results.
		2d6min : roll 2d6, but only keep the minimum result.
		2d6>=3 : roll 2d6, but only keep any result greater than or equal to 3.
		2d6>3 : roll 2d6, but only keep any result greater than, but not equal to 3.
		2d6-3 : roll 2d6, then subtract 3 from the total result.
		2d6>=3num : roll 2d6. The result will be however many rolls are >= 3 (either 0, 1, or 2).
		2d6num : since no results were excluded (like with "max" or "<"), this always results in a 2
		2d6 >=3 num : this is invalid, since there are spaces between the dice and the modifiers.
		"2d6 >=3 num" : this is valid, because the whole roll is surrounded by quotes ("").
		"2d6 >= 3 num" : spaces may also occur between modifiers and their values when quoted.

		To see what special dice are available, see the "sdocs" subcommand.
		"""
		await ctx.send_help(ctx.command)

	@roll.command(name="sdocs", aliases=["sdoc"], brief="docs for special dice")
	async def roll_sdocs(self, ctx):
		"""
		Since what special dice are available can change, but this documentation cannot, please call this command to see what they currently are.
		"""
		ebd = Embed(
			color = Color.from_rgb(*colcon["roll"]),
			title = self._parse_emoji(ctx, "Available special dice"),
			description = "Each category will say what it is, then what the delimiter is (the \"d\" in \"XdY\"), then will have a list of possible dice in that category. Each dice will show its name, then will list the possible options for \"Y\" that will roll that dice. Frequently this will include longer versions, as well as shorter aliases."
		)

		for category, data in dcon.items():
			title = f"{category} : {data['delimiter']}"
			desc = {}
			for name in data["faces"].keys():
				desc[name] = data["aliases"][name]

			values = []
			for name, aliases in desc.items():
				values.append(f"{name}: {', '.join(aliases)}")

			ebd.add_field(
				name = self._parse_emoji(ctx, title),
				value = self._parse_emoji(ctx, "\n".join(values)),
				inline = False
			)

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
