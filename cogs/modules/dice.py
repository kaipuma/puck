from functools import total_ordering
from random import randint, shuffle, choice
from typing import Union, List
import re

from discord.ext import commands as cmds

from .configs import dice_config as dcon

class NoMatchError(Exception): pass
class DiceError(cmds.CommandError): pass

@total_ordering
class BasicDie:
	"""A data container for a single numeric die roll"""
	__slots__ = ["value", "valid", "explosion"]

	def __init__(self, value: int, explosion: int = 0, valid: bool = True):
		self.value = value
		self.explosion = explosion
		self.valid = valid

	__int__ = lambda s: s.value
	__str__ = lambda s: str(s.value)
	__repr__ = lambda s: f"BasicDie({s}, {s.explosion}, {s.valid})"
	__eq__ = lambda s, o: s.value == int(o) if hasattr(o, "__int__") else NotImplemented
	__le__ = lambda s, o: s.value <= int(o) if hasattr(o, "__int__") else NotImplemented

class SpecialDie:
	"""A data container for a single special die roll"""
	__slots__ = ["symbols", "category", "total"]

	def __init__(self, category: str, result: Union[str, List[str]]):
		self.category = category
		if isinstance(result, str):
			self.symbols = [result]
		else:
			self.symbols = list(result)

		# count how many of each symbol is here
		# (more than three of any one will display as "SxN"
		# where S is the symbol and N is how many there are)
		counts = dict()
		reduced = self.reduce(self.symbols)
		for symb in reduced:
			if symb not in counts:
				counts[symb] = 0
			counts[symb] += 1

		# add any non-blank value to the "total" string
		# any occuring more than 3x is depicted once w/ that number
		self.total = ""
		blanks = dcon[category]["blank"]
		for symb in reduced:
			if symb not in blanks:
				if counts[symb] > 0:
					self.total += symb
				if counts[symb] > 3:
					self.total += f"x{counts[symb]}"
					counts[symb] = 0

		# default the total to the default value in the config
		if not self.total:
			self.total = dcon[category]["default"]

	def reduce(self, symbols):
		"""Reduce a list of symbols based on this category's configs"""
		symbols = symbols[:]
		if "reduce" in dcon[self.category]:
			for i in range(len(symbols)):
				for base, lst in dcon[self.category]["reduce"].items():
					if symbols[i] in lst:
						symbols[i] = base
		return symbols


	__str__ = lambda s: "".join(s.symbols)

	def __add__(self, other):
		# can only cancel with other dice in the same category
		if not isinstance(other, self.__class__) \
		or other.category != self.category:
			return NotImplemented

		# collect all the symbols from both sides
		all_symb = self.reduce(self.symbols + other.symbols)

		# the cancelation categories. anything in any list in each of these
		# will cancel with anything else in that list
		can_cats = dcon[self.category]["cancels"]

		# a place to count the symbols while working
		working = [{name:0 for name in cat} for cat in can_cats]

		# go through the symbols, finding which category they each belong to
		# if there's already another symbol in that category with a positive 
		# count, decrement it. otherwise, increment that symbol's count
		no_cat = []
		for symbol in all_symb:
			for i, cat in enumerate(can_cats):
				if symbol not in cat: continue
				for k, v in working[i].items():
					if v > 0 and k != symbol:
						working[i][k] -= 1
						break
				else:
					working[i][symbol] += 1
				break
			else:
				no_cat.append(symbol)

		# merge all remaining items
		result = no_cat
		for w in working:
			for k, v in w.items():
				result += [k]*v

		# return a new SpecialDie object with the canceled list
		return self.__class__(self.category, result)

class RollEntry:
	"""
	A base class for all variety of entries to the "roll" command.
	All subclasses of this will have a "_regex", which an argument will be checked against on __init__.
	If it fails, "NoMatchError" will be raised. Otherwise, its groups are stored in "_groups". Subclasses
	must define "invoke", "result". These represent the incoming argument and the generated results 
	respectively. "total" represents the numeric representation of the sum of the results, if applicable.
	"""
	__slots__ = ["invoke", "result", "total", "_groups"]
	_regex = re.compile(r"^$")

	def __init__(self, arg: str):
		match = self.match(arg)
		if match is None:
			raise NoMatchError(f"\"{arg}\" doesn't match the regex \"{self._regex.pattern}\".")
		self._groups = match.groups()

	def match(self, arg: str):
		return self._regex.match(arg)

