import json
from typing import Optional
import re

from discord.ext import commands as cmds

from .modules.misc import TimerConverter, Timer

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
		startmsg = f"Timer{tstr} started. Use the 'timer status{tstr}' command to view its status"
		endmsg = f"Timer{tstr} ended!"

		# send msg, wait for timer to run, then send complete message
		await ctx.send(startmsg)
		status = await timer.start(tid, ctx.bot.locks["timers"])
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
		await existing.stop(tid, ctx.bot.locks["timers"])
		tstr = f" \"{tag}\"" if tag else ""
		await ctx.send(f"Timer{tstr} stopped with {existing.remaining} remaining")
