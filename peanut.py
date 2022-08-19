import asyncio
from os import getenv
import random
import discord
from discord.ext import commands
from discord_together import DiscordTogether
from discord_slash import SlashCommand, SlashContext
from discord_slash.utils.manage_commands import create_option
from discord_slash.model import SlashCommandOptionType
import urllib.parse, urllib.request, re
import youtube_dl
from pyunsplash import PyUnsplash
import time
import asyncpraw
import pypexels

bot = commands .Bot(command_prefix='p!')
slash = SlashCommand(bot, sync_commands=True)
bot.remove_command('help') # <---- DO NOT EDIT --->

pu = PyUnsplash(api_key=getenv('UNSPLASH_ACCESS_KEY'))
reddit = asyncpraw.Reddit(client_id = getenv('REDDIT_ID'), client_secret = getenv('REDDIT_SECRET'), user_agent = "pythonpraw")
pexels = pypexels.PyPexels(api_key=getenv('PEXELS_KEY'))

#################################################
        
 ################   VARIABLES   ################

#################################################

time_since_first_request_unsplash = 0
unsplash_request_counter = 50
UNSPLASH_REQ_PER_HOUR = 50
time_since_first_request_pexels = 0
pexels_request_counter = 50
PEXELS_REQ_PER_HOUR = 200

queue = []
yt_url = ''
players = {}
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0',  # bind to ipv4 since ipv6 addresses cause issues sometimes
}
ffmpeg_options = {
    'options': '-vn',
}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

current_song = ''

################################################
        
################ SLASH COMMANDS ################

################################################

@slash.slash(name='greet', description='Greets the user')
async def greet_command(ctx: SlashContext):
    try:
        await ctx.send('Hello')
    except Exception as e:
        print(str(e))
        
@slash.slash(name='join', description='join the voice channel the author is in')
async def join(ctx: SlashContext):
    """Joins a voice channel"""
    try:
        await ensure_voice(ctx)
    except Exception as e:
        print(str(e))

@slash.slash(name='stop', description='Stops and disconnects bot from voice')
async def stop(ctx: SlashContext):
    """Stops and disconnects the bot from voice"""
    try:    
        await ctx.voice_client.disconnect()
    except Exception as e:
        print(str(e))
        
@slash.slash(name='play', 
             description='Plays a video from YouTube', 
             options=[
                 create_option(
                     name='search',
                     description='Video name or url',
                     required=True,
                     option_type=SlashCommandOptionType.STRING)])
async def play_YT(ctx: SlashContext, *, search:str):
    global yt_url
    global queue
    try:
        await ensure_voice(ctx)
        if ctx.author.voice:
            
            if 'https://' in search or 'http://' in search:
               yt_url = search
            else:
                yt_url = await getYtVideo(ctx, search) 
            
            player, info = await ytdl_source(yt_url, loop=bot.loop, stream=True)
            
            time = info['duration']
            hours = int(time / 3600)
            minutes = int(((time % 3600) / 3600) * 60)
            seconds = int((((time % 3600) % 60) / 60) * 60)
            title = info['title']
            channel = info['channel']
            channel_url = info['channel_url']
            
            if len(queue) == 0:
                embed = discord.Embed(title="Playing song:", description=f"**Channel :** [{channel}]({channel_url})\n\n[{title}]({yt_url})\n\n\nduration:  {hours if hours>=10 else ('0'+str(hours))}:{minutes if minutes>=10 else ('0'+str(minutes))}:{seconds if seconds>=10 else ('0'+str(seconds))}", color=discord.Color.blue())
                await ctx.send(embed=embed)
                queue.append(player)
                ctx.voice_client.play(player, after=lambda x=None: play_next(ctx.voice_client))
            else:
                await ctx.send('**Song queued**')
                queue.append(player)
    except Exception as e:
        print(str(e))

@slash.slash(name='skip',
             description='skip currently playing music')
async def skip(ctx: SlashContext):
    # play_next(ctx.voice_client)
    ctx.voice_client.stop()
        
@slash.slash(name='image', 
             description='Get random image using a query', 
             options=[
                 create_option(
                     name='query',
                     description='Search query',
                     required=True,
                     option_type=SlashCommandOptionType.STRING),
                 create_option(name='source',
                               description='source to to get image from (Unsplash/Pexels)',
                               required=False,
                               option_type=SlashCommandOptionType.STRING)
                 ])
