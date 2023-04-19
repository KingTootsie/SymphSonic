import discord
from discord.ext import commands
from discord.commands import SlashCommandGroup
import mafic
import sqlite3
from datetime import datetime as dt
import json
import asyncio

class Music(commands.Cog):
    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    member_count = {}
    skip_members = {}
       
    @commands.slash_command()
    async def play(self, ctx: discord.ApplicationContext, query: str):
        voice_client: mafic.Player = ctx.guild.voice_client

        if voice_client is None:
            vc = ctx.author.voice.channel
            if vc is None:
                return ctx.respond(embed=discord.Embed(title="You must be in a VC to play music."))
            else:
                await vc.connect(cls=mafic.Player)
                Music.skip_members.update({f"{ctx.guild.id}": []})
                Music.member_count.update({f"{ctx.guild.id}": []})
                Queue.queues.update({f"{ctx.guild.id}": []})

        voice_client: mafic.Player = ctx.guild.voice_client

        tracks = await voice_client.fetch_tracks(query=query, search_type = "ytsearch")

        if len(tracks) == 0:
            return await ctx.respond("No track found.")
        
        track = tracks[0]

        track_time = ""
        if track.stream:
            track_time = "LIVE"
        else:
            track_time = Utilities.get_formatted_time(track.length)

        embed = discord.Embed()

        queue = Queue.queues.get(f"{ctx.guild.id}")

        if Queue.is_empty(guild_id=ctx.guild.id):
            queue.append(track)

            await voice_client.play(track)

            embed.title = f"Now playing: \"{track.title}\" ({track_time})"

            await ctx.respond(embed = embed)
        else:
            queue.append(track)

            embed.title = f"Added \"{track.title}\" ({track_time}) to queue."

            await ctx.respond(embed=embed)

    @commands.slash_command()
    async def search(self, ctx: discord.ApplicationContext, query: str):
        await ctx.response.defer(ephemeral=False)
        
        try:
            node = self.bot.node_pool.get_node(guild_id=ctx.guild.id, endpoint=None)

            results = await node.fetch_tracks(query=query, search_type = "ytsearch")

            results = results[0:5]
        except Exception as e:
            print(e)
            return await ctx.respond(embed=discord.Embed(title=f"An error occured when searching for \"{query}\"."))
        if len(results) == 0:
            return await ctx.respond(embed=discord.Embed(title=f"There are no search results for \"{query}\"."))

        view = Music.searchView(original_self=self, results=results)

        #view labels
        for position, item in enumerate(results):
            name = item.title

            if len(name) > 90:
                truncated_name = name[0:89]
                name = f"{truncated_name}..."

            view.children[0].add_option(label=f"#{position + 1} - {name}")

        #embed
        text = ""
        for num, result in enumerate(results):
            title = result.title
            time = Utilities.get_formatted_time(result.length)
            text += f"#{num + 1} - {title} ({time})\n"
        embed = discord.Embed(title=f"Search results for \"{query}\":", description=f"{text}")

        message = await ctx.respond(embed=embed, view=view)
        view.message = message
    
    class searchView(discord.ui.View):
        def __init__(self, original_self, results):
            super().__init__(timeout=30)
            self.results = results
            self.original_self = original_self

        async def on_timeout(self):
            for child in self.children:
                child.disabled = True
            await self.message.edit(view=self)
        
        @discord.ui.select()
        async def select_callback(self, select, interaction):
            select.disabled = True
            await self.message.edit(view=self)

            await interaction.response.defer(ephemeral=True)

            position = ""
            for i in select.values[0][1:]:
                print(i)
                if i == "-" or i == " ":
                    break
                else:
                    position += i
                
            position = int(position) - 1

            track: mafic.Track = self.results[position]
            title = track.title
            #print(f"{position} - {title}")

            voice_client = interaction.guild.voice_client

            if voice_client is None:
                if interaction.user.voice:
                    await interaction.user.voice.channel.connect(cls=mafic.Player)
                    Music.skip_members.update({f"{interaction.guild.id}": []})
                    Music.member_count.update({f"{interaction.guild.id}": []})
                    Queue.queues.update({f"{interaction.guild.id}": []})
                else:
                    return await interaction.followup.send(embed=discord.Embed(title=f"You are not connected to a voice channel."))
                    #raise commands.CommandError("Author not connected to a voice channel.")

            voice_client = interaction.guild.voice_client
            try:
                tracks = await voice_client.fetch_tracks(query=track.uri, search_type = "ytsearch")
                track = tracks[0]

            except Exception as e:
                print(f"Something went wrong. {e}")
                return await interaction.followup.send(embed=discord.Embed(title=f"An error occurred. Please let King Tootsie know about this error message."))

            time = ""
            if track.stream == True:
                time = "(LIVE)"
            else:
                time = f"({Utilities.get_formatted_time(track.length)})"
            
            queue = Queue.queues.get(f"{interaction.guild.id}")
            
            if Queue.is_empty(guild_id=interaction.guild.id) == True:
                current_time = dt.now()
                print(f"({current_time}) Now playing \"{track.title}\".")

                await voice_client.play(track)
                queue.append(track)

                return await interaction.followup.send(embed=discord.Embed(title=f"Now playing: \"{track.title}\" " + time))
            else:
                current_time = dt.now()
                print(f"({current_time}) Added \"{track.title}\" to queue.")

                queue.append(track)

                return await interaction.followup.send(embed=discord.Embed(title=f"Added \"{track.title}\" to queue. " + time))
            
    @commands.slash_command()
    async def force_skip(self, ctx: discord.ApplicationContext):
        if ctx.author.guild_permissions.mute_members == False:
            return await ctx.respond(embed=discord.Embed(title=f"You must have the `mute_members` permission to forcefully skip songs."))

        if ctx.voice_client is None:
            return await ctx.respond(embed=discord.Embed(title=f"Not connected to voice channel."))
        elif ctx.author.voice is None:
            return await ctx.respond(embed=discord.Embed(title=f"You are not connected to a voice channel."))

        if ctx.voice_client.channel != ctx.author.voice.channel:
            return await ctx.respond(embed=discord.Embed(title=f"You must be in the same VC to skip."))

        is_queue_empty = Queue.is_empty()
        if is_queue_empty:
            return await ctx.respond(embed=discord.Embed(title=f"There's nothing to skip."))

        if not is_queue_empty:
            old_track = ctx.voice_client.current
            await ctx.voice_client.stop()
            new_track = ctx.voice_client.current
            if old_track == new_track:
                await ctx.voice_client.dispatch_event(payload=mafic.TrackEndEvent(track=old_track, player=ctx.voice_client))

        return await ctx.respond(embed=discord.Embed(title=f"Forcefully skipped song."))
        
    @commands.slash_command()
    async def skip(self, ctx: discord.ApplicationContext):
        current_time = dt.now()
        print(f"({current_time}) {ctx.author} issued skip command.")
    
        if ctx.voice_client is None:
            return await ctx.respond(embed=discord.Embed(title=f"Not connected to voice channel."))
        elif ctx.author.voice is None:
            return await ctx.respond(embed=discord.Embed(title=f"You are not connected to a voice channel."))
        
        if ctx.voice_client.current == None:
            return await ctx.respond(embed=discord.Embed(title=f"Nothing is playing currently."))

        if ctx.voice_client.channel != ctx.author.voice.channel:
            return await ctx.respond(embed=discord.Embed(title=f"You must be in the same VC to skip."))

        skip_members = Music.skip_members[f"{ctx.guild.id}"]
        member_count = Music.member_count[f"{ctx.guild.id}"]

        member_count.clear()
        for member in ctx.voice_client.channel.members:
            if member.bot == False:
                member_count.append(member.id)

        #checks if any users that voted to skip are still in the VC next time someone tries to skip.
        if len(skip_members) > 0:
            remove_members = []

            for member_id in skip_members:
                if member_id not in member_count:
                    remove_members.append(member_id)
        
            for member in remove_members:
                skip_members.remove(member)

        if ctx.author.id not in skip_members:
            skip_members.append(ctx.author.id)
            await ctx.respond(embed=discord.Embed(title=f"{ctx.author} voted to skip. ({len(skip_members)}/{len(member_count)})"))
        else:
            return await ctx.respond(embed=discord.Embed(title=f"You've already skipped."))
            
        if (len(skip_members) >= len(member_count)):
            await ctx.send(embed=discord.Embed(title=f"Skipping..."))
            if not Queue.is_empty():
                old_track = ctx.voice_client.current
                await ctx.voice_client.stop()
                new_track = ctx.voice_client.current
                if old_track == new_track:
                    await ctx.voice_client.dispatch_event(payload=mafic.TrackEndEvent(track=old_track, player=ctx.voice_client))
            skip_members.clear()

    @commands.slash_command()
    async def join(self, ctx: discord.ApplicationContext, *, channel: discord.VoiceChannel = None):
        """Joins a voice channel"""
        if channel is None:
            try:
                channel = ctx.author.voice.channel

            except AttributeError:
                return await ctx.respond(embed=discord.Embed(title=f"You didn't provide a channel nor are you connected to one."))
            
            except:
                return await ctx.respond(embed=discord.Embed(title=f"An error occured."))

        if channel.permissions_for(channel.guild.me).connect == False:
            return await ctx.respond(embed=discord.Embed(title=f"I do not have permission to connect to {channel}."))

        if ctx.voice_client is not None:
            if ctx.voice_client.channel == channel:
                return await ctx.respond(embed=discord.Embed(title=f"I am already connected to {channel}."))
            else:
                await ctx.voice_client.disconnect()
                await ctx.author.voice.channel.connect(cls=mafic.Player)
                return await ctx.respond(embed=discord.Embed(title=f"Moved to {channel}."))
        else:
            await channel.connect(cls=mafic.Player)
            Music.skip_members.update({f"{ctx.guild.id}": []})
            Music.member_count.update({f"{ctx.guild.id}": []})
            Queue.queues.update({f"{ctx.guild.id}": []})
            await ctx.respond(embed=discord.Embed(title=f"Connected to {channel}.")) 
    
    @commands.slash_command(description="Team Xension - Disconnects the bot and clears the queue.")
    async def stop(self, ctx: discord.ApplicationContext):
        voice_client: mafic.Player = ctx.guild.voice_client

        embed = discord.Embed()
        if voice_client is None:
            embed.title = f"Bot is not connected to a voice channel."
            return await ctx.respond(embed = embed)
        
        await voice_client.destroy()
        Queue.song_list.clear()
        del Music.skip_members[f"{ctx.guild.id}"]
        del Music.member_count[f"{ctx.guild.id}"]

        embed.title = f"Disconnected from the vc and cleared the queue."
        await ctx.respond(embed=embed)

    @commands.slash_command()
    async def add_filter(self, ctx: discord.ApplicationContext, selected_filter: discord.Option(
            name = "filter",
            required = True,
            choices = [
                #discord.OptionChoice(name="Test", value="test"),
                discord.OptionChoice(name="Karaoke", value="karaoke"),
                discord.OptionChoice(name="Low Pass", value="low_pass"),
                discord.OptionChoice(name="Tremolo", value="tremolo"),
                discord.OptionChoice(name="Vibrato", value="vibrato"),
            ]
    )):
        #All booleans set to True should actually be mafic objects of their respective types.
        filter: mafic.Filter = None
        if selected_filter == "karaoke":
            filter = mafic.Filter(karaoke=mafic.Karaoke(1))
        elif selected_filter == "low_pass":
            filter = mafic.Filter(low_pass=mafic.LowPass(1))
        elif selected_filter == "tremolo":
            filter = mafic.Filter(tremolo=mafic.Tremolo(1))
        elif selected_filter == "vibrato":
            filter = mafic.Filter(vibrato=mafic.Vibrato(1))
        
        await ctx.guild.voice_client.add_filter(filter, label="appliedfilter")

        await ctx.respond(selected_filter)

    #Might remove. Obsolete code 
    #@play.before_invoke
    async def check_vc(self, ctx: discord.ApplicationContext):
        vc = ctx.author.voice.channel
        vclient = ctx.voice_client

        if vclient is not None:
            return

        if vc is None:
            ctx.respond("You are not connected to a voice channel.")
        else:
            await vc.connect(cls=mafic.Player)

    """@commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.bot:
            return
        
        if before.channel is None:
            return

        voice_client: mafic.Player = member.guild.voice_client
        if voice_client is None:
            return

        all_vc_members = before.channel.members

        vc_members = []

        for member in all_vc_members:
            if member.bot is False:
                vc_members.append(member)
        
        if len(vc_members) == 0:
            sqlconnection = sqlite3.connect("./data/guilds.db")
            cursor = sqlconnection.cursor()
            
            result = cursor.execute(f'SELECT * FROM guilds WHERE guild_id={member.guild.id}').fetchone()

            channel = self.bot.get_channel(result[2])

            await voice_client.destroy()
            del Music.skip_members[f"{member.guild.id}"]
            del Music.member_count[f"{member.guild.id}"]
            del Queue.queues[f"{member.guild.id}"]

            embed = discord.Embed()
            embed.title = "Disconnected from the VC because everyone left."
            await channel.send(embed=embed)
"""
    @commands.Cog.listener()
    async def on_track_end(self, event: mafic.TrackEndEvent):
        queue = Queue.queues.get(f"{event.player.guild.id}")
        queue.pop(0)

        sqlconnection = sqlite3.connect("./data/guilds.db")
        cursor = sqlconnection.cursor()
        
        result = cursor.execute(f'SELECT * FROM guilds WHERE guild_id={event.player.guild.id}').fetchone()

        channel = self.bot.get_channel(result[2])

        embed = discord.Embed()

        #Must fix.
        if Queue.doQueueClear:
            print("Queue clear initalized.")
            
            queue.clear()

            #This must be removed.
            Queue.doQueueClear = False

            return
        
        if Queue.is_empty():
            print("Queue is empty.")
        else:
            track = queue[0]

            track_time = ""
            if track.stream:
                track_time = "LIVE"
            else:
                track_time = Utilities.get_formatted_time(track.length)
            await event.player.play(track)

            embed.title = f"Now playing: \"{track.title}\" ({track_time})"

            await channel.send(embed = embed) 

