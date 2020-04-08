from pathlib import Path
import json
import os

_paths = {
	"dice": Path("./configs/dice.json"),
	"emoji": Path("./configs/emoji.json")
}

class _Reader:
	def __init__(self, path):
		self._path = path
		self._mtime = 0
		self._data = None

	def __getitem__(self, item):
		mtime = os.path.getmtime(self._path)
		if mtime > self._mtime:
			self._mtime = mtime
			with open(self._path, "r") as file:
				self._data = json.load(file)

		return self._data[item]

dice_config = _Reader(_paths["dice"])
emoji_config = _Reader(_paths["emoji"])
