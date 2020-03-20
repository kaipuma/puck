from discord.ext import commands as cmds
import discord
from random import randint, choices
from typing import Sequence
import re

class Dice:
	def __init__(self, pool: int, faces: Sequence):
		self.type = "Generic"
		self.pool = pool
		self.faces = list(faces)
		self.results = self.faces and choices(self.faces, k=pool)

	def __str__(self):
		s = f"{self.pool} of {self.faces}: "
		s += ", ".join(map(str, self.results))
		return s

class Modifier(Dice):
	def __init__(self, val: int, inverted: bool = False):
		super().__init__(1, [-val if inverted else val])
		self.inverted = inverted
		self.type = "Numeric"

	def total(self):
		return f"{int(self):+}"

	def __add__(self, other):
		if isinstance(other, Standard) or isinstance(other, self.__class__):
			return Modifier(int(self) + int(other), self.inverted)

		return NotImplemented

	def __int__(self):
		return -self.results[0] if self.inverted else self.results[0]

	def __str__(self):
		return f"{'-' if self.inverted else '+'}{self.results[0]}"

class Standard(Dice):
	max_explode = 100

	def __init__(self, pool: int, maximum: int, minimum: int = 1, inverted: bool = False):
		super().__init__(pool, range(minimum, maximum + 1))
		self.type = "Numeric"
		self.range = (minimum, maximum)
		self.inverted = inverted
		if inverted:
			self.results = [-i for i in self.results]
		self.explosions = []

	def explode(self):
		hits = sum(i == faces[-1] for i in self.results)
		rolls = self.faces and choices(self.faces, k=hits)
		if self.inverted: rolls = [-i for i in rolls]
		self.explosions.append(rolls)

	def exexplode(self):
		hits = sum(i == self.faces[-1] for i in self.results)
		rolls = self.faces and choices(self.faces, k=hits)
		if self.inverted: rolls = [-i for i in rolls]
		while hits:
			self.explosions.append(rolls)
			hits = sum(i == self.faces[-1] for i in rolls)
			rolls = self.faces and choices(self.faces, k=hits)
			if self.inverted: rolls = [-i for i in rolls]
			if len(self.explosions) > self.__class__.max_explode:
				break

	def total(self):
		return f"{int(self):+}"

	def __add__(self, other):
		if isinstance(other, Modifier):
			return Modifier(int(self) + int(other), other.inverted)

		elif not isinstance(other, self.__class__):
			return NotImplemented

		total = int(self) + int(other)
		ret = self.__class__(self.pool + other.pool, 0, 1)
		ret.results = self.results + other.results
		ret.explosions = self.explosions + other.explosions
		return ret

	def __int__(self):
		return sum(self.results) + sum(map(sum, self.explosions))

	def __str__(self):
		s = f"{self.pool}d"
		if self.range[0] == 1:
			s += f"{self.range[1]}: "
		else:
			s += f"{self.range[0]}-{self.range[1]}: "
		s += ", ".join(map(str, self.results))
		for ex in self.explosions:
			s += " " + str(ex)
		return s

class Fate(Dice):
	def __init__(self, pool: int):
		super().__init__(pool, ["+", "0", "-"])
		self.type = "Fate"

	def total(self):
		val = int(self)
		sign = "-" if val < 0 else "+"
		return (sign * val) or "0"

	def __add__(self, other):
		if not isinstance(other, self.__class__):
			return NotImplemented
		ret = self.__class__(self.pool + other.pool)
		ret.results = self.results + other.results
		return ret

	def __int__(self):
		s = "".join(self.results)
		return s.count("+") - s.count("-")

	def __str__(self):
		s = f"{self.pool}Fate: "
		s += ", ".join(self.results)
		return s

