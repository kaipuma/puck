from datetime import datetime, timedelta
import asyncio
import shelve
import re

from discord.ext import commands as cmds

class TimerLockError(RuntimeError): pass
class Timer:
	def __init__(self, time: int):
		self._time = time
		self._starttime = None
		self._endtime = None

	@classmethod
	def get(cls, timerid):
		with shelve.open("data/timers.shelf") as shelf:
			return shelf[timerid] if timerid in shelf else None

	@property
	def elapsed(self):
		if self._starttime is None:
			return timedelta()
		return datetime.now() - self._starttime

	@property
	def remaining(self):
		if self._starttime is None:
			return timedelta()
		# return the remaining time if its positive, else 0
		return max((self._endtime - datetime.now()), timedelta())

	@property
	def length(self):
		return self._time

	async def start(self, timerid: str):
		self._starttime = datetime.now()
		self._endtime = self._starttime + timedelta(seconds=self._time)

		with shelve.open("data/timers.shelf") as shelf:
			shelf[timerid] = self

		await asyncio.sleep(self._time)
		return self.get(timerid) and True

	async def stop(self, timerid: str):
		with shelve.open("data/timers.shelf") as shelf:
			shelf[timerid] = None

class TimerConverterError(cmds.CommandError): pass
class TimerConverter(cmds.Converter):
	# a[:b[:c]] OR a[s] WHERE a, b, & c are ints, and s is a size (hour, second, etc.)
	_time_regex = re.compile(r"^(\d+)(?::(\d+)(?::(\d+))?|(s|m|h|d|y))?$")
	_converters = {
		"s": 1,
		"m": 60,
		"h": 3600,
		"d": 86400,
		"y": 31557600
	}
	async def convert(self, ctx, arg: str):
		match = self._time_regex.match(arg)
		if match is None:
			raise TimerConverterError(f"\"{arg}\" doesn't match any known time format")

		first, second, third, size = match.groups()

		seconds = 0
		if third:
			seconds += int(first)  * self._converters["h"]
			seconds += int(second) * self._converters["m"]
			seconds += int(third)  * self._converters["s"]
		elif second:
			seconds	+= int(first)  * self._converters["m"]
			seconds += int(second) * self._converters["s"]
		else:
			seconds += int(first)  * self._converters[size or "m"]

		return Timer(seconds)