class TagEntry(RollEntry):
	"""A simple RollEntry that accepts any value, for adding tags to rolls"""
	_regex = re.compile(r"^(.*)$", flags=re.S)
	__str__ = lambda s: s._groups[0]

class SignEntry(RollEntry):
	"""
	An entry in the "roll" command consisting of just a "+" or "-" (for when people forget to add a space).
	This uses "sign" instead of the standard "values" to store its one value
	"""
	__slots__ = ["sign"]
	_regex = re.compile(r"^([+-])$")

	def __init__(self, arg: str):
		super().__init__(arg)
		self.sign = -1 if arg == "-" else 1
		self.invoke = self.result = arg

class NumberEntry(RollEntry):
	"""
	An entry consisting of a single integer value, to add/subtract from totals.
	This foregos using "values" in favor of storing its one result directly in "total"
	"""
	_regex = re.compile(r"^([+-]?)(\d+)$")

	def __init__(self, arg: str):
		super().__init__(arg)
		self.total = int(self._groups[1])
		if self._groups[0] == "-":
			self.total *= -1
		self.invoke = self.result = f"{self.total:+}"

	def invert(self):
		self.total *= -1
		self.invoke = self.result = f"{self.total:+}"

class BasicEntry(RollEntry):
	"""An entry representing a basic numeric dice roll (e.g. 2d6, 1d20, etc.)"""
	__slots__ = ["override", "modifiers", "_values"]
	# the regex for all the possible modifiers
	_mod_regex = re.compile(r"\s*(xx|x|<=|>=|<|>|=|min|max|num|\+|-)\s*(\d*)\s*", flags=re.I)
	_regex = re.compile(fr"^([+-]?)(\d*)d(?:(\d+)-)?(\d+)((?:{_mod_regex.pattern})*)$", flags=re.I)
	# all the possible comparison modifiers, and their functions
	_comparisons = {
		"<=": int.__le__,
		">=": int.__ge__,
		"<" : int.__lt__,
		">" : int.__gt__,
		"=" : int.__eq__
	}

	def __init__(self, arg: str):
		super().__init__(arg)
		# setup some values to start
		self.override = None
		sign = -1 if self._groups[0] == "-" else 1
		pool = int(self._groups[1] or 1)
		minimum = int(self._groups[2] or 1)
		maximum = int(self._groups[3])
		# a function that randomly generates a new die from local values
		newval = lambda e=0: BasicDie(sign * randint(minimum, maximum), e)

		# generate the list of values to start
		self._values = []
		for _ in range(pool):
			self._values.append(newval())

		# collect up all the modifiers found, and their argument (default 1)
		self.modifiers = dict()
		for key, value in self._mod_regex.findall(self._groups[4]):
			self.modifiers[key] = int(value or 1)

		# generate the invoke, adding the optional minimum and 
		# modifier values as appropriate (e.g. 1d3-6 [min 3])
		self.invoke = f"{'-' if sign == -1 else ''}{pool}d"
		if minimum != 1:
			self.invoke += f"{minimum}-"
		self.invoke += str(maximum)
		for mod, val in self.modifiers.items():
			self.invoke += f" [{mod}"
			if val != 1 or mod in self._comparisons:
				self.invoke += f" {val}"
			self.invoke += "]"

		# parse the "xx" modifier (exploding recursively)
		if "xx" in self.modifiers:
			valid = list(range(maximum + 1 - self.modifiers["xx"], maximum + 1))
			nxt = self._values
			iteration = 1
			while len(nxt) and iteration <= 64:
				nxt = [newval(iteration) for n in nxt if n in valid]
				self._values.extend(nxt)
				iteration += 1

		# parse the "x" modifier (exploding dice)
		elif "x" in self.modifiers:
			valid = list(range(maximum + 1 - self.modifiers["x"], maximum + 1))
			self._values.extend(newval(1) for v in self._values if v in valid)

		# parse the numeric modifiers (an option in case someone forgets to add a
		# space between arguments). These are denoted with an explosion value of -1
		if "+" in self.modifiers:
			self._values.append(BasicDie(self.modifiers["+"], -1))
		if "-" in self.modifiers:
			self._values.append(BasicDie(-self.modifiers["-"], -1))

		# run the validate function. This checks all the modifiers that may 
		# change with an "invert" call, so as to be able to be called from there
		self.validate()

	def validate(self):
		# first set all entries to valid
		for value in self._values:
			value.valid = True

		# iterate over all comparisons in the modifiers list
		for mod in self._comparisons.keys():
			if mod not in self.modifiers:
				continue

			# mark any that fail the test as invalid (unless they're numeric modifiers)
			for v in self._values:
				if not self._comparisons[mod](int(v), self.modifiers[mod]):
					v.valid = v.explosion == -1

		# mark any values invalid as appropriate to min and max values
		for mod in ("min", "max"):
			if mod in self.modifiers:
				sort = sorted(self._values, reverse=(mod == "max"))
				for i in range(self.modifiers[mod], len(self._values)):
					sort[i].valid = sort[i].explosion == -1

		# set the override to the numer of valid values if "num" was used
		if "num" in self.modifiers:
			self.override = sum(v.valid for v in self._values)

	@property
	def result(self):
		# sort values by their explosion value, then by valid/invalid
		results = dict()
		for v in self._values:
			if v.explosion not in results:
				results[v.explosion] = {"valid":[], "invalid":[]}
			if v.valid:
				results[v.explosion]["valid"].append(v)
			else:
				results[v.explosion]["invalid"].append(v)

		# loop over every used explosion value, adding to the return string 
		# as appropriate (marking numeric modifiers with "()", and each 
		# iteration of explosions with "[]", as well as using ~~these~~ to
		# strike through any values sorted into the invalid lists)
		s = ""
		max_expl = max(results.keys())
		min_expl = min(results.keys())
		for i in range(min_expl, max_expl+1):
			if i == -1:
				s += "("
			elif i != 0:
				s += " ["

			if results[i]["invalid"]:
				s += f"~~{', '.join(map(str, results[i]['invalid']))}~~"
				if results[i]["valid"]:
					s += ", "

			if results[i]["valid"]:
				s += ", ".join(map(str, results[i]["valid"]))

			if i == -1:
				s += ") "
			elif i != 0:
				s += "]"

		# show the overide if it's set
		if self.override is not None:
			s += f" => {self.override}"

		return s

	@property
	def total(self):
		# return either the override, or the sum of all valid values
		if self.override is not None:
			return self.override
		else:
			return sum(map(int, (v for v in self._values if v.valid)))

	def invert(self):
		# first, invert the sign on the value of all BasicDie entries
		# in "_values", then adding/removing a "-" from the invoke as
		# needed, then run validate to refresh valid and override values
		for v in self._values:
			v.value *= -1
		if self.invoke[0] == "-":
			self.invoke = self.invoke[1:]
		else:
			self.invoke = "-" + self.invoke
		self.validate()