async def image_command(ctx: SlashContext, *, query:str, source:str='pexels'):
    try:
        if source.lower() == 'unsplash':
            global time_since_first_request_unsplash, unsplash_request_counter
            if unsplash_request_counter > 0:
                if (time_since_first_request_unsplash == 0) or (int(time.time()) - time_since_first_request_unsplash >= 3600):
                    time_since_first_request = int(time.time())
                    unsplash_request_counter = UNSPLASH_REQ_PER_HOUR
                photos = pu.photos(type_='random', count=1, featured=True, query=query)
                if len(list(photos.entries)) > 0:
                    [photo] = photos.entries
                    attribution = photo.get_attribution(format='txt')
                    link = photo.link_download
                    unsplash_request_counter = unsplash_request_counter - 1
                    embed = discord.Embed(title="Image Picked:", description=f"**Attribution :** \n{attribution}", color=discord.Color.green())
                    embed.set_image(url = link)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send('**No results were found!!**')
            else:
                await ctx.send('Maximum requests reached on Unsplash for this hour, you must wait **{}** minutes before next request'.format((time_since_first_request+3600-int(time.time())/60)))
        elif source.lower() == 'pexels':
            global time_since_first_request_pexels, pexels_request_counter
            if pexels_request_counter > 0:
                if (time_since_first_request_pexels == 0) or (int(time.time()) - time_since_first_request_pexels >= 3600):
                    time_since_first_request_pexels = int(time.time())
                    pexels_request_counter = PEXELS_REQ_PER_HOUR
                else:
                    print('here')
                search_results_list = list(pexels.search(query=query, per_page=40).entries)
                if len(search_results_list) > 0:
                    random_pic = random.choice(search_results_list)
                    attribution = f"Photo by {random_pic.photographer} on Pexels"
                    print(attribution)
                    photographer = (random_pic.photographer).split(' ')
                    print(photographer)
                    link = f'https://images.pexels.com/photos/{random_pic.id}/pexels-photo-{random_pic.id}.jpeg?cs=srgb&dl=pexels-{photographer[0]}-{photographer[1]}-{random_pic.id}.jpg&fm=jpg'
                    # link = random_pic.url
                    embed = discord.Embed(title="Image Picked:", description=f"**Attribution :** \n{attribution}", color=discord.Color.green())
                    embed.set_image(url = link)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send('**No results were found!!**')
            else:
                await ctx.send('Maximum requests reached on Pexels for this hour, you must wait **{}** minutes before next request'.format((time_since_first_request+3600-int(time.time())/60)))
        
    except Exception as e:
        print(str(e))
    
@slash.slash(name="RedditSearch",
             description="Search reddit",
             options=[
                 create_option(
                     name='query',
                     required=True,
                     description='query used for search',
                     option_type=SlashCommandOptionType.STRING),
                 create_option(
                     name="subreddit",
                     required=False,
                     description="Search in a specific subreddit",
                     option_type=SlashCommandOptionType.STRING)
             ])
async def search_reddit(ctx:SlashContext, *, query:str, subreddit:str="all"):
    try:
        output = subreddit
        subreddit_required = await reddit.subreddit(subreddit)
        i=0
        async for post in subreddit_required.search(query):
            output = output + ("\n{}\n{}\n".format(post.title,post.url))
            i = i+1
            if i == 10:
                break
        embed = discord.Embed(title='Reddit search results', description=output, color=discord.Color.orange())
        await ctx.send(embed=embed)
    except Exception as e:
        print(str(e))
        
@slash.slash(name='Thanks',
             description='Thank peanut for his efforts')
async def thanks_command(ctx:SlashContext):
    try:
        author = ctx.author.name
        await ctx.send(content=f'**{author}**, no problem..!!',file=discord.File('mp3/brother.mp3'))
    except Exception as e:
        print(str(e))
        
################################################
        
################ HELPER METHODS ################

################################################
        
async def ytdl_source(url, *, loop=None, stream=False):
    try:
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download = not stream))

        if 'entries' in data:
            data = data['entries'][0]
            
        filename = data['url'] if stream else ytdl.prepare_filename(data)
        pcmAudio = discord.FFmpegPCMAudio(filename, **ffmpeg_options)
        return discord.PCMVolumeTransformer(pcmAudio, volume=0.25), data
    except Exception as e:
        print(str(e))

async def getYtVideo(ctx, search):
    await ctx.send(f':mag: **searching for** `{search}`')
    query_string = urllib.parse.urlencode({'search_query': search})
    htm_content = urllib.request.urlopen('http://www.youtube.com/results?' + query_string)
    search_results = re.findall(r'/watch\?v=(.{11})', htm_content.read().decode())
    url = 'http://www.youtube.com/watch?v=' + search_results[0]
    return url

def play_next(voice):
    try:
        player = queue.pop(0)
        voice.play(player, after=lambda x=None: play_next(voice))
    except:
        pass

async def ensure_voice(ctx: SlashContext):
    if ctx.author.voice:
        voice_channel: discord.VoiceChannel = ctx.author.voice.channel
        if not ctx.voice_client:
            if voice_channel.permissions_for(ctx.guild.me).connect:
                await voice_channel.connect()
            else:
                await ctx.send("*__I don't have access to this channel__*")
        elif voice_channel != ctx.voice_client.channel:
            await ctx.send("*__ I know you like peanuts, but I am in another channel right now! __* ")
            raise commands.CommandError("Author not connected to a voice channel")
    elif ctx.voice_client.is_playing():
            ctx.voice_client.stop()
    else:
        await ctx.send("*__ It's lonely in there, please join a channel first __*")
                
bot.run(getenv('TOKEN'))