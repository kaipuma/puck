import discord
from discord.ext import commands as cmds
from typing import Optional, Union
from random import randint, choice

class Dice:
	max_explode = 100

	def __init__(self, pool: int, size: int, sign: int = 1):
		self.pool = pool
		self.size = size
		self.sign = sign
		result = lambda: 0 if size == 0 else randint(1, size)
		self.results = [sign * result() for _ in range(pool)]

	def explode(self):
		result = lambda: 0 if self.size == 0 else randint(1, self.size)
		self.results += [self.sign * result() for r in self.results if abs(r) == self.size]

	def exexplode(self, iteration=0):
		if iteration >= Dice.max_explode: return
		bonus = sum(map(lambda r: abs(r) == self.size, self.results))
		if not bonus: return
		dice = Dice(bonus, self.size, self.sign)
		dice.exexplode(iteration+1)
		self.results += dice.results

	def __int__(self):
		return sum(self.results)

	def __str__(self):
		s = f"{self.pool}d{self.size}: "
		s += ", ".join(map(str, self.results))
		return s

class Fate(Dice):
	def __init__(self, pool: int):
		self.pool = pool
		self.size = "F"
		self.sign = 1
		self.results = [choice(("+", "0", "-")) for _ in range(pool)]

	def __int__(self):
		s = "".join(self.results)
		return s.count("+") - s.count("-")

class DiceError(cmds.CommandError): pass
class DiceConverter(cmds.Converter):
	"""Converts dice in the form XdY"""
	async def convert(self, ctx, arg):
		# split across the "d"
		args = arg.split("d")
		if len(args) != 2:
			raise DiceError("Invalid number of 'd' delimiters")

		# collect values, or their defaults
		pool = args[0] or "1"
		size = args[1] or "6"

		# extract & count signs 
		signs = {"+":1, "-":-1}
		sign = 1 

		if pool[0] in signs:
			sign *= signs[pool[0]]
			# check again in case of "-dY" etc. args
			pool = pool[1:] or "1"

		if size[0] in signs:
			sign *= signs[size[0]]
			size = size[1:] or "6"

		try:
			pool = int(pool)
			if size.upper() in ("F", "FATE"):
				return Fate(pool)
			size = int(size)
			return Dice(pool, size, sign)
		except:
			raise DiceError(f"{arg} is not in a proper form for dice")

class Modifier(int):
	def __str__(self):
		s = " +" if self >= 0 else " "
		s += str(int(self)) + ": "
		s += str(int(self))
		return s

class ModifierError(cmds.CommandError): pass
class ModifierConverter(cmds.Converter):
	"""Converts modifiers of the form "(+)Z" or "-Z" """
	async def convert(self, ctx, arg):
		try: return Modifier(arg)
		except: raise ModifierError(f"{arg} is not a number")

class Option:
	"""Represents a command option"""
	def __init__(self, name, arg = None):
		self.name = name
		self.arg = arg

	def __eq__(self, other):
		return other == self.name

class OptionsError(cmds.CommandError): pass
class OptionsConverter(cmds.Converter):
	"""Converts command options"""
	async def convert(self, ctx, arg):
		if arg.startswith("--"):
			raise OptionsError("Explicit end of options list")
		elif not arg.startswith("-"):
			raise OptionsError("Not a valid option")

		if "=" in arg[2:]:
			value = arg[arg.index("=")+1:]
			name = arg[1:arg.index("=")]
			return Option(name, value)
		else:
			name = arg[1:]
			return Option(name)

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