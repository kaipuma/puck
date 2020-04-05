import re
import json

class DiceConfig:
	with open("./configs/dice.json", "r") as file:
		_raw = json.load(file)

	@classmethod
	def get_faces(cls, category: str, die: str):
		category, die = category.lower(), die.lower()
		if category not in cls._raw:
			return None
		elif die not in cls._raw[category]["faces"]:
			for name, aliases in cls._raw[category]["aliases"].items():
				if die in aliases:
					die = name
					break
			else:
				return False
		else:
			return False

		return cls._raw[category]["faces"][die][:]

	@classmethod
	def get_all_names(cls, category: str):
		category = category.lower()
		if category not in cls._raw:
			return None

		all_names = []
		for name, aliases in cls._raw[category]["aliases"].items():
			all_names.append(name)
			all_names.extend(aliases)

		return all_names

	@classmethod
	def get_default(cls, category: str):
		pass

	@classmethod
	def get_empty(cls, category: str):
		pass

	@classmethod
	def cancels_with(cls, category: str, face: str):
		pass

class RollEntry:
	"""
	A single argument in a dice roll command.

	Attributes:
		category: Each category can be added only to others of that category
		total: a str representation of the final, summed result
		results: a list of all the individual results
		invoke: a str that represents this entry
	"""
	category = "default"
	total = "default"
	results = []
	invoke = "default"

	@classmethod
	def from_results(cls, results):
		ret = cls()
		ret.results = results
		return ret

	def __add__(self, other):
		if not isinstance(other, RollEntry):
			return NotImplemented

		if not self.sort == other.sort:
			return NotImplemented

		return self.from_results(self.results + other.results)

	def __str__(self):
		return f"{self.invoke}: {', '.join(map(str, self.results))}"

class DiceEntry(RollEntry):
	categories = ["basic", "spectaculars", "starwars", "fate"]
	mod_regex = re.compile(r"(xx|x|<|>|=|min|max)(\d*)", flags=re.I)
	regexes = {
		"basic":		re.compile(fr"^(\d+)(?:{mod_regex.pattern})*$", flags=re.I),
		"spectaculars":	re.compile(r"^(a(?:dv(?:antage)?)?|c(?:hal(?:lenge)?)?)$", flags=re.I),
		"starwars":		re.compile(r"^(y(?:ellow)|g(?:reen)|b(?:lue)|r(?:ed)|p(?:urple)|(?:b)(?:lac)k|w(?:hite))$", flags=re.I),
		"fate":			re.compile(r"^()$")
	}

	@classmethod
	def from_results(cls, results):
		pass

	@property
	def total(self):
		pass
	
	def __init__(self, category: str, num: int, dice: str):
		if category not in self.categories:
			raise TypeError(
				f"Invalid category of dice \"{category}\".\n"
				f"See {self.__class__.__name__}.categories"
			)

		pass

class ModifierEntry(RollEntry):
	category = "numeric"

	@classmethod
	def from_results(cls, results):
		return cls(sum(results))

	def __init__(self, num: int):
		if num > 0:
			self._sign = "+"
		elif num < 0:
			self._sign = "-"
		elif num == 0:
			self._sign = "±"

		self.total = self._sign + str(abs(num))
		self.invoke = f"{self.total}: {self.total}"
		self.results = [num]

if __name__ == '__main__':
	pass