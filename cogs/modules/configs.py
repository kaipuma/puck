from pathlib import Path
import json
import os

_paths = {
	"dice": Path("./configs/dice.json"),
	"emoji": Path("./configs/emoji.json"),
	"colors": Path("./configs/colors.json")
}

class _Reader:
	def __init__(self, path):
		self._path = path
		self._mtime = 0
		self._data = None

	def _refresh(self):
		mtime = os.path.getmtime(self._path)
		if mtime > self._mtime:
			self._mtime = mtime
			with open(self._path, "r") as file:
				self._data = json.load(file)

	def __getitem__(self, item):
		self._refresh()
		return self._data[item]
		
	def __getattr__(self, attr):
		self._refresh()
		return getattr(self._data, attr)


dice_config = _Reader(_paths["dice"])
emoji_config = _Reader(_paths["emoji"])
color_config = _Reader(_paths["colors"])
