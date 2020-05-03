import json
from typing import Optional
from random import shuffle
import re

from discord.ext import commands as cmds
from discord import Embed, Color

from .modules.misc import TimerConverter, Timer
from .modules.configs import color_config as colcon

class Other(cmds.Cog):
	@cmds.group(aliases=["time"], brief="start a timer", invoke_without_command=True)
	async def timer(self, ctx, timer: TimerConverter, *, tag: Optional[str] = ""):
		# get the unique timer id from the channel id + tag, and set it
		tid = f"{ctx.channel.id}: {tag}"

		# raise an error if there's already such a timer running
		existing = Timer.get(tid)
		if existing and existing.remaining:
			await ctx.send("There's already a timer running in this channel with that tag")
			return
		
		# compose message
		tstr = f" \"{tag}\"" if tag else ""
		startmsg = f"{ctx.author.mention}, your timer{tstr} has started.\nUse the 'timer status{tstr}' command to view its status"
		endmsg = f"{ctx.author.mention}, your timer{tstr} has ended!"

		# send msg, wait for timer to run, then send complete message
		await ctx.send(startmsg)
		status = await timer.start(tid)
		if status:
			await ctx.send(endmsg)

	@timer.command(name="status", aliases=["show"], brief="show timer status")
	async def timer_status(self, ctx, *, tag: Optional[str] = ""):
		# get the unique timer id from the channel id + tag
		tid = f"{ctx.channel.id}: {tag}"

		# raise an error if there's no such timer running
		existing = Timer.get(tid)
		if not (existing and existing.remaining):
			await ctx.send("There's no timer running in this channel with that tag")
			return

		await ctx.send(f"That timer has {existing.remaining} remaining")

	@timer.command(name="stop", aliases=["end", "kill"], brief="stop the running of a timer")
	async def timer_stop(self, ctx, *, tag: Optional[str] = ""):
		# get the unique timer id from the channel id + tag
		tid = f"{ctx.channel.id}: {tag}"

		# raise an error if there's no such timer running
		existing = Timer.get(tid)
		if not existing or not existing.remaining:
			await ctx.send("There's no timer running in this channel with that tag")
			return

		# stop the timer and say as such
		await existing.stop(tid)
		tstr = f" \"{tag}\"" if tag else ""
		await ctx.send(f"Timer{tstr} stopped with {existing.remaining} remaining")

	@cmds.command(aliases=["shuff", "shuf", "sh"], brief="shuffle a list")
	async def shuffle(self, ctx, *choices: str):
		"""
		Given a list, output that list shuffled.
		Allows options to be given in the form "thisXnum", which will add "num" instances of "this" to the pool.
		For example, "Crash Paragon Nautica villainX3" would output a list six items long.
		Of note:
		- "X" isn't case sensitive
		- The number must be positive
		- Multi-word names can be accomplished by surrounding the whole choice in quotes (e.g. "Death Bladex4" would put four "Death Blade"s on the list). This includes the "Xnum" part.
		"""
		final = []
		for c in choices:
			# split all in the form thingXnum 
			base, mult = re.match(r"(.*?)(?:x(\d+))?$", c, flags=re.I).groups()
			# int(mult), or 1 if mult is None
			mult = int(mult or 1)
			for _ in range(mult):
				final.append(base)

		shuffle(final)
		ebd = Embed(
			color = Color.from_rgb(*colcon["shuffle"]),
			title = "Your shuffled list is:",
			description = "\n".join(final)
		)

		await ctx.send(embed=ebd)
