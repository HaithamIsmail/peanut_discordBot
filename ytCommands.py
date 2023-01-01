import urllib.parse, urllib.request, re 
import youtube_dl
import asyncio
import discord
from discord_slash import SlashCommand, SlashContext
from discord.ext import commands

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
    else:
        await ctx.send("*__ It's lonely in there, please join a channel first __*")