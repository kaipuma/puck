from collections import OrderedDict, Counter
from copy import deepcopy
from functools import total_ordering
from random import randint, shuffle, choice
import re
import shelve
from typing import Union, List

from discord.ext import commands as cmds

from .configs import dice_config as dcon, rolls_config as rcon

@total_ordering
class Die:
	"""Represents a single numeric die roll"""
	__slots__ = "value", "depth", "valid"
	def __init__(self, value:int, depth:int = 0, valid:bool = True):
		self.value = value
		self.valid = valid
		self.depth = depth

	__str__ = lambda s: str(s.value)
	__repr__ = lambda s: f"Die({s.value!r}, {s.depth!r}, {s.valid!r})"

	# these and @total_ordering allow this class to be sorted
	__le__ = lambda s, o: s.value <= o.value
	__eq__ = lambda s, o: s.value == o.value

class SpecialDie:
	"""Represents a single special die roll"""
	__slots__ = "value", "name", "category"
	def __init__(self, value:str, category:str):
		if isinstance(value, list):
			self.value = value[:]
		else:
			self.value = [value]
		self.category = category

	@property
	def reduced(self):
		values = Counter(self.value[:])
		config = dcon[self.category]

		# first, reduce any values to their veneric version
		if "reduce" in config:
			for reduce_to, reduce_from in config["reduce"].items():
				# move all values of any items in reduce_from to reduce_to
				for v in reduce_from:
					values[reduce_to] += values[v]
					values[v] = 0

		# next, cancel any elements that do so
		if "cancels" in config:
			for group in config["cancels"]:
				for _ in range(32):
					# get the two values of this group with the
					# largest number of present items in values
					_, first = max((values[v], v) for v in group)
					_, second = max((values[v], v) for v in group if v != first)

					# if either is zero, then this group is canceled
					if not (values[first] and values[second]): break

					# otherwise, reduce both values by one
					values.subtract((first, second))

		# then remove any elements designated as blanks
		if "blank" in config:
			blanks = config["blank"]
			if isinstance(blanks, str):
				blanks = [blanks]

			for blank in blanks:
				values[blank] = 0

		# return the reduced copy
		return SpecialDie(list(values.elements()), self.category)

	def __add__(self, other):
		if not isinstance(other, type(self)) \
		or not self.category == other.category:
			return NotImplemented

		value = self.value + other.value
		return type(self)(value, self.category)

	def __str__(self):
		values = Counter(self.value)
		config = dcon[self.category]
		if "max consecutive" in config:
			for val, count in list(values.items()):
				if count > config["max consecutive"]:
					values[val] = 0
					values[val + f"x{count}"] = 1
		return " ".join(sorted(values.elements())) or config["default"]

	__deepcopy__ = lambda s, m: type(s)(s.value, s.category)
	__repr__ = lambda s: f"SpecialDie({s.value!r}, {s.category!r})"

