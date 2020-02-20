from discord.ext import commands as cmds
import discord
from random import randint, choice
from enum import Enum, auto

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
	def __init__(self, allowed = None, *args, **kwargs):
		super(*args, **kwargs)
		self.allowed = allowed

	async def convert(self, ctx, arg):
		if arg.startswith("--"):
			raise OptionsError("Explicit end of options list")
		elif not arg.startswith("-"):
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

class SwEnum(Enum):
	BOOST = auto()
	ABILITY = auto()
	PROFICIENCY = auto()
	SETBACK = auto()
	DIFFICULTY = auto()
	CHALLENGE = auto()
	FORCE = auto()

	SUCCESS = auto()
	ADVANTAGE = auto()
	TRIUMPH = auto()
	FALURE = auto()
	THREAT = auto()
	DISPAIR = auto()
	LIGHT = auto()
	DARK = auto()

class Sw(Enum):
	S = SwEnum.SUCCESS
	A = SwEnum.ADVANTAGE
	TR = SwEnum.TRIUMPH
	F = SwEnum.FALURE
	T = SwEnum.THREAT
	DI = SwEnum.DISPAIR
	LS = SwEnum.LIGHT
	DS = SwEnum.DARK

class SwError(cmds.CommandError): pass

class SwDie:
	values = {
		SwEnum.BOOST: (tuple(), tuple(), (Sw.S,), (Sw.S, Sw.A), (Sw.A, Sw.A), (Sw.A,)),
		SwEnum.ABILITY: (tuple(), (Sw.S,), (Sw.S,), (Sw.S, Sw.S), (Sw.A,), (Sw.A,), (Sw.S, Sw.A), (Sw.A, Sw.A)),
		SwEnum.PROFICIENCY: (tuple(), (Sw.S,), (Sw.S,), (Sw.S, Sw.S), (Sw.S, Sw.S), (Sw.A,), (Sw.S, Sw.A), (Sw.S, Sw.A), (Sw.S, Sw.A), (Sw.A, Sw.A), (Sw.A, Sw.A), (Sw.TR,)),
		SwEnum.SETBACK: (tuple(), tuple(), (Sw.F,), (Sw.F,), (Sw.T,), (Sw.T,)),
		SwEnum.DIFFICULTY: (tuple(), (Sw.F,), (Sw.F, Sw.F), (Sw.T,), (Sw.T,), (Sw.T,), (Sw.T, Sw.T), (Sw.F, Sw.T)),
		SwEnum.CHALLENGE: (tuple(), (Sw.F,), (Sw.F,), (Sw.F, Sw.F), (Sw.F, Sw.F), (Sw.T,), (Sw.T,), (Sw.F, Sw.T), (Sw.F, Sw.T), (Sw.T, Sw.T), (Sw.T, Sw.T), (Sw.DI,)),
		SwEnum.FORCE: ((Sw.DS,), (Sw.DS,), (Sw.DS,), (Sw.DS,), (Sw.DS,), (Sw.DS,), (Sw.DS, Sw.DS), (Sw.LS,), (Sw.LS,), (Sw.LS, Sw.LS), (Sw.LS, Sw.LS), (Sw.LS, Sw.LS))
	}

	aliases = {
		SwEnum.BOOST: ("boost", "blue"),
		SwEnum.ABILITY: ("ability", "green"),
		SwEnum.PROFICIENCY: ("proficiency", "yellow"),
		SwEnum.SETBACK: ("setback", "black"),
		SwEnum.DIFFICULTY: ("difficulty", "purple"),
		SwEnum.CHALLENGE: ("challenge", "red"),
		SwEnum.FORCE: ("force", "white")
	}

	@classmethod
	def validate(cls, text):
		if isinstance(text, SwEnum): return text
		text = text.lower()

		matches = {"strong": set(), "weak": set()}
		for die, aliases in cls.aliases.items():
			for alias in aliases:
				if alias.startswith(text):
					matches["strong"].add(die)
				elif text in alias:
					matches["weak"].add(die)

		if len(matches["strong"]) == 1:
			return matches["strong"].pop()
		elif len(matches["weak"]) == 1:
			return matches["weak"].pop()
		else:
			return list(matches["strong"] | matches["weak"])

	def __init__(self, raw_name):
		name = type(self).validate(raw_name)
		if not isinstance(name, SwEnum):
			if name:
				raise SwError(f"Too many possible matches for {raw_name}: {str(name)[1:-1]}")
			raise SwError(f"No matches for {raw_name}.")

		self.name = name
		self.values = type(self).values[name]

	def roll(self):
		return choice(self.values)