class Queue(commands.Cog):
    def __init__(self, bot) -> None:
        super().__init__()
        self.bot = bot

    queues = {}
    doQueueClear = False

    def is_empty(guild_id: str):
        queue = Queue.queues.get(f"{guild_id}")
        if len(queue) == 0:
            return True
        else:
            return False

    queuecommand = SlashCommandGroup("queue", "A bunch of queue commands.")

    """Queuecommand sub command. When called by a user, it retrieves the current songs in the queue."""
    @queuecommand.command(description="Shows the current queue.")
    async def list(self, ctx: discord.ApplicationContext):
        queue = Queue.queues.get(f"{ctx.guild.id}")
        if len(queue) == 0:
            return await ctx.respond(embed=discord.Embed(title=f"There is currently nothing in the queue."))
        else:
            first_song = queue[0]
            time = ""
            if first_song.stream == True:
                time = "(LIVE)"
            else:
                time = f"{Utilities.get_formatted_time(first_song.length)}"
            msg_embed = discord.Embed(title=f"Now playing: \"{first_song.title}\" ({time})")
            next = ""
            if len(queue) == 1:
                next = "Nothing."
            else:
                for position, item in enumerate(queue[1:]):
                    time = ""
                    if item.stream == True:
                        time = "(LIVE)"
                    else:
                        time = f"{Utilities.get_formatted_time(item.length)}"

                    next += f"#{position+1} - \"{item.title}\" ({time}) \n"

            
            msg_embed.add_field(name="Up next:", value=next)
            view = Queue.queueViews.main.mainView(timeout=60)
            await ctx.respond(embed=msg_embed, view=view)

    @queuecommand.command()
    async def remove(self, ctx: discord.ApplicationContext, position: int):
        queue = Queue.queues.get(f"{ctx.guild.id}")
        if len(queue) == 0:
            return await ctx.respond(embed=discord.Embed(title=f"Nothing is in the queue currently."))

        if (position > len(queue)) or (position < 0):
            return await ctx.respond(embed=discord.Embed(title=f"Error: Number provided is out of queue range."))

        else:
            try:
                tempname = queue[position].title
                tempytobject = queue[position]
                if position == 0:
                    await ctx.voice_client.stop()
                else:
                    queue.pop(position)
                return await ctx.respond(embed=discord.Embed(title=f"Removed \"{tempname}\" from the queue."), view=Queue.queueViews.removalView(element=tempytobject, position=position, authorid=ctx.author.id))
            except:
                await ctx.respond(embed=discord.Embed(title=f"An error occurred. Please let King Tootsie know if you see this."))
    
    @queuecommand.command()
    async def clear(self, ctx: discord.ApplicationContext):
        queue = Queue.queues.get(f"{ctx.guild.id}")
        if len(queue) == 0:
            return await ctx.respond(embed=discord.Embed(title=f"Nothing is in the queue currently."))

        Queue.doQueueClear = True
        old_track = ctx.voice_client.current
        await ctx.voice_client.stop()
        new_track = ctx.voice_client.current
        if old_track == new_track:
            await ctx.voice_client.dispatch_event(payload=mafic.TrackEndEvent(track=old_track, player=ctx.voice_client))
        return await ctx.respond(embed=discord.Embed(title=f"Cleared the queue."))
    
    class queueViews:
        class main:
            class mainView(discord.ui.View):
                def __init__(self, timeout: float | None = 180, disable_on_timeout: bool = True):
                    super().__init__(timeout=timeout)
                
                async def on_timeout(self):
                    for child in self.children:
                        child.disabled = True
                    await self.message.edit(view=self)

                @discord.ui.button(label="Remove item", style = discord.ButtonStyle.red)
                async def remove_callback(self, button, interaction):
                    queue = Queue.queues.get(f"{interaction.guild.id}")

                    button.disabled = True
                    await self.message.edit(view=self)

                    await interaction.response.defer(ephemeral=False, invisible=True)

                    view = Queue.queueViews.main.removalSelectView()

                    for position, item in enumerate(queue):
                        name = item.title
                        view.children[0].add_option(label=f"#{position + 1} - {name}")

                    message = await interaction.followup.send(view=view, ephemeral=True)

                    view.message = message

            class removalSelectView(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=30,disable_on_timeout=True)

                async def on_timeout(self):
                    for child in self.children:
                        child.disabled = True
                    await self.message.edit(view=self)

                @discord.ui.select(placeholder = "Select a song to remove.", min_values=1, max_values=1, options=None)
                async def select_callback(self, select, interaction):
                    queue = Queue.queues.get(f"{interaction.guild.id}")
                    select.disabled = True
                    await self.message.edit(view=self)

                    await interaction.response.defer(ephemeral=False, invisible=True)

                    position = ""
                    for i in select.values[0][1:]:
                        print(i)
                        if i == "-" or i == " ":
                            break
                        else:
                            position += i
                        
                    position = int(position) - 1

                    try:
                        tempname = queue[position].title
                        temp_track_object = queue[position]

                        first_elem = False
                        if position == 0:
                            await interaction.guild.voice_client.stop()
                            first_elem = True
                        else:
                            queue.pop(position)

                        
                        view = Queue.queueViews.main.removalSelectView.undoButton(element=temp_track_object, position=position, authorid=interaction.user.id)
                        message = await interaction.followup.send(embed=discord.Embed(title=f"Removed \"{tempname}\" from the queue."), view=discord.MISSING if first_elem is True else view)
                        if first_elem == False:
                            view.message = message

                    except:
                        await interaction.followup.send(embed=discord.Embed(title=f"An error occurred. Please let King Tootsie know if you see this."))
                        
                class undoButton(discord.ui.View):
                    def __init__(self, element, position: int, authorid: int):
                        super().__init__(timeout=30)
                        self.element = element
                        self.position = position
                        self.authorid = authorid
                    
                    async def on_timeout(self):
                        for child in self.children:
                            child.disabled = True
                            child.style = discord.ButtonStyle.grey
                        await self.message.edit(view=self)
                    
                    @discord.ui.button(label="Undo", style=discord.ButtonStyle.red)
                    async def button_callback(self, button, interaction):
                        queue = Queue.queues.get(f"{interaction.guild.id}")
                        if self.authorid != interaction.user.id:
                            return await interaction.response.send_message(embed=discord.Embed(title=f"You don't have permission to undo this action."), ephemeral=True)

                        await interaction.response.defer(ephemeral=False, invisible=True)

                        button.disabled = True
                        button.style = discord.ButtonStyle.grey

                        embeds = self.message.embeds
                        embed = discord.Embed(title=f"~~{embeds[0].title}~~")
                        
                        await self.message.edit(embed=embed, view=self)

                        try:
                            queue.insert(self.position, self.element)
                            return await interaction.followup.send(embed=discord.Embed(title=f"Removal undone."))
                        except:
                            await interaction.followup.send(embed=discord.Embed(title=f"An error occurred. Please let King Tootsie#3881 know if you see this."))

        class removalView(discord.ui.View):
            def __init__(self, element, position: int, authorid: int):
                super().__init__(timeout=30)
                self.element = element
                self.position = position
                self.authorid = authorid
            
            async def on_timeout(self):
                for child in self.children:
                    child.disabled = True
                    child.style = discord.ButtonStyle.grey
                await self.message.edit(view=self)
            
            @discord.ui.button(label="Undo", style=discord.ButtonStyle.red)
            async def button_callback(self, button, interaction):
                queue = Queue.queues.get(f"{interaction.guild.id}")
                if self.authorid != interaction.user.id:
                    return await interaction.response.send_message(embed=discord.Embed(title=f"You don't have permission to undo this action."), ephemeral=True)

                await interaction.response.defer(ephemeral=False, invisible=True)

                button.disabled = True
                button.style = discord.ButtonStyle.grey

                embeds = self.message.embeds
                embed = discord.Embed(title=f"~~{embeds[0].title}~~")
                
                await self.message.edit(embed=embed, view=self)

                try:
                    queue.insert(self.position, self.element)
                    return await interaction.followup.send(embed=discord.Embed(title=f"Removal undone."))
                except:
                    await interaction.followup.send(embed=discord.Embed(title=f"An error occurred. Please let King Tootsie#3881 know if you see this."))
                