class DiceList(list):
	"""A list of Dice, automatically generated from the supplied values"""
	def __init__(self, size:int, minv:int, maxv:int, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.override = None
		self.size = size
		self.minv = minv
		self.maxv = maxv
		for _ in range(size):
			self.append(Die(randint(minv, maxv)))

	def new(self, depth = 0, valid = True):
		self.append(Die(randint(self.minv, self.maxv), depth, valid))

	@property
	def result(self):
		data = dict()
		for die in self:
			dp = die.depth
			if dp not in data:
				data[dp] = {True:[], False:[]}
			data[dp][die.valid].append(die)

		lists = []
		for depth, dice in sorted(data.items()):
			if depth == -1:
				parens = ("(", ")")
			elif depth == 0:
				parens = ("", "")
			else:
				parens = ("[", "]")

			s = parens[0]
			if data[depth][False]:
				s += f"~~{', '.join(map(str, data[depth][False]))}~~"
				if data[depth][True]:
					s += ", "
			lists.append(s + ", ".join(map(str, data[depth][True])) + parens[1])

		s = " ".join(lists)
		if isinstance(self.override, bool):
			s += f" -> {'Success' if self.override else 'Failure'}"
		elif self.override is not None:
			s += f" -> {self.override}"

		return s

	@property
	def total(self):
		return sum(map(lambda d: d.valid and d.value, self))

	def __str__(self):
		s = super().__str__()
		if self.override is not None:
			s += f"({self.override})"
		return s

class Entry:
	__slots__ = "_parent", "_children", "invoke", "result", "token"
	_allowed_additions = ()
	def __init__(self, token = None):
		self.token = token
		self._parent = None
		self._children = []
		self.invoke = ""
		self.result = ""

	def add(self, item):
		if not isinstance(item, Entry):
			raise ValueError("Added item must be a subclass of Entry")

		if type(item) in self._allowed_additions:
			self._children.append(item)
			item._parent = self
			return True

		if self._parent is None:
			return False

		return self._parent.add(item)

	def as_tag(self):
		s = ""
		if self.token is not None:
			s += self.token.raw

		for child in self._children:
			s += child.as_tag()

		return s

	def evaluate(self, dice:DiceList = None):
		return self

class RootEntry:
	"""A base class to track which classes can be roots of their Entry trees."""
	__slots__ = ()

class OneChild(Entry):
	"""Any Entry which can accept only one child"""
	__slots__ = ()
	def add(self, item):
		if len(self._children) > 0:
			if self._parent is None:
				return False
			return self._parent.add(item)

		return super().add(item)

class NoChild(Entry):
	"""Any Entry which can accept no children"""
	__slots__ = ()
	def add(self, item):
		if self._parent is None:
			return False
		return self._parent.add(item)

class Number(Entry, RootEntry):
	"""Represents a number, wither as an argument for a modifier, or a flat addition to a roll."""
	__slots__ = "value"
	def __init__(self, value, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.value = int(value)
		self.invoke = f"[{self.value:+}]"
		self.result = f"{self.value:+}"

	def evaluate(self, dice:DiceList = None, flat:int = 0):
		if dice is None:
			return self
		dice.append(Die(self.value, depth=-1))

class Flat(Number):
	"""Represents a flat modifier to a numeric roll (but not an argument to another modifier)."""
	__slots__ = ()

class Modifier(OneChild):
	"""Represents a modifier to a numeric roll."""
	__slots__ = "name", "_default", "_hidden", "_comp", "_evaluated"
	_allowed_additions = (Number,)
	# this stores the defalt value, and whether to hide that 
	# value if it's the one used, and any comparison function
	_configs = {
		"xx": (1, True, None), 
		"x": (1, True, None), 
		"<=": (0, False, int.__le__), 
		">=": (0, False, int.__ge__), 
		"<": (0, False, int.__lt__), 
		">": (0, False, int.__gt__), 
		"=": (0, False, int.__eq__), 
		"min": (1, True, None), 
		"max": (1, True, None)
	}
	def __init__(self, name, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.name = name
		self._evaluated = False
		configs = self._configs[name]
		self._default = configs[0]
		self._hidden = configs[1]
		self._comp = configs[2]
		self.invoke = f"[{self.name}]"
		if not self._hidden:
			self.invoke = f"[{self.name} {self._default}]"

	def evaluate(self, dice:DiceList, flat:int = 0):
		value = self._default
		if self._children:
			value = self._children[0].value
		
		self.invoke = f"[{self.name} {value}]"
		if self._hidden and value == self._default:
			self.invoke = f"[{self.name}]"

		if self.name in ("min", "max"):
			ordered = sorted(dice, reverse=(self.name == "max"))
			for i, die in enumerate(ordered):
				if die.depth >= 0 and i >= value:
					die.valid = False

		elif self._comp is not None:
			for die in dice:
				if die.depth >= 0 and not self._comp(die.value+flat, value):
					die.valid = False

		elif self.name == "x":
			# never evaluate this modifier more than once
			if self._evaluated: return self
			thold = dice.maxv - value
			toadd = sum(d.value > thold for d in dice if d.depth >= 0)
			for _ in range(toadd):
				dice.new(depth=1)

		elif self.name == "xx":
			# never evaluate this modifier more than once
			if self._evaluated: return self
			thold = dice.maxv - value
			toadd = sum(d.value > thold for d in dice if d.depth >= 0)
			level = 1
			while (toadd > 0) and (level < 64):
				for _ in range(toadd):
					dice.new(depth=level)
					# only decrement toadd if the value misses the threshold
					toadd -= dice[-1].value <= thold 
				level += 1

		self._evaluated = True
		return self

class Counters(Modifier, NoChild):
	"""Represents a modifier to a numeric roll that counts valid dice"""
	__slots__ = ()
	# this stores the defalt value, and whether to hide that 
	# value if it's the one used, and any comparison function
	_configs = {
		"num": (0, True, None),
		"count": (0, True, None),
		"pas": (0, True, None),
		"success": (0, True, None)
	}

	def evaluate(self, dice:DiceList, flat:int = 0):
		if self.name in ("num", "count"):
			dice.override = sum(d.valid for d in dice)

		elif self.name in ("pas", "success"):
			dice.override = any(d.valid for d in dice)

		self._evaluated = True
		return self

class Ranged(Entry, RootEntry):
	"""Represents a dice roll in the form "XrY-Z", which rolls X dice numbered Y-Z."""
	__slots__ = "sign", "pool", "minv", "maxv", "roll", "_invoke"
	_allowed_additions = Number, Flat, Modifier
	def __init__(self, sign, pool, minv, maxv, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.sign = "-" if sign == "-" else "+"
		self.pool = int(pool or 1)
		self.minv = int(minv)
		self.maxv = int(maxv)
		self.roll = DiceList(self.pool, self.minv, self.maxv)
		self._invoke = f"{self.sign}{self.pool}r{self.minv}-{self.maxv}"
		self.invoke = self._invoke

	def evaluate(self):
		flat = sum(c.value for c in self._children if isinstance(c, Flat))
		for child in self._children:
			child.evaluate(self.roll, flat=flat)

		self.result = self.roll.result
		self.invoke = self._invoke
		for mod in self._children:
			self.invoke += " " + mod.invoke
		return self

	@property
	def total(self):
		if self.roll.override is None:
			return self.roll.total

		if isinstance(self.roll.override, bool):
			return self.roll.override

		t = self.roll.override
		for mod in self._children:
			if isinstance(mod, Flat):
				t += mod.value

		return t

class Basic(Ranged, RootEntry):
	"""Represents a dice roll in the form "XdY", which rolls X Y-sided dice."""
	__slots__ = ()
	def __init__(self, sign, pool, maxv, *args, **kwargs):
		super().__init__(sign, pool, 1, maxv, *args, **kwargs)
		self._invoke = f"{self.sign}{self.pool}d{self.maxv}"
		self.invoke = self._invoke

class Special(Entry, RootEntry):
	"""Represents any roll of dice defined in the dice.json config file"""
	__slots__ = "pool", "name", "category", "alias", "roll"
	def __init__(self, pool, name, category, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.category = category
		self.pool = int(pool or 1)
		self.alias = name
		config = dcon[category]

		# if this is a dummy class for addition,
		if self.alias == "":
			self.name = ""
			rawrolls = ("" for _ in range(self.pool))

		else:
			self.name = next(k for k, v in config["aliases"].items() if name in v)
			rawrolls = (choice(config["faces"][self.name]) for _ in range(self.pool))

		self.roll = tuple(SpecialDie(r, category) for r in rawrolls)
		self.invoke = f"{self.pool}{config['delimiter']}{self.name}"
		self.result = ", ".join(str(r) for r in self.roll)

	@property
	def total(self):
		t = deepcopy(self.roll[0])
		for r in self.roll[1:]:
			t += r
		return t

	def __deepcopy__(self, memo):
		new = type(self)(self.pool, self.alias, self.category)
		new.roll = deepcopy(self.roll, memo)
		new.invoke = f"{new.pool}{config['delimiter']}{new.name}"
		new.results = ", ".join(str(r) for r in new.roll)
		return new

	def __add__(self, other):
		if not isinstance(other, type(self)) \
		or not self.category == other.category:
			return NotImplemented

		new = deepcopy(self)
		if self.name != other.name:
			new.alias = new.name = ""
		
		allrolls = self.roll + other.roll
		new.roll = type(new).reduce(allrolls, new.category)

class Tag(Entry):
	"""Represents miscellaneous other text used to tag a roll."""
	_allowed_additions = Modifier, Number, Flat, Counters
	def __init__(self, value, *args, **kwargs):
		super().__init__(*args, **kwargs)
		self.value = value

class MasterTag(Entry, RootEntry):
	"""Each roll will have one MasterTag that has all other tags as children."""
	_allowed_additions = (Tag,)

	@property
	def is_empty(self):
		return not self._children

class Token:
	__slots__ = "name", "args", "raw", "subname"
	# all the basic regexes for different possible elements of a "roll" command
	# the first group collects the entire raw sting used
	_regexes = OrderedDict(
		basic = r"([+-]?)(\d*)d(\d+)",
		range = r"([+-]?)(\d*)r(\d+)-(\d+)",
		flat = r"([+-]\d+)",
		number = r"(\d+)",
		counters = r"(num|count|pas|success)",
		modifier = r"(xx|x|<=|>=|<|>|=|min|max)"
	)
	_master_regex = "|".join(fr"(?P<{k}>{v}\s*)" for k, v in _regexes.items())

	@classmethod
	def _get_special_regexes(cls):
		"""Get a dict of regexes for special dice defined by the config file"""
		regexes = dict()
		for category, data in dcon.items():
			# flatten the lists of aliases
			aliases = [re.escape(i) for l in data["aliases"].values() for i in l]
			aliases = "|".join(aliases)
			# get the delimiter
			delim = re.escape(data['delimiter'])
			# make the regex string
			regexes[category] = fr"(?:(?<=\s)|^)(\d*){delim}({aliases})(?=\s|$)"

		return regexes

	@classmethod
	def parse(cls, arg):
		"""Parse a string into tokens"""
		# prepare the master regex
		sregs = cls._get_special_regexes()
		master = "|".join(fr"(?P<special_{k}>{v}\s*)" for k, v in sregs.items())
		master += "|" + cls._master_regex
		master += r"|(?P<tag>(\S*\s*))"

		tokens = []
		# iterate over all matches
		for match in re.finditer(master, arg, flags=re.I):
			# collect the groups that recieved values
			groups = []
			for group in match.groups():
				if group is not None:
					groups.append(group)

			raw = groups[0]
			args = tuple(groups[1:])
			name = match.lastgroup

			# create the token based on if it's special or not
			special = re.match(r"special_(.+)", name)
			if special is not None:
				tokens.append(cls("special", raw, args, special.group(1)))
			else:
				tokens.append(cls(name, raw, args))

		return tokens

	def __init__(self, name, raw, args, subname=None):
		self.name = name
		self.raw = raw
		self.args = args
		self.subname = subname

	__str__ = lambda s: f"{s.name}: {s.args}"
	__repr__ = lambda s: f"Token({s.name!r}, {s.args!r})"

class Roll:
	# a dict of classes that represent the entry types
	# the keys are the same as the Token._regexes, plus "special" and "tag"
	_classes = {
		"basic": Basic,
		"range": Ranged,
		"flat": Flat,
		"number": Number,
		"counters": Counters,
		"modifier": Modifier,
		"special": Special,
		"tag": Tag
	}

	def __init__(self, tokens):
		self.tokens = tokens
		self.tag = MasterTag()
		self.raw = " ".join(map(lambda t:t.raw.strip(), tokens))

		# here we turn each token into a full "Entry" subclass instance
		# then add each into a series of tree structures for evaluating
		# "prev" will track the last "Entry" subclass instance created
		prev = None
		self.bases = []
		for token in tokens:
			# first get the appropriate class, and make the instance
			cls = self._classes[token.name]
			args = token.args
			if token.name == "special":
				new = cls(*args, token=token, category=token.subname)
			else:
				new = cls(*args, token=token)

			# any tags (and whitespace) get added to the master tag. this should never fail
			if isinstance(new, Tag):
				self.tag.add(new)

			# if this isn't the first token, try to add it to the prev tree
			elif prev is not None:
				success = prev.add(new)

				# if it fails and is a possible root, add it to bases
				# otherwise, raise an error
				if success is False:
					if not isinstance(new, RootEntry):
						raise ValueError(f"Cannot fit \"{new!r}\" in tree.")
					self.bases.append(new)

			# if it's the first token
			else:
				# and it's a valid root, add it to bases
				if isinstance(new, RootEntry):
					self.bases.append(new)

				# otherwise, try to add it to a tag, raising an error if that fails
				else:
					newtag = Tag("")
					success = newtag.add(new)
					if success is False:
						raise ValueError(f"\"{new!r}\" cannot be a base or tag.")
					self.tag.add(newtag)

			# set the next "prev" value to this token's class, if applicable
			prev = new

		# set self.tag to None if no tags were added
		if self.tag.is_empty:
			self.tag = None

	def evaluate(self):
		for base in self.bases:
			base.evaluate()
		return self

	@property
	def num_total(self):
		result = None
		for base in self.bases:
			if isinstance(base, (Number, Ranged)):
				if not isinstance(base.total, bool):
					result = (result or 0) + base.total

			elif isinstance(base, Number):
				result = (result or 0) + base.value

		return result

	@property
	def other_totals(self):
		success = None
		specials = {}
		for base in self.bases:
			# add any boolean numeric results
			if isinstance(base, (Number, Ranged)):
				if isinstance(base.total, bool):
					if success is None: success = True
					success &= base.total

			# add any special dice results
			elif isinstance(base, Special):
				if base.category in specials:
					specials[base.category] += base.total
				else:
					specials[base.category] = base.total

		results = []
		if success is not None:
			results.append("Success" if success else "Failure")

		for sdie in specials.values():
			results.append(str(sdie.reduced))

		return results

	@property
	def totals(self):
		num = self.num_total
		if num is not None:
			return [str(num)] + self.other_totals
		return self.other_totals

class TokenConverter(cmds.Converter):
	async def convert(self, ctx, arg: str):
		return Token.parse(arg)

class RollConverter(cmds.Converter):
	async def convert(self, ctx, arg: str):
		return Roll(Token.parse(arg))

class PresetConverterError(cmds.CommandError): pass
class PresetConverter(cmds.Converter):
	async def convert(self, ctx, arg: str):
		arg = arg.lower()
		# check global configs first
		for name, text in rcon.items():
			if arg == name:
				return Token.parse(text)

		with shelve.open("data/presets.shelf") as shelf:
			# then check if there's such a preset for this channel
			if "channel" in shelf \
			and str(ctx.channel.id) in shelf["channel"] \
			and arg in shelf["channel"][str(ctx.channel.id)]:
				return shelf["channel"][str(ctx.channel.id)][arg]

			# last, check if there's such a preset for this user
			if "user" in shelf \
			and str(ctx.author.id) in shelf["user"] \
			and arg in shelf["user"][str(ctx.author.id)]:
				return shelf["user"][str(ctx.author.id)][arg]

		raise PresetConverterError(f"Could not find preset for {arg}")