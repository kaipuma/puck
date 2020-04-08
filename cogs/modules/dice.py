from functools import total_ordering
from random import randint, shuffle
import re

from configs import dice_config as dcon

class NoMatchError(Exception): pass
class ModifierError(Exception): pass

class RollEntry:
	__slots__ = ["invoke", "values", "result", "_groups"]
	_regex = re.compile(r"^$")

	def __init__(self, arg: str):
		match = self.match(arg)
		if match is None:
			raise NoMatchError(f"\"{arg}\" doesn't match the regex \"{self._regex.pattern}\".")
		self._groups = match.groups()

	def match(self, arg: str):
		return self._regex.match(arg)

class SignEntry(RollEntry):
	_regex = re.compile(r"^([+-])$")

	def __init__(self, arg: str):
		super().__init__(arg)
		self.values = [-1 if arg == "-" else 1]
		self.invoke = self.result = arg

	def invert(self):
		self.values[0] *= -1
		self.invoke = "-" if self.values[0] < 0 else "+"
		self.result = self.invoke

class NumberEntry(RollEntry):
	_regex = re.compile(r"^([+-]?)(\d+)$")

	def __init__(self, arg: str):
		super().__init__(arg)
		self.values = [int(self._groups[1])]
		if self._groups[0] == "-":
			self.values[0] *= -1
		self.invoke = f"{self.values[0]:+}"
		self.result = self.invoke

	def invert(self):
		self.values[0] *= -1
		self.invoke = f"{self.values[0]:+}"
		self.result = self.invoke

@total_ordering
class BasicDie:
	__slots__ = ["value", "valid", "explosion"]

	def __init__(self, value: int, explosion: int = 0, valid: bool = True):
		self.value = value
		self.explosion = explosion
		self.valid = valid

	def invalid(self, is_invalid: bool = True):
		self.valid = not is_invalid

	def __str__(self):
		return str(self.value)

	def __repr__(self):
		s = f"BasicDie({self.value}"
		if self.explosion != 0:
			s += f", {self.explosion}"
		if not self.valid:
			s += f", {self.valid}"
		return s + ")"

	def __int__(self):
		return self.value

	def __eq__(self, other):
		try: other = int(other)
		except: return NotImplemented
		return self.value == other

	def __lt__(self, other):
		try: other = int(other)
		except: return NotImplemented
		return self.value < other

class BasicEntry(RollEntry):
	__slots__ = ["override"]
	_mod_regex = re.compile(r"\s*(xx|x|<=|>=|<|>|=|min|max|num|\+|-)\s*(\d*)\s*", flags=re.I)
	_regex = re.compile(fr"^([+-]?)(\d*)d(?:(\d+)-)?(\d+)((?:{_mod_regex.pattern})*)$", flags=re.I)
	_comparisons = {
		"<=": int.__le__,
		">=": int.__ge__,
		"<" : int.__lt__,
		">" : int.__gt__,
		"=" : int.__eq__
	}

	def __init__(self, arg: str):
		super().__init__(arg)
		self.override = None
		sign = -1 if self._groups[0] == "-" else 1
		pool = int(self._groups[1] or 1)
		minimum = int(self._groups[2] or 1)
		maximum = int(self._groups[3])
		newval = lambda e=0: BasicDie(sign * randint(minimum, maximum), e)

		self.values = []
		for _ in range(pool):
			self.values.append(newval())

		modifiers = dict()
		for key, value in self._mod_regex.findall(self._groups[4]):
			if not value and key in ("<=", ">=", "<", ">", "="):
				raise ModifierError(f"Modifier \"{key}\" requires a value.")

			if value and key in ("num"):
				raise ModifierError(f"Modifier \"{key}\" cannot take a value.")

			modifiers[key] = int(value or 1)

		if "xx" in modifiers:
			valid = list(range(maximum + 1 - modifiers["xx"], maximum + 1))
			nxt = self.values
			iteration = 1
			while len(nxt) and iteration <= 64:
				nxt = [newval(iteration) for n in nxt if n in valid]
				self.values.extend(nxt)
				iteration += 1

		elif "x" in modifiers:
			valid = list(range(maximum + 1 - modifiers["x"], maximum + 1))
			self.values.extend(newval(1) for v in self.values if v in valid)

		for mod in self._comparisons.keys():
			if mod not in modifiers:
				continue

			for v in self.values:
				if not self._comparisons[mod](v, modifiers[mod]):
					v.invalid()

		for mod in ("min", "max"):
			if mod in modifiers:
				sort = sorted(self.values, reverse=(mod == "max"))
				for i in range(modifiers[mod], len(self.values)):
					sort[i].invalid()

		if "num" in modifiers:
			self.override = len(self.values)

		if "+" in modifiers:
			self.values.append(BasicDie(modifiers["+"], -1))
		if "-" in modifiers:
			self.values.append(BasicDie(-modifiers["-"], -1))

if __name__ == '__main__':
	d = BasicEntry("2d6+3")
	print("values:", d.values)
	print("valid:", *(v.value for v in d.values if v.valid))
	print("exp:", sorted(d.values, key=lambda v: v.explosion, reverse=True))