class Utilities:
    def get_formatted_time(total_miliseconds: str) -> str:
        total_seconds = total_miliseconds / 1000
        int_hours, after_hours_remainder = divmod(total_seconds, 3600)
        int_minutes, int_seconds = divmod(after_hours_remainder, 60)

        int_hours = int(int_hours)
        int_minutes = int(int_minutes)
        int_seconds = int(int_seconds)

        str_hours = ""
        str_minutes = ""
        str_seconds = ""

        str_hours = str(int_hours)

        if len(str(int_minutes)) == 2:
            str_minutes = f"{int_minutes}"
        else:
            str_minutes = f"0{int_minutes}"

        if len(str(int_seconds)) == 2:
            str_seconds = f"{int_seconds}"
        else:
            str_seconds = f"0{int_seconds}"

        if int_hours > 0:
            time = f"{str_hours}:{str_minutes}:{str_seconds}"
        elif int_minutes > 0:
            if str_minutes[0] == "0":
                time = f"{str_minutes[1]}:{str_seconds}"
            else:
                time = f"{str_minutes}:{str_seconds}"
        elif int_seconds > 0:
            if str_minutes[0] == "0":
                time = f"{str_seconds[1]}"
            else:
                time = f"{str_seconds}"

        return time
    
def setup(bot):
    bot.add_cog(Music(bot))
    bot.add_cog(Queue(bot))