class SpecialEntry(RollEntry):
	"""An entry for special dice, as defined in the dice.json config file"""
	__slots__ = ["category", "die", "_values"]
	def __init__(self, arg: str):
		# this subclass will overwrite the base class's __init__ entirely
		# since there's more than one possible regex to match against

		# create then check the regexes based on the config data
		for name, data in dcon.items():
			aliases = sum(data["aliases"].values(), [])
			aliases = sorted(aliases, key=lambda a: len(a), reverse=True)
			regex_string = fr"(\d*){data['delimiter']}({'|'.join(aliases)})"
			match = re.match(regex_string, arg, flags=re.I)
			if match is not None:
				self._groups = match.groups()
				self.category = name
				break
		else:
			# if no regex matched, raise the appropriate error, like in the base
			raise NoMatchError(f"\"{arg}\" doesn't match any special die regex.")

		# collect some variables
		pool = int(self._groups[0] or 1)
		alias = self._groups[1]
		for name, aliases in dcon[self.category]["aliases"].items():
			if alias in aliases:
				self.die = name
				break
		faces = dcon[self.category]["faces"][self.die]

		# roll dice
		self._values = []
		for _ in range(pool):
			self._values.append(SpecialDie(self.category, choice(faces)))
		# define the invoke and results strings
		self.invoke = f"{pool}{dcon[self.category]['delimiter']}{self.die}"
		self.result = ", ".join(map(str, self._values))

	@property
	def total(self):
		if not self._values:
			return SpecialDie(self.category, dcon[self.category]["default"])
		result = self._values[0]
		for v in self._values[1:]:
			result += v

		return result

class RollConverter(cmds.Converter):
	async def convert(self, ctx, arg: str):
		# this order matters, since TagEntry is a catchall
		for cls in (BasicEntry, NumberEntry, SpecialEntry, SignEntry, TagEntry):
			try:
				return cls(arg)
			except NoMatchError:
				continue

		raise DiceError(f"Cannot convert {arg} to any RollEntry subclass")
