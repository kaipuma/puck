from collections import Counter
from typing import Optional, Union
import json
import re
import shelve

from discord.ext import commands as cmds
import discord.utils as utils
from discord import Embed, Color

from .modules.dice import TokenConverter, PresetConverter, Roll
from .modules.configs import color_config as colcon
from .modules.configs import dice_config as dcon
from .modules.configs import rolls_config as rcon

class RPG(cmds.Cog):
	def __init__(self, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self._force_points = {}
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
	async def roll(self, ctx, preset: Optional[PresetConverter] = [], *, roll: Optional[TokenConverter] = []):
		"""
		Roll some number of dice with potential modifiers.
		The documentation for this command is quite long, detailing exactly what can and cannot be supplied as an argument. As such, it has been moved to the "roll docs" subcommand. Either call that command, or call the help command on it to read the documentation. Please consider doing so in direct messages with me if you wish not to have long messages in this channel.
		"""
		# convert arguments to a Roll object
		roll = Roll(preset + roll)

		# call evaluate to apply all modifiers
		roll.evaluate()

		# create all the strings to be used in the embed
		title = f"Rolling \"{roll.raw}\"" if roll.tag is None else roll.tag.as_tag()
		results = "".join(f"\n{b.invoke}: {b.result}" for b in roll.bases)
		totals = ", ".join(roll.totals) or "No dice rolled"
		plural = "" if len(roll.bases) == 1 else "s"

		# check if the roll is hidden
		if roll.hidden:
			results = "[REDACTED]"

		# create the embed and add the values
		ebd = Embed(
			color = Color.from_rgb(*colcon["roll"]),
			title = self._parse_emoji(ctx, title),
		).add_field(
			name = f"Result{plural}:",
			value = self._parse_emoji(ctx, results),
			inline = False
		).add_field(
			name = f"Total{plural}:",
			value = self._parse_emoji(ctx, totals),
			inline = False
		)

		# and send
		await ctx.send(embed=ebd)

	@roll.command(name="docs", aliases=["doc"], brief="docs for the roll command")
	async def roll_docs(self, ctx):
		"""
		Roll some number of dice with potential modifiers.
		Each entry is separated by some space. The core of an entry is the dice. This is in the form "XdY", where X and Y are numbers. This will roll X dice with sides numbered 1 through Y.
		Alternatively, the entry core could be in the form "XrM-Y" to specify a "range" of values to be rolled from. X and Y are the same, but M specifies a different minimum value. For example, "3r4-6" will roll three dice, each with faces of 4, 5, and 6.
		Lastly, a "-" may be placed immediately before the entry to negate the result. If the value for X is omitted, the default is 1

		An entry can also have modifiers applied to it. Some examples of this are shown below in the Examples section. Most modifiers have the option to have a number value afterwards. Most of these values default to 1 if not supplied. Any exceptions are noted. The possible modifiers are described here:

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
		count : Alias for "num"
		pas : This will result in a "success" if any of the dice rolled are accepted, and a "Failure" otherwise. Putting this on multiple parts of a roll requires all to pass.
		success: Alias for "pas"
		+ : This will add the supplied value to the roll as a flat modifier.
		- : This will subtract the supplied value from the roll as a flat modifier.

		In addition to standard rolls, entries can be some special values. An entry consisting of just a number, with an optional "+" or "-" in front is added (or subtracted) from the total as a flat modifier. 
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
		Since which special dice are available can change, but this documentation cannot, please call this command to see what they currently are.
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

	@roll.group(name="preset", aliases=["pset"], brief="view and create presets", invoke_without_command=True)
	async def roll_preset(self, ctx, name: Optional[PresetConverter] = None):
		if name is None:
			# strt with any global presets
			ps = set(rcon.keys())
			with shelve.open("data/presets.shelf") as shelf:
				# check if there's presets for this channel
				if "channel" in shelf and str(ctx.channel.id) in shelf["channel"]:
					ps.update(shelf["channel"][str(ctx.channel.id)].keys())

				# check if there's presets for this user
				if "user" in shelf and str(ctx.author.id) in shelf["user"]:
					ps.update(shelf["user"][str(ctx.author.id)].keys())

			await ctx.send(f"The possible presets for {ctx.author.mention} in this channel are: " + ", ".join(ps))
			return

		roll = " ".join(map(lambda t: t.raw.strip(), name))
		await ctx.send(f"That preset for you here would roll \"{roll}\"")

	@roll_preset.command(name="set", aliases=["s"], brief="set a user preset")
	async def roll_preset_set(self, ctx, name: str, *, roll: TokenConverter):
		name = name.lower()
		with shelve.open("data/presets.shelf") as shelf:
			if "user" not in shelf:
				shelf["user"] = {}

			# this and the "shelf["user"] = udict" below are
			# to manage writing to mutable shelf entries
			udict = shelf["user"]

			uid = str(ctx.author.id)
			if uid not in udict:
				print("setting uid")
				udict[uid] = {}

			udict[uid][name] = roll
			shelf["user"] = udict
			await ctx.send("Preset set, try it out!")

	@roll_preset.command(name="remove", aliases=["r"], brief="remove a user preset")
	async def roll_preset_remove(self, ctx, name: str):
		name = name.lower()
		with shelve.open("data/presets.shelf") as shelf:
			if "user" not in shelf:
				shelf["user"] = {}

			# this and the "shelf["user"] = udict" below are
			# to manage writing to mutable shelf entries
			udict = shelf["user"]

			uid = str(ctx.author.id)
			if uid not in udict or name not in udict[uid]:
				await ctx.send("No such user preset defined for you.")
				return

			del udict[uid][name]
			shelf["user"] = udict
			await ctx.send("Preset removed.")

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

	async def _send_force_points(self, ctx, mod = None, new = None):
		catid = ctx.channel.category_id
		if catid not in self._force_points:
			self._force_points[catid] = Counter({"light":0, "dark":0})
		points = self._force_points[catid]

		if new is not None:
			if new["light"] < 0 or new["dark"] < 0:
				await ctx.send("Cannot set points below zero.\nPoints not adjusted.")
			else:
				points["light"] = new["light"]
				points["dark"] = new["dark"]

		elif mod is not None:
			if (points + mod).most_common()[-1][1] < 0:
				await ctx.send("Points cannot go below zero.\nPoints not adjusted.")
			else:
				points.update(mod)

		lsebd = Embed(
			title = f"Light side: {points['light']}",
			color = Color.from_rgb(*colcon["lightside"])
		)
		dsebd = Embed(
			title = f"Dark side: {points['dark']}",
			color = Color.from_rgb(*colcon["darkside"])
		)

		await ctx.send(embed=lsebd)
		await ctx.send(embed=dsebd)

	@cmds.group(aliases=["sw"], brief="Starwars commands", invoke_without_command=True)
	async def starwars(self, ctx):
		"""A group of commands for starwars rpgs"""
		await ctx.send_help(ctx.command)

	@starwars.command(name="light", aliases=["l"], brief="Flip a light-side point")
	async def starwars_light(self, ctx, num: Optional[int] = 1):
		"""Flip one or more light side points to dark side points."""
		await self._send_force_points(ctx, mod = Counter(light = -num, dark = num))

	@starwars.command(name="dark", aliases=["d"], brief="Flip a dark-side point")
	async def starwars_dark(self, ctx, num: Optional[int] = 1):
		"""Flip one or more dark side points to light side points."""
		await self._send_force_points(ctx, mod = Counter(light = num, dark = -num))

	@starwars.command(name="clear", aliases=["c"], brief="Clear force points")
	async def starwars_clear(self, ctx, light: Optional[int] = 0, dark: Optional[int] = 0):
		"""Clear all light  and dark side points. Optionally also set a new pool of them."""
		await self._send_force_points(ctx, new = Counter(light = light, dark = dark))

	@starwars.command(name="set", aliases=["s"], brief="Set force points")
	async def starwars_set(self, ctx, light: int, dark: int):
		"""Set the pool of light and dark side force points"""
		await self._send_force_points(ctx, new = Counter(light = light, dark = dark))

	@starwars.command(name="points", aliases=["p"], brief="List force points")
	async def starwars_points(self, ctx):
		"""Show the pool of light and dark side force points"""
		await self._send_force_points(ctx)
