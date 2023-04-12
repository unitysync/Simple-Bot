import os
import discord
from discord_slash import SlashCommand, SlashContext
from discord.ext import commands
from dotenv import load_dotenv
import asyncio
import random
import string

# Load the bot's configuration from .env file
load_dotenv()
config = {
  "token": os.getenv("DISCORD_TOKEN"),
  "leveling_enabled": os.getenv("LEVELING_ENABLED").lower() == "true",
  "leveling_channel": os.getenv("LEVELING_CHANNEL"),
  "leveling_rate": float(os.getenv("LEVELING_RATE")),
}

# Set up the Discord client and command handler
client = commands.Bot(command_prefix="!")
slash = SlashCommand(client, sync_commands=True)

# Set up the leveling system
leveling_data = {}
if config["leveling_enabled"]:
  # Load leveling data from file
  if os.path.exists("leveling_data.txt"):
    with open("leveling_data.txt", "r") as f:
      leveling_data = eval(f.read())

  # Save leveling data to file periodically
  async def save_leveling_data():
    await client.wait_until_ready()
    while not client.is_closed():
      with open("leveling_data.txt", "w") as f:
        f.write(str(leveling_data))
      await asyncio.sleep(600)
  client.loop.create_task(save_leveling_data())

# Define the slash command to create a giveaway
@slash.slash(name="create-giveaway",
             description="Create a giveaway",
             options=[
               {
                 "name": "prize",
                 "description": "The prize for the giveaway",
                 "type": 3,
                 "required": True
               },
               {
                 "name": "num_winners",
                 "description": "The number of winners for the giveaway",
                 "type": 4,
                 "required": True
               },
               {
                 "name": "duration",
                 "description": "The duration of the giveaway (in minutes)",
                 "type": 4,
                 "required": True
               }
             ])
async def create_giveaway(ctx: SlashContext, prize: str, num_winners: int, duration: int):
  # Set up the giveaway message
  message = f"🎉 **GIVEAWAY** 🎉\n\nReact with :tada: to enter!\n\nPrize: {prize}\n\nNumber of winners: {num_winners}\n\nDuration: {duration} minutes"

  # Send the giveaway message and add the reaction
  giveaway_message = await ctx.send(message)
  await giveaway_message.add_reaction("🎉")

  # Wait for the duration of the giveaway
  await asyncio.sleep(duration * 60)

  # Get the list of users who entered the giveaway
  reaction = await giveaway_message.fetch_reaction("🎉")
  users = await reaction.users().flatten()
  users.pop(users.index(client.user))

  # Select the winners and send them a message
  winners = random.sample(users, num_winners)
  for winner in winners:
    await winner.send(f"Congratulations! You won the {prize} giveaway! 🎉")

  # Announce the winners in the channel
  winners_mention = " ".join([winner.mention for winner in winners])
  await ctx.send(f"Congratulations {winners_mention}! You have won the {prize} giveaway!")

@slash.slash(name="ban",
             description="Ban a user",
             options=[
               {
                 "name": "user",
                 "description": "The user to ban",
                 "type": 6,
                 "required": True
               },
               {
                 "name": "reason",
                 "description": "The reason for the ban",
                 "type": 3,
                 "required": False
               }
             ])
@commands.has_permissions(ban_members=True)
async def ban(ctx: SlashContext, user: discord.User, reason: str = "No reason provided"):
  await moderate(ctx.guild, ctx.author, user, "ban", reason)
  await ctx.send(f"{user.name}#{user.discriminator} has been banned from the server. Reason: {reason}")


# Define the slash command to unban a user
@slash.slash(name="unban",
             description="Unban a user",
             options=[
               {
                 "name": "user",
                 "description": "The user to unban",
                 "type": 6,
                 "required": True
               }
             ])
@commands.has_permissions(ban_members=True)
async def unban(ctx: SlashContext, user: discord.User):
  try:
    await ctx.guild.unban(user)
    await ctx.send(f"{user.mention} has been unbanned!")
  except:
    await ctx.send(f"Failed to unban {user.mention}. Please check that the user is currently banned.")

@slash.slash(name="level",
             description="View your level and experience points")
async def view_level(ctx: SlashContext):
  if config["leveling_enabled"]:
    user_id = str(ctx.author.id)
    if user_id in leveling_data:
      level, exp = leveling_data[user_id]
      await ctx.send(f"{ctx.author.mention}, you are at level {level} with {exp} experience points.")
    else:
      await ctx.send(f"{ctx.author.mention}, you haven't earned any experience points yet.")
  else:
    await ctx.send("The leveling system is currently disabled.")

@slash.slash(name="leaderboard",
             description="View the server's leaderboard")
async def view_leaderboard(ctx: SlashContext):
  if config["leveling_enabled"]:
    sorted_data = sorted(leveling_data.items(), key=lambda x: x[1][0], reverse=True)
    leaderboard = []
    for i, (user_id, (level, exp)) in enumerate(sorted_data):
      try:
        user = await client.fetch_user(int(user_id))
        leaderboard.append(f"{i+1}. {user.name} - Level {level} ({exp} exp)")
      except:
        continue
      if i >= 9:
        break
    leaderboard_str = "\n".join(leaderboard)
    await ctx.send(f"**Leaderboard:**\n{leaderboard_str}")
  else:
    await ctx.send("The leveling system is currently disabled.")

async def level_up(user_id, user_level):
  # Increase the user's level
  user_level += 1
  leveling_data[user_id] = user_level

  # Check if the user has reached a new level
  if int(user_level) % 5 == 0:
    channel = client.get_channel(int(config["leveling_channel"]))
    await channel.send(f"Congratulations <@{user_id}>! You have reached level {user_level}! :tada:")

  return user_level

@client.event
async def on_message(message):
  if message.author == client.user:
    return

  # Check if leveling is enabled and the user is not a bot
  if config["leveling_enabled"] and not message.author.bot:
    # Check if the user has an entry in the leveling data
    user_id = str(message.author.id)
    if user_id not in leveling_data:
      leveling_data[user_id] = 0

    # Update the user's level and send a message in the leveling channel if they have leveled up
    user_level = await level_up(user_id, leveling_data[user_id])

  await client.process_commands(message)

@client.event
async def on_reaction_add(reaction, user):
    # Ignore reactions by the bot
    if user.bot:
        return

    # Check if the reaction is on a giveaway message
    message = reaction.message
    if message.id in giveaways.keys() and str(reaction) == "🎉":
        giveaway = giveaways[message.id]
        # Add the user to the list of participants
        if user.id not in giveaway["participants"]:
            giveaway["participants"].append(user.id)

# Define the command to mute a user
@client.command()
@commands.has_permissions(kick_members=True)
async def mute(ctx, member: discord.Member, duration: int):
    role = discord.utils.get(ctx.guild.roles, name="Muted")
    if not role:
        role = await ctx.guild.create_role(name="Muted", reason="To mute users")
        for channel in ctx.guild.channels:
            await channel.set_permissions(role, send_messages=False)
    await member.add_roles(role)
    await ctx.send(f"{member.mention} has been muted for {duration} minutes.")
    await asyncio.sleep(duration * 60)
    await member.remove_roles(role)
    await ctx.send(f"{member.mention} has been unmuted.")

# Define the command to kick a user
@client.command()
@commands.has_permissions(kick_members=True)
async def kick(ctx, member: discord.Member, *, reason=None):
    await member.kick(reason=reason)
    await ctx.send(f"{member.mention} has been kicked from the server.")


client.run(config["token"])