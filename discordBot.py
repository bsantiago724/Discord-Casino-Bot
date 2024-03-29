import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import random
import pytz
import asyncio
import sqlite3
import requests
import collections

load_dotenv()

API_KEY = os.getenv("API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
connect = sqlite3.connect('user_data.db')
cursor = connect.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS user_balance (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        bet_amount INTEGER DEFAULT 0,
        daily_last_claimed TEXT,
        hourly_last_claimed TEXT
    )
''')

bot = commands.Bot(command_prefix='.', intents=discord.Intents.all())
bot.remove_command('help')

user_balance = {}
user_used_cards = {}

games = {}

@bot.event
async def on_ready():
    print(f'{bot.user.name} is online')
    daily_reset_task.start()

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("Command not found")
    else:
        pass

class WordleGame:
    def __init__(self):
        self.word_to_guess = None
        self.tries_left = 6
        self.guesses_results = []

    def start_game(self):
        self.word_to_guess = self.get_random_word().upper()
        self.tries_left = 6
        self.guesses_results = []

    def get_random_word(self):
        while True:
            try:
                response = requests.get("https://api.wordnik.com/v4/words.json/randomWord", params={"minLength": 5, "maxLength": 5, "api_key": API_KEY})
                response.raise_for_status()
                word_data = response.json()
                word = word_data['word'].upper()
                if word.isalpha() and word.isascii() and not word.endswith('S'):
                    return word
            except requests.exceptions.RequestException as e:
                print(f"Error fetching word: {e}")
                return ""

    def compare_words(self, guess):
        result = []
        word_to_guess_count = collections.Counter(self.word_to_guess)
        guess_counts = collections.Counter(guess)

        for i in range(len(guess)):
            if guess[i] == self.word_to_guess[i]:
                result.append(":green_square:")
                word_to_guess_count[guess[i]] -= 1
            elif guess[i] in self.word_to_guess and word_to_guess_count[guess[i]] > 0:
                result.append(":yellow_square:")
                word_to_guess_count[guess[i]] -= 1
            else:
                result.append(":black_large_square:")
        return " ".join(result)
    
    def is_valid_word(self, word):
        if not word.isalpha() or not word.isascii() or word.endswith('S'):
            return False
        
        try:
            response = requests.get("https://api.wordnik.com/v4/word.json/" + word.lower() + "/definitions", params={"api_key": "7nblpeddeeinryrevje2k7we86z0fnhewadxal2niazi33iv3"})
            response.raise_for_status()
            return True
        except requests.exceptions.RequestException as e:
            return False

    def play_turn(self, guess):
        if guess.upper() == self.word_to_guess:
            self.tries_left -= 1
            return True, None
        elif not guess.isalpha() or len(guess) != 5 or not self.is_valid_word(guess):
            message = "Please enter a valid 5-letter English word"
            return False, message

        self.tries_left -= 1
        result = self.compare_words(guess.upper())
        if self.tries_left <= 0:
            return False, None
        
        self.guesses_results.append((guess.upper(), result))
        return False, None
    
game = WordleGame()

@bot.command(name='wordle', help='Guess the 5 letter word before running out of tries')
async def wordle(ctx, *, user_word: str):
    gradient = {
        5: 0x97D112,
        4: 0xCBD112,
        3: 0xD1A012,
        2: 0xD16312,
        1: 0xD11212
    }

    color = gradient.get(game.tries_left, 0x3DD112)

    if game.word_to_guess is None or game.tries_left == 0:
        game.start_game()

    game_won, message = game.play_turn(user_word)

    if message:
        await ctx.send(message)

    else:
        embed = discord.Embed(title=f"Wordle - Tries Left: {game.tries_left}", color=color)
        guesses = "\n".join([f"`{item[0]}`" for item in game.guesses_results])
        results = "\n".join([item[1] for item in game.guesses_results])
    
        if game.tries_left <= 0 or game_won:
            if game_won and game.tries_left >= 0:
                embed.color = 0x3DD112
                embed.add_field(name="Congratulations!", value=f"You've guessed the word: {game.word_to_guess}!", inline=False)
            else:
                embed.add_field(name="Game Over", value=f"Sorry, you've run out of tries. The word was: {game.word_to_guess}", inline=False)
            
            guesses += f"\n`{user_word.upper()}`"
            results += f"\n{game.compare_words(user_word.upper())}"

            embed.add_field(name="Previous Guesses", value=guesses, inline=True)
            embed.add_field(name="Result", value=results, inline=True)

            game.start_game()
        else:
            embed.add_field(name="Previous Guesses", value=guesses, inline=True)
            embed.add_field(name="Result", value=results, inline=True)

        await ctx.send(embed=embed)

@bot.command(name='help', help='Display a list of available commands')
async def help_command(ctx):
    embed_page_1 = discord.Embed(title="Command Help - General", color=0x89CFF0)
    embed_page_2 = discord.Embed(title="Command Help - Games", color=0x89CFF0)

    categories = {
        "General": [
            ('.daily', 'Claim your daily prize'),
            ('.hourly', 'Claim your hourly prize'),
            ('.balance', 'View your current balance'),
            ('.leaderboard', 'View the top coin earners'),
            ('.help', 'Display a list of available commands')
        ],
        "Games": [
            ('.wordle', 'Guess the 5 letter word before running out of tries'),
            ('.blackjack', 'Play a hand of blackjack vs the Bot'),
            ('.minesweeper', 'Open boxes and avoid bombs'),
            ('.dice', 'Roll over/under on a dice'),
            ('.rps', 'Play rock-paper-scissors against the bot'),
            ('.coinflip', 'Flip a coin')
        ]
    }

    for category, commands_list in categories.items():
        for command, description in commands_list:
            if category == "General":
                embed_page_1.add_field(name=command, value=description, inline=False)
            elif category == "Games":
                embed_page_2.add_field(name=command, value=description, inline=False)

    pages = [embed_page_1, embed_page_2]
    current_page = 0

    def update_page_number(embed, current, total):
        embed.set_footer(text=f"Page {current + 1}/{total}")

    update_page_number(embed_page_1, current_page, len(pages))
    update_page_number(embed_page_2, current_page, len(pages))

    message = await ctx.send(embed=pages[current_page])
    await message.add_reaction("⬅️")
    await message.add_reaction("➡️")

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ["⬅️", "➡️"]

    while True:
        try:
            reaction, _ = await bot.wait_for('reaction_add', timeout=30.0, check=check)
        except asyncio.TimeoutError:
            break

        if str(reaction.emoji) == "⬅️":
            current_page = (current_page - 1) % len(pages)
        elif str(reaction.emoji) == "➡️":
            current_page = (current_page + 1) % len(pages)

        await message.edit(embed=pages[current_page])
        update_page_number(pages[current_page], current_page, len(pages))
        await reaction.remove(ctx.author)

    await message.clear_reactions()

@bot.command(name='daily', help='Claim your daily prize')
async def daily(ctx):
    user_id = ctx.author.id
    create_user_balance(user_id)

    cursor.execute('SELECT daily_last_claimed FROM user_balance WHERE user_id = ?', (user_id,))
    last_claimed = datetime.fromisoformat(cursor.fetchone()[0])

    local_timezone = pytz.timezone('America/New_York')
    current_time = datetime.now(local_timezone)
    midnight_today = local_timezone.localize(datetime(current_time.year, current_time.month, current_time.day, 0, 0, 0))

    time_remaining = midnight_today + timedelta(days=1) - current_time

    if (current_time.date() - last_claimed.date()) >= timedelta(days=1):  # Updated line
        chips = random.randint(500, 2000)
        cursor.execute('UPDATE user_balance SET balance = balance + ?, daily_last_claimed = ? WHERE user_id = ?', (chips, current_time, user_id))
        connect.commit()
        await ctx.send(f'You claimed your daily and received {chips} chips.')
    else:
        time_remaining_str = str(time_remaining).split(".")[0]
        await ctx.send(f'You already claimed your daily. You can claim your next daily in {time_remaining_str}')
    return

@bot.command(name='hourly', help='Claim your hourly prize')
async def hourly(ctx):
    user_id = ctx.author.id
    create_user_balance(user_id)

    cursor.execute('SELECT hourly_last_claimed FROM user_balance WHERE user_id = ?', (user_id,))
    last_claimed = datetime.fromisoformat(cursor.fetchone()[0])
    current_time = datetime.now()

    cooldown_duration = timedelta(seconds=60 * 60)

    if (current_time - last_claimed) >= cooldown_duration:
        chips = random.randint(100, 200)
        cursor.execute('UPDATE user_balance SET balance = balance + ?, hourly_last_claimed = ? WHERE user_id = ?', (chips, current_time, user_id))
        connect.commit()
        await ctx.send(f'You claimed your hourly and received {chips} chips.')
    else:
        time_remaining = cooldown_duration - (current_time - last_claimed)
        time_remaining_str = str(time_remaining).split(".")[0]
        await ctx.send(f'You already claimed your hourly. You can claim your next hourly in {time_remaining_str}')

@bot.command(name='balance', aliases=['bal'], help='View your current balance')
async def balance(ctx):
    user_id = ctx.author.id
    create_user_balance(user_id)

    cursor.execute('SELECT balance FROM user_balance WHERE user_id = ?', (user_id,))
    user_balance = cursor.fetchone()[0]

    await ctx.send(f'Balance: {user_balance} chips')

@bot.command(name='rps', help='Play rock-paper-scissors against the bot')
async def rps(ctx, bet_amount = None):
    choices = ['🪨', '📄', '✂️']

    if bet_amount is None:
        await ctx.send("Usage: `.rps [bet amount]`")
        return

    try:
        bet_amount = int(bet_amount)
    except ValueError:
        await ctx.send("Please enter a valid bet amount.\n"
                       "Usage: `.rps [bet amount]`")
        return

    if bet_amount <= 0:
        await ctx.send("Please enter a bet amount greater than 0.\n"
                       "Usage: `.rps [bet amount]`")
        return

    user_id = ctx.author.id
    create_user_balance(user_id)

    cursor.execute('SELECT balance FROM user_balance WHERE user_id = ?', (user_id,))
    user_balance = cursor.fetchone()[0]

    if bet_amount > user_balance:
        await ctx.send("You don't have enough chips to place that bet.")
        return

    await asyncio.sleep(1)
    
    embed = discord.Embed(title="Rock, Paper, Scissors", description="React with your choice:", color=0xff9900)
    embed.add_field(name="🪨", value="Rock", inline=True)
    embed.add_field(name="📄", value="Paper", inline=True)
    embed.add_field(name="✂️", value="Scissors", inline=True)
    embed.set_footer(text=f"Bet Amount: {bet_amount} chips")

    message = await ctx.send(embed=embed)

    for emoji in choices:
        await message.add_reaction(emoji)

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in choices

    try:
        reaction, _ = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except TimeoutError:
        await ctx.send("Took too long to pick, please try again.")
        return

    user_choice = str(reaction.emoji)

    bot_choice = random.choice(choices)

    player_choice = f"You chose {user_choice}"
    bot_message = f"Bot chose {bot_choice} "

    await asyncio.sleep(1)
    
    if user_choice == bot_choice:
        result_message = (f"{player_choice}\n"
                          f"{bot_message}\n"
                          "It's a tie!")
    elif (
        (user_choice == '🪨' and bot_choice == '✂️') or
        (user_choice == '📄' and bot_choice == '🪨') or
        (user_choice == '✂️' and bot_choice == '📄')
    ):
        cursor.execute('UPDATE user_balance SET balance = balance + ? WHERE user_id = ?', (bet_amount, user_id))
        connect.commit()
        result_message = (f"{player_choice}\n"
                          f"{bot_message}\n"
                          f"You win! +{bet_amount} coins.")
    else:
        cursor.execute('UPDATE user_balance SET balance = balance - ? WHERE user_id = ?', (bet_amount, user_id))
        connect.commit()
        result_message = (f"{player_choice}\n"
                          f"{bot_message}\n"
                          f"You lose. -{bet_amount} coins.")

    await ctx.send(result_message)

@bot.command(name='coinflip', aliases=['cf'], help='Flip a coin')
async def coinflip(ctx, bet_amount = None):
    choices = ['🌝', '🌚']

    if bet_amount is None:
        await ctx.send("Usage: `.cf [bet amount]`")
        return

    try:
        bet_amount = int(bet_amount)
    except ValueError:
        await ctx.send("Please enter a valid bet amount.\n"
                       "Usage: `.cf [bet amount]`")
        return

    if bet_amount <= 0:
        await ctx.send("Please enter a bet amount greater than 0.\n"
                       "Usage: `.cf [bet amount]`")
        return

    user_id = ctx.author.id
    create_user_balance(user_id)

    cursor.execute('SELECT balance FROM user_balance WHERE user_id = ?', (user_id,))
    user_balance = cursor.fetchone()[0]

    if bet_amount > user_balance:
        await ctx.send("You don't have enough chips to place that bet.")
        return

    await asyncio.sleep(1)
    
    embed = discord.Embed(title="Heads or Tails", description="React with your choice:", color=0xff9900)
    embed.add_field(name="🌝", value="Heads", inline=True)
    embed.add_field(name="🌚", value="Tails", inline=True)
    embed.set_footer(text=f"Bet Amount: {bet_amount} chips")

    message = await ctx.send(embed=embed)

    for emoji in choices:
        await message.add_reaction(emoji)

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in choices

    try:
        reaction, _ = await bot.wait_for('reaction_add', timeout=30.0, check=check)
    except TimeoutError:
        await ctx.send("Took too long to pick, please try again.")
        return

    user_choice = str(reaction.emoji)
    flip = random.choice(choices)
    flip_message = f"Coin landed on {flip}."

    await asyncio.sleep(1)
    
    if user_choice == flip:
        cursor.execute('UPDATE user_balance SET balance = balance + ? WHERE user_id = ?', (bet_amount, user_id))
        connect.commit()
        result_message = (f"{flip_message}\n"
                          "You win!\n"
                          f"+{bet_amount} coins.")
    
    elif user_choice != flip:
        cursor.execute('UPDATE user_balance SET balance = balance - ? WHERE user_id = ?', (bet_amount, user_id))
        connect.commit()
        result_message = (f"{flip_message}\n"
                          "You lose.\n"
                          f"-{bet_amount} coins.")

    await ctx.send(result_message)

@bot.command(name='blackjack', aliases=['bj'], help='Play a hand of blackjack vs the Bot')
async def blackjack(ctx, bet_amount=None):

    if bet_amount is None:
        await ctx.send("Usage: `.bj [bet amount]`")
        return

    try:
        bet_amount = int(bet_amount)
    except ValueError:
        await ctx.send("Please enter a valid bet amount.\n"
                       "Usage: `.bj [bet amount]`")
        return

    if bet_amount <= 0:
        await ctx.send("Please enter a bet amount greater than 0.\n"
                       "Usage: `.bj [bet amount]`")
        return

    user_id = ctx.author.id
    create_user_balance(user_id)

    cursor.execute('SELECT balance FROM user_balance WHERE user_id = ?', (user_id,))
    user_balance = cursor.fetchone()[0]

    if bet_amount > user_balance:
        await ctx.send("You don't have enough chips to place that bet.")
        return

    player_cards = [draw_card(user_id), draw_card(user_id)]
    bot_cards = [draw_card(user_id), draw_card(user_id)]

    if user_blackjack(player_cards):
        embed_blackjack = discord.Embed(title="Blackjack", color=0x00ff00)
        embed_blackjack.add_field(name="Your cards", value=f"{', '.join(player_cards)}\nValue: {hand_value(player_cards)}", inline=False)
        embed_blackjack.add_field(name="Dealer's cards", value=f"{bot_cards[0]}, {bot_cards[1]}\nValue: {hand_value(bot_cards)}", inline=False)
        embed_blackjack.add_field(name="Result", value=f"Blackjack! You win! +{int(bet_amount * 1.5)} chips.", inline=False)
        await ctx.send(embed=embed_blackjack)

        cursor.execute('UPDATE user_balance SET balance = balance + ? WHERE user_id = ?', (int(bet_amount * 1.5), user_id))
        connect.commit()
        return

    embed = discord.Embed(title="Blackjack", color=0xff9900)
    embed.add_field(name="Your cards", value=f"{', '.join(player_cards)}\nValue: {hand_value(player_cards)}", inline=False)
    embed.add_field(name="Dealer's cards", value=f"{bot_cards[0]}, ?\nValue: {hand_value([bot_cards[0]])}", inline=False)
    embed.set_footer(text=f"Bet Amount: {bet_amount} chips")

    message = await ctx.send(embed=embed)
    await message.add_reaction("✅")
    await message.add_reaction("❌")

    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ["✅", "❌"]

    while True:
        try:
            reaction, _ = await bot.wait_for('reaction_add', timeout=60.0, check=check)
        except TimeoutError:
            await ctx.send("Took too long to decide. Game over.")
            cursor.execute('UPDATE user_balance SET balance = balance - ? WHERE user_id = ?', (int(bet_amount), user_id))
            connect.commit()
            return

        if str(reaction.emoji) == "✅":
            new_card = draw_card(user_id)
            player_cards.append(new_card)

            if hand_value(player_cards) > 21:
                embed_bust = discord.Embed(title="Blackjack", color=0xff0000)
                embed_bust.add_field(name="Your cards", value=f"{', '.join(player_cards)}\nValue: {hand_value(player_cards)}", inline=False)
                embed_bust.add_field(name="Dealer's cards", value=f"{bot_cards[0]}, {bot_cards[1]}\nValue: {hand_value(bot_cards)}", inline=False)
                embed_bust.add_field(name="Result", value=f"Bust! You drew a {new_card}. You lose.", inline=False)
                await ctx.send(embed=embed_bust)

                cursor.execute('UPDATE user_balance SET balance = balance - ? WHERE user_id = ?', (int(bet_amount), user_id))
                connect.commit()
                return

            else:
                embed = discord.Embed(title="Blackjack", color=0xff9900)
                embed.add_field(name="Result", value=f"You drew a {new_card}", inline=False)
                embed.add_field(name="Your cards", value=f"{', '.join(player_cards)}\nValue: {hand_value(player_cards)}", inline=False)
                embed.add_field(name="Dealer's cards", value=f"{bot_cards[0]}, ?\nValue: {hand_value([bot_cards[0]])}", inline=False)
                embed.set_footer(text=f"Bet Amount: {bet_amount} chips")
                await message.edit(embed=embed)

                await asyncio.sleep(1)
                await message.clear_reactions()
                await message.add_reaction("✅")
                await message.add_reaction("❌")

        elif str(reaction.emoji) == "❌":
            break

    while hand_value(bot_cards) < 17:
        await asyncio.sleep(1)
        new_card = draw_card(user_id)
        bot_cards.append(new_card)
        embed_dealer_hit = discord.Embed(title="Blackjack", color=0xff9900)
        revealed_value = hand_value(bot_cards[:-1])
        embed_dealer_hit.add_field(name="Dealer's Turn", value=f"Dealer hits. Dealer's cards: {', '.join(bot_cards[:-1])}, ?\nValue: {revealed_value}", inline=False)
        await ctx.send(embed=embed_dealer_hit)

    await asyncio.sleep(1)

    player_value = hand_value(player_cards)
    dealer_value = hand_value(bot_cards)

    embed_result = discord.Embed(title="Blackjack", color=0xff9900)
    embed_result.add_field(name="Your cards", value=f"{', '.join(player_cards)}\nValue: {player_value}", inline=False)
    embed_result.add_field(name="Dealer's cards", value=f"{', '.join(bot_cards)}\nValue: {dealer_value}", inline=False)
    await ctx.send(embed=embed_result)

    await asyncio.sleep(1)
    
    if dealer_value > 21 or (player_value <= 21 and player_value > dealer_value):
        embed_win = discord.Embed(title="Blackjack", color=0x00ff00)
        embed_win.add_field(name="Result", value=f"You win! +{bet_amount} chips.", inline=False)
        await ctx.send(embed=embed_win)
        cursor.execute('UPDATE user_balance SET balance = balance + ? WHERE user_id = ?', (bet_amount, user_id))
    elif player_value == dealer_value:
        embed_tie = discord.Embed(title="Blackjack", color=0xffff00)
        embed_tie.add_field(name="Result", value="It's a tie!", inline=False)
        await ctx.send(embed=embed_tie)
    else:
        embed_lose = discord.Embed(title="Blackjack", color=0xff0000)
        embed_lose.add_field(name="Result", value=f"You lose. -{bet_amount} chips.", inline=False)
        await ctx.send(embed=embed_lose)
        cursor.execute('UPDATE user_balance SET balance = balance - ? WHERE user_id = ?', (bet_amount, user_id))

    connect.commit()

@bot.command(name='dice', help='dice idk')
async def dice(ctx, choice: str = None, number: str = None, bet_amount = None):
    if choice is None or number is None or bet_amount is None:
        await ctx.send("Usage: `.dice [over/under] [number] [bet amount]`")
        return

    try:
        bet_amount = int(bet_amount)
        if not (0 < float(number) < 100):
            raise ValueError("Number must be between 0 and 100")
    except ValueError:
        await ctx.send("Incorrect usage.\n"
                       "Usage: `.dice [over/under] [number] [bet amount]`")
        return
	
    if choice.lower() not in ['over', 'under']:
        await ctx.send("Invalid choice. Use 'over' or 'under'.\n"
                       "Usage: `.dice [over/under] [number] [bet amount]`")
        return

    if bet_amount <= 0:
        await ctx.send("Please enter a bet amount greater than 0.\n"
                       "Usage: `.dice [over/under] [number] [bet amount]`")
        return

    user_id = ctx.author.id
    create_user_balance(user_id)

    cursor.execute('SELECT balance FROM user_balance WHERE user_id = ?', (user_id,))
    user_balance = cursor.fetchone()[0]

    if bet_amount > user_balance:
        await ctx.send("You don't have enough chips to place that bet.")
        return
    
    generated_number = round(random.uniform(0.01, 99.99), 2)

    number = float(number)
    if choice.lower() == 'over':
        if 5.99 <= number <= 99.98:
            multiplier = 100 / (100 - number)
        else:
            await ctx.send("Invalid number range.\n"
                           "5.99 - 99.98 for over rolls")
            return
    else:
        if 0.01 <= number <= 94:
            multiplier = 100 / number
        else:
            await ctx.send("Invalid number range.\n"
                           "0.01 - 94 for under rolls")
            return

    if (choice.lower() == 'over' and generated_number > number) or \
       (choice.lower() == 'under' and generated_number < number):
        winnings = round(bet_amount * multiplier) - bet_amount
        cursor.execute('UPDATE user_balance SET balance = balance + ? WHERE user_id = ?', (winnings, user_id))
        if winnings > 1:
            result_message = (f"You win {winnings} chips!")
        else:
            result_message = (f"You win {winnings} chip!")
        color = 0x00ff00
    else:
        cursor.execute('UPDATE user_balance SET balance = balance - ? WHERE user_id = ?', (bet_amount, user_id))
        if bet_amount > 1:
            result_message = (f"You lose {bet_amount} chips")
        else:
            result_message = (f"You lose {bet_amount} chip")
        color = 0xff0000
        
    bar_length = 20
    bar_position = int((generated_number / 100) * bar_length)
    bar = '[' + '=' * bar_position + '>' + '-' * (bar_length - bar_position - 1) + ']'

    embed = discord.Embed(title="Dice Roll Result", color=color)
    embed.add_field(name="Your Choice", value=choice.capitalize(), inline=True)
    embed.add_field(name="Your Number", value=str(number), inline=True)
    embed.add_field(name="Your Bet", value=bet_amount, inline=True)
    embed.add_field(name=f"Rolled Number - {generated_number}", value=f"{bar}", inline=True)
    embed.add_field(name="Multiplier", value=f"{multiplier:.2f}", inline=True)
    embed.add_field(name="Winnings/Loss", value=result_message, inline=False)
    
    await ctx.send(embed=embed)
    
@bot.command(name='leaderboard', aliases=['lb'], help='View the top coin earners')
async def leaderboard(ctx):
    cursor.execute('SELECT user_id, balance FROM user_balance ORDER BY balance DESC')
    user_data = cursor.fetchall()

    if not user_data:
        await ctx.send("No users found.")
        return

    leaderboard_embed = discord.Embed(title="Leaderboard", color=0xff9900)

    for index, (user_id, balance) in enumerate(user_data, start=1):
        user = await bot.fetch_user(user_id)
        username = user.name if user else f'User ID {user_id}'
        leaderboard_embed.add_field(name=f"{index}. {username}", value=f"{balance} chips", inline=False)

    await ctx.send(embed=leaderboard_embed)
    
@tasks.loop(hours=24)
async def daily_reset_task():
    now_utc = datetime.utcnow()
    utc_timezone = pytz.timezone('UTC')
    now_utc = utc_timezone.localize(now_utc)

    local_timezone = pytz.timezone('America/New_York') 
    now_local = now_utc.astimezone(local_timezone)

    if now_local.hour == 0 and now_local.minute == 0:
        cursor.execute('SELECT user_id, daily_last_claimed FROM user_balance')
        user_data = cursor.fetchall()

        for user_id, last_claimed in user_data:
            last_claimed_time = datetime.fromisoformat(last_claimed)
            time_difference = now_local - last_claimed_time

            if time_difference >= timedelta(days=1):
                cursor.execute('UPDATE user_balance SET daily_last_claimed = ?, hourly_last_claimed = ? WHERE user_id = ?', (now_local, now_local, user_id))
                connect.commit()
                
def create_user_balance(user_id):
    cursor.execute('SELECT * FROM user_balance WHERE user_id = ?', (user_id,))
    user_data = cursor.fetchone()

    if not user_data:
        current_time = datetime.now()
        initial_last_claimed = current_time - timedelta(days=1)  
        cursor.execute('INSERT INTO user_balance (user_id, balance, bet_amount, daily_last_claimed, hourly_last_claimed) VALUES (?, 0, 0, ?, ?)', (user_id, initial_last_claimed, initial_last_claimed))
        connect.commit()

def draw_card(user_id):
    if user_id not in user_used_cards:
        user_used_cards[user_id] = set()

    cards = ['A❤️', '2❤️', '3❤️', '4❤️', '5❤️', '6❤️', '7❤️', '8❤️', '9❤️', '10❤️', 'J❤️', 'Q❤️', 'K❤️', 
             'A♠️', '2♠️', '3♠️', '4♠️', '5♠️', '6♠️', '7♠️', '8♠️', '9♠️', '10♠️', 'J♠️', 'Q♠️', 'K♠️',
             'A♦️', '2♦️', '3♦️', '4♦️', '5♦️', '6♦️', '7♦️', '8♦️', '9♦️', '10♦️', 'J♦️', 'Q♦️', 'K♦️',
             'A♣️', '2♣️', '3♣️', '4♣️', '5♣️', '6♣️', '7♣️', '8♣️', '9♣️', '10♣️', 'J♣️', 'Q♣️', 'K♣️']
    
    card = random.choice(cards)
    while card in user_used_cards[user_id]:
        card = random.choice(cards)

    user_used_cards[user_id].add(card)
    return card

def hand_value(cards):
    value = 0
    aces = 0

    for card in cards:
        if card[0].isdigit() and card[0] != '1':
            value += int(card[0])
        elif card[0] == '1' and card[1] == '0':
            value += 10
        elif card[0] in ['J', 'Q', 'K']:
            value += 10
        elif card[0] == 'A':
            value += 11
            aces += 1

    while aces > 0 and value > 21:
        value -= 10
        aces -= 1

    return value

def user_blackjack(cards):
    return len(cards) == 2 and hand_value(cards) == 21
       
bot.run(BOT_TOKEN)