# Spectaculars rpg custom dice base
class Spec(Dice):
	emoji = {
		"hit":":green_square:",
		"miss":":red_square:"
	}
	choices = ("hit", "miss")
	empty = ""

	def __init__(self, pool):
		super().__init__(pool, self.choices)
		self.type = "Spectaculars"

	def total(self):
		return " ".join([self.emoji["hit"]] * abs(int(self))) or self.emoji["miss"]

	def __add__(self, other):
		if not isinstance(other, Spec):
			return NotImplemented

		# squash down to minimum dice, canceling if needed
		# get the class with the same sign as the total (default self)
		total = int(self) + int(other)
		if total * int(self) > 0 or total == 0:
			cls = self.__class__
		else:
			cls = other.__class__

		# instantiate new obj, and override results array
		ret = cls(abs(total))
		ret.results = ["hit"]*abs(total)
		return ret

	def __int__(self):
		val = self.results.count("hit")
		sign = 1 if isinstance(self, SpecAdvantage) else -1
		return sign * val

	def __str__(self):
		subtype = "Adv" if isinstance(self, SpecAdvantage) else "Chal"
		s = f"{self.pool}Spec{subtype}: "
		s += ", ".join(map(lambda k: self.emoji[k], self.results))
		return s

class SpecAdvantage(Spec):
	emoji = {
		"hit": ":SpecBoon:",
		"miss": ":white_medium_small_square:"
	}
	choices = ("hit",)*4 + ("miss",)*4

class SpecChallenge(Spec):
	emoji = {
		"hit": ":SpecDrawback:",
		"miss": ":black_medium_small_square:"
	}
	choices = ("hit",)*6 + ("miss",)*4

class DiceError(cmds.CommandError): pass
class DiceConverter(cmds.Converter):
	"""Converts dice in the form XdY"""
	# the possible delimiters
	# IMPORTANT: remember to put more general ones later, e.g. put "s" after "sw"
	# this will be used in a regex, so if "s" was before "sw", "sw" would never match
	delimiters = ["d", "f", "s"]
	# compile the main regex
	exp = re.compile(rf"([+-]?)(\d+)({'|'.join(delimiters)})(.*)", flags=re.I)
	# compile the modifier regex
	mod_exp = re.compile(r"^([+-]?)(\d+)$")
	# compile the "d" (default) delimiter's style regex
	d_exp = re.compile(r"(?:(\d*?)-)?(\d+)", flags=re.I)
	# compile the "s" (spectaculars) delimiter's style regex
	s_exp = re.compile(r"(?:pec(?:taculars)?)?([AC]).*", flags=re.I)

	async def convert(self, ctx, arg):
		# try to match the argument against the main regex
		match = self.exp.match(arg.lower())
		if match is None:
			# try to match it against the modifier regex
			mod_match = self.mod_exp.match(arg)
			if mod_match is None:
				raise DiceError("Invalid format")
			sign, val = mod_match.groups()
			is_inverted = sign == "-"
			return Modifier(int(val), is_inverted)

		# split the match groups
		sign, pool, delim, style = match.groups()
		is_inverted = sign == "-"
		pool = int(pool)

		# generate the appropriate Dice subclass
		if delim.lower() == "d":
			d_match = self.d_exp.match(style)
			if d_match is None:
				raise DiceError("Invalid format")
			minimum, maximum = d_match.groups()
			minimum = int(minimum or 1)
			maximum = int(maximum)
			return Standard(pool, maximum, minimum, is_inverted)

		elif delim.lower() == "f":
			return Fate(pool)

		elif delim.lower() == "s":
			s_match = self.s_exp.match(style)
			if s_match is None:
				raise DiceError("Invalid format")
			dice_type = s_match.groups()[0]
			if dice_type.lower() == "a":
				return SpecAdvantage(pool)
			else:
				return SpecChallenge(pool)

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
	def __init__(self, allowed = None, *args, **kwargs):
		super(*args, **kwargs)
		self.allowed = allowed

	async def convert(self, ctx, arg):
		# this won't work, since "--" will then be passed to the next converter
		# if arg.startswith("--"):
		# 	raise OptionsError("Explicit end of options list")
		if not arg.startswith("-"):
			raise OptionsError("Not a valid option")

		if "=" in arg[2:]:
			value = arg[arg.index("=")+1:]
			name = arg[1:arg.index("=")]
			if self.allowed is not None and name not in self.allowed:
				raise OptionsError("Not a valid option")
			return Option(name, value)
		else:
			name = arg[1:]
			if self.allowed is not None and name not in self.allowed:
				raise OptionsError("Not a valid option")
			return Option(name)

if __name__ == '__main__':
	c = SpecChallenge(3)
	a = SpecAdvantage(3)
	print(c, a, (a + c).total(), sep="\n")