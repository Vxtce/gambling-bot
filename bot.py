import discord


from discord import app_commands
import random
import json
import os
from datetime import datetime, timedelta

# ─── CONFIG ───────────────────────────────────────────────────────────────────
TOKEN = os.getenv("TOKEN")
STARTING_BALANCE = 1000
DAILY_REWARD = 500

# ─── DATA STORAGE ─────────────────────────────────────────────────────────────
DATA_FILE = "economy.json"

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_user(data, user_id):
    uid = str(user_id)
    if uid not in data:
        data[uid] = {"balance": STARTING_BALANCE, "last_daily": None, "total_won": 0, "total_lost": 0}
    return data[uid]

# ─── BOT SETUP ────────────────────────────────────────────────────────────────
intents = discord.Intents.default()
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ═══════════════════════════════════════════════════════════════════════════════
#  ECONOMY
# ═══════════════════════════════════════════════════════════════════════════════

@tree.command(name="balance", description="Check your coin balance")
async def balance(interaction: discord.Interaction):
    data = load_data()
    user = get_user(data, interaction.user.id)
    save_data(data)
    embed = discord.Embed(title="💰 Balance", color=0xF1C40F)
    embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
    embed.add_field(name="Coins", value=f"**{user['balance']:,}** 🪙", inline=False)
    embed.add_field(name="Total Won",  value=f"{user['total_won']:,}",  inline=True)
    embed.add_field(name="Total Lost", value=f"{user['total_lost']:,}", inline=True)
    await interaction.response.send_message(embed=embed)

@tree.command(name="daily", description="Claim your 500 free coins (24h cooldown)")
async def daily(interaction: discord.Interaction):
    data = load_data()
    user = get_user(data, interaction.user.id)
    now = datetime.utcnow()
    if user["last_daily"]:
        last = datetime.fromisoformat(user["last_daily"])
        diff = now - last
        if diff < timedelta(hours=24):
            remaining = timedelta(hours=24) - diff
            h, m = divmod(int(remaining.total_seconds()), 3600)
            m //= 60
            await interaction.response.send_message(f"⏳ Already claimed! Come back in **{h}h {m}m**.", ephemeral=True)
            return
    user["balance"] += DAILY_REWARD
    user["last_daily"] = now.isoformat()
    save_data(data)
    embed = discord.Embed(title="🎁 Daily Reward!", description=f"You received **{DAILY_REWARD:,}** 🪙!", color=0x2ECC71)
    embed.set_footer(text=f"New balance: {user['balance']:,}")
    await interaction.response.send_message(embed=embed)

@tree.command(name="give", description="Give coins to another user")
@app_commands.describe(member="Who to give coins to", amount="How many coins")
async def give(interaction: discord.Interaction, member: discord.Member, amount: int):
    if member == interaction.user:
        await interaction.response.send_message("❌ You can't give coins to yourself!", ephemeral=True); return
    if amount <= 0:
        await interaction.response.send_message("❌ Amount must be positive.", ephemeral=True); return
    data = load_data()
    sender = get_user(data, interaction.user.id)
    receiver = get_user(data, member.id)
    if sender["balance"] < amount:
        await interaction.response.send_message("❌ You don't have enough coins!", ephemeral=True); return
    sender["balance"] -= amount
    receiver["balance"] += amount
    save_data(data)
    await interaction.response.send_message(f"✅ **{interaction.user.display_name}** gave **{amount:,}** 🪙 to **{member.display_name}**!")

@tree.command(name="leaderboard", description="Top 10 richest players")
async def leaderboard(interaction: discord.Interaction):
    data = load_data()
    sorted_users = sorted(data.items(), key=lambda x: x[1]["balance"], reverse=True)[:10]
    embed = discord.Embed(title="🏆 Leaderboard — Top 10 Richest", color=0xF39C12)
    desc = ""
    medals = ["🥇","🥈","🥉"]
    for i, (uid, info) in enumerate(sorted_users):
        medal = medals[i] if i < 3 else f"`#{i+1}`"
        try:
            user = await bot.fetch_user(int(uid))
            name = user.display_name
        except:
            name = f"User {uid}"
        desc += f"{medal} **{name}** — {info['balance']:,} 🪙\n"
    embed.description = desc or "No data yet."
    await interaction.response.send_message(embed=embed)

# ═══════════════════════════════════════════════════════════════════════════════
#  COINFLIP
# ═══════════════════════════════════════════════════════════════════════════════

@tree.command(name="coinflip", description="Flip a coin — 2x payout!")
@app_commands.describe(choice="heads or tails", amount="Amount to bet")
@app_commands.choices(choice=[
    app_commands.Choice(name="Heads", value="heads"),
    app_commands.Choice(name="Tails", value="tails"),
])
async def coinflip(interaction: discord.Interaction, choice: str, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Bet must be positive.", ephemeral=True); return
    data = load_data()
    user = get_user(data, interaction.user.id)
    if user["balance"] < amount:
        await interaction.response.send_message(f"❌ Not enough coins. You have **{user['balance']:,}** 🪙.", ephemeral=True); return
    result = random.choice(["heads","tails"])
    won = choice == result
    emoji = "🪙" if result == "heads" else "🐦"
    if won:
        user["balance"] += amount; user["total_won"] += amount
        color, title, outcome = 0x2ECC71, "✅ You Won!", f"+{amount:,} 🪙"
    else:
        user["balance"] -= amount; user["total_lost"] += amount
        color, title, outcome = 0xE74C3C, "❌ You Lost!", f"-{amount:,} 🪙"
    save_data(data)
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="Coin",    value=f"{emoji} **{result.capitalize()}**", inline=True)
    embed.add_field(name="Result",  value=outcome,                               inline=True)
    embed.add_field(name="Balance", value=f"{user['balance']:,} 🪙",            inline=False)
    await interaction.response.send_message(embed=embed)

# ═══════════════════════════════════════════════════════════════════════════════
#  DICE
# ═══════════════════════════════════════════════════════════════════════════════

@tree.command(name="dice", description="Roll 2 dice — beat the bot to win!")
@app_commands.describe(amount="Amount to bet")
async def dice(interaction: discord.Interaction, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Bet must be positive.", ephemeral=True); return
    data = load_data()
    user = get_user(data, interaction.user.id)
    if user["balance"] < amount:
        await interaction.response.send_message(f"❌ Not enough coins. You have **{user['balance']:,}** 🪙.", ephemeral=True); return
    player_roll = random.randint(1,6) + random.randint(1,6)
    bot_roll    = random.randint(1,6) + random.randint(1,6)
    if player_roll > bot_roll:
        user["balance"] += amount; user["total_won"] += amount
        color, title, outcome = 0x2ECC71, "🎲 You Won!", f"+{amount:,} 🪙"
    elif player_roll < bot_roll:
        user["balance"] -= amount; user["total_lost"] += amount
        color, title, outcome = 0xE74C3C, "🎲 You Lost!", f"-{amount:,} 🪙"
    else:
        color, title, outcome = 0x95A5A6, "🎲 Tie — Push!", "No change"
    save_data(data)
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="Your Roll", value=f"**{player_roll}** 🎲", inline=True)
    embed.add_field(name="Bot Roll",  value=f"**{bot_roll}** 🤖",    inline=True)
    embed.add_field(name="Result",    value=outcome,                   inline=False)
    embed.add_field(name="Balance",   value=f"{user['balance']:,} 🪙", inline=False)
    await interaction.response.send_message(embed=embed)

# ═══════════════════════════════════════════════════════════════════════════════
#  SLOTS
# ═══════════════════════════════════════════════════════════════════════════════

SLOT_SYMBOLS = ["🍒","🍋","🍊","🍇","⭐","💎","7️⃣"]
SLOT_WEIGHTS  = [30,  25,  20,  15,   6,   3,   1]
SLOT_PAYOUTS  = {"💎💎💎":50,"7️⃣7️⃣7️⃣":25,"⭐⭐⭐":10,"🍇🍇🍇":5,"🍊🍊🍊":4,"🍋🍋🍋":3,"🍒🍒🍒":2}

@tree.command(name="slots", description="Spin the slot machine!")
@app_commands.describe(amount="Amount to bet (min 10)")
async def slots(interaction: discord.Interaction, amount: int):
    if amount < 10:
        await interaction.response.send_message("❌ Minimum bet is **10** 🪙.", ephemeral=True); return
    data = load_data()
    user = get_user(data, interaction.user.id)
    if user["balance"] < amount:
        await interaction.response.send_message(f"❌ Not enough coins. You have **{user['balance']:,}** 🪙.", ephemeral=True); return
    reels = random.choices(SLOT_SYMBOLS, weights=SLOT_WEIGHTS, k=3)
    result_str = "".join(reels)
    multiplier = SLOT_PAYOUTS.get(result_str, 0)
    if multiplier:
        winnings = amount*multiplier - amount
        user["balance"] += winnings; user["total_won"] += winnings
        color, title, outcome = 0xF1C40F, f"🎰 JACKPOT! ×{multiplier} Payout!", f"+{winnings:,} 🪙"
    elif reels[0]==reels[1] or reels[1]==reels[2] or reels[0]==reels[2]:
        loss = amount // 2
        user["balance"] -= loss; user["total_lost"] += loss
        color, title, outcome = 0xF39C12, "🎰 Close! Two of a kind.", f"-{loss:,} 🪙 (half back)"
    else:
        user["balance"] -= amount; user["total_lost"] += amount
        color, title, outcome = 0xE74C3C, "🎰 No Match — You Lost!", f"-{amount:,} 🪙"
    save_data(data)
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="Reels",   value=f"[ {' | '.join(reels)} ]", inline=False)
    embed.add_field(name="Result",  value=outcome,                      inline=True)
    embed.add_field(name="Balance", value=f"{user['balance']:,} 🪙",   inline=True)
    await interaction.response.send_message(embed=embed)

# ═══════════════════════════════════════════════════════════════════════════════
#  BLACKJACK
# ═══════════════════════════════════════════════════════════════════════════════

SUITS = ["♠","♥","♦","♣"]
RANKS = ["A","2","3","4","5","6","7","8","9","10","J","Q","K"]

def new_deck():
    deck = [(r,s) for s in SUITS for r in RANKS]
    random.shuffle(deck); return deck

def card_value(rank):
    if rank in ("J","Q","K"): return 10
    if rank == "A": return 11
    return int(rank)

def hand_value(hand):
    total = sum(card_value(r) for r,_ in hand)
    aces  = sum(1 for r,_ in hand if r=="A")
    while total > 21 and aces:
        total -= 10; aces -= 1
    return total

def fmt_hand(hand):
    return "  ".join(f"`{r}{s}`" for r,s in hand)

bj_games = {}

@tree.command(name="blackjack", description="Play blackjack!")
@app_commands.describe(amount="Amount to bet")
async def blackjack(interaction: discord.Interaction, amount: int):
    if interaction.user.id in bj_games:
        await interaction.response.send_message("❌ You have an active game! Use `/hit` or `/stand`.", ephemeral=True); return
    if amount <= 0:
        await interaction.response.send_message("❌ Bet must be positive.", ephemeral=True); return
    data = load_data()
    user = get_user(data, interaction.user.id)
    if user["balance"] < amount:
        await interaction.response.send_message(f"❌ Not enough coins. You have **{user['balance']:,}** 🪙.", ephemeral=True); return
    user["balance"] -= amount
    save_data(data)
    deck = new_deck()
    player = [deck.pop(), deck.pop()]
    dealer = [deck.pop(), deck.pop()]
    bj_games[interaction.user.id] = {"deck":deck,"player":player,"dealer":dealer,"bet":amount}
    pval = hand_value(player)
    embed = discord.Embed(title="🃏 Blackjack", color=0x2980B9)
    embed.add_field(name="Your Hand",    value=f"{fmt_hand(player)} — **{pval}**", inline=False)
    embed.add_field(name="Dealer Shows", value=f"{fmt_hand([dealer[0]])}  `??`",   inline=False)
    embed.set_footer(text="Use /hit to draw or /stand to stay.")
    await interaction.response.send_message(embed=embed)

@tree.command(name="hit", description="Draw another card in blackjack")
async def bj_hit(interaction: discord.Interaction):
    if interaction.user.id not in bj_games:
        await interaction.response.send_message("❌ No active game. Start one with `/blackjack`.", ephemeral=True); return
    game = bj_games[interaction.user.id]
    game["player"].append(game["deck"].pop())
    pval = hand_value(game["player"])
    embed = discord.Embed(title="🃏 Blackjack — Hit", color=0x2980B9)
    embed.add_field(name="Your Hand",    value=f"{fmt_hand(game['player'])} — **{pval}**", inline=False)
    embed.add_field(name="Dealer Shows", value=f"{fmt_hand([game['dealer'][0]])}  `??`",   inline=False)
    if pval > 21:
        embed.color = 0xE74C3C; embed.title = "🃏 Bust! You Lost."
        data = load_data()
        user = get_user(data, interaction.user.id)
        user["total_lost"] += game["bet"]; save_data(data)
        del bj_games[interaction.user.id]
        embed.set_footer(text=f"Lost {game['bet']:,} 🪙  |  Balance: {user['balance']:,} 🪙")
    else:
        embed.set_footer(text="Use /hit to draw or /stand to stay.")
    await interaction.response.send_message(embed=embed)

@tree.command(name="stand", description="Stand in blackjack (dealer plays out)")
async def bj_stand(interaction: discord.Interaction):
    if interaction.user.id not in bj_games:
        await interaction.response.send_message("❌ No active game. Start one with `/blackjack`.", ephemeral=True); return
    game = bj_games.pop(interaction.user.id)
    dealer = game["dealer"]
    while hand_value(dealer) < 17:
        dealer.append(game["deck"].pop())
    pval = hand_value(game["player"]); dval = hand_value(dealer)
    data = load_data(); user = get_user(data, interaction.user.id)
    if pval > 21 or (dval <= 21 and dval >= pval):
        if dval == pval:
            user["balance"] += game["bet"]
            color, title, outcome = 0x95A5A6, "🃏 Push — Tie!", "Bet refunded 🪙"
        else:
            user["total_lost"] += game["bet"]
            color, title, outcome = 0xE74C3C, "🃏 Dealer Wins!", f"-{game['bet']:,} 🪙"
    else:
        user["balance"] += game["bet"]*2; user["total_won"] += game["bet"]
        color, title, outcome = 0x2ECC71, "🃏 You Win!", f"+{game['bet']:,} 🪙"
    save_data(data)
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="Your Hand",   value=f"{fmt_hand(game['player'])} — **{pval}**", inline=False)
    embed.add_field(name="Dealer Hand", value=f"{fmt_hand(dealer)} — **{dval}**",         inline=False)
    embed.add_field(name="Result",      value=outcome,                                     inline=True)
    embed.add_field(name="Balance",     value=f"{user['balance']:,} 🪙",                  inline=True)
    await interaction.response.send_message(embed=embed)

# ═══════════════════════════════════════════════════════════════════════════════
#  ROULETTE
# ═══════════════════════════════════════════════════════════════════════════════

RED_NUMBERS   = {1,3,5,7,9,12,14,16,18,19,21,23,25,27,30,32,34,36}
BLACK_NUMBERS = {2,4,6,8,10,11,13,15,17,20,22,24,26,28,29,31,33,35}

@tree.command(name="roulette", description="Spin the roulette wheel!")
@app_commands.describe(bet_type="red/black/odd/even/green or a number 0-36", amount="Amount to bet")
async def roulette(interaction: discord.Interaction, bet_type: str, amount: int):
    if amount <= 0:
        await interaction.response.send_message("❌ Bet must be positive.", ephemeral=True); return
    data = load_data()
    user = get_user(data, interaction.user.id)
    if user["balance"] < amount:
        await interaction.response.send_message(f"❌ Not enough coins. You have **{user['balance']:,}** 🪙.", ephemeral=True); return
    spin = random.randint(0, 36)
    color_emoji = "🟢" if spin==0 else ("🔴" if spin in RED_NUMBERS else "⚫")
    bt = bet_type.lower(); multiplier = 0
    if bt=="red"   and spin in RED_NUMBERS:         multiplier=2
    elif bt=="black" and spin in BLACK_NUMBERS:     multiplier=2
    elif bt=="odd"   and spin!=0 and spin%2==1:     multiplier=2
    elif bt=="even"  and spin!=0 and spin%2==0:     multiplier=2
    elif bt in ("green","0") and spin==0:           multiplier=35
    elif bt.isdigit() and int(bt)==spin:            multiplier=35
    if multiplier:
        winnings = amount*multiplier - amount
        user["balance"] += winnings; user["total_won"] += winnings
        color, title, outcome = 0x2ECC71, "🎡 Winner!", f"+{winnings:,} 🪙 (×{multiplier})"
    else:
        user["balance"] -= amount; user["total_lost"] += amount
        color, title, outcome = 0xE74C3C, "🎡 No luck!", f"-{amount:,} 🪙"
    save_data(data)
    embed = discord.Embed(title=title, color=color)
    embed.add_field(name="Spin Result", value=f"{color_emoji} **{spin}**",               inline=True)
    embed.add_field(name="Your Bet",    value=f"{bet_type.capitalize()} — {amount:,} 🪙", inline=True)
    embed.add_field(name="Outcome",     value=outcome,                                     inline=False)
    embed.add_field(name="Balance",     value=f"{user['balance']:,} 🪙",                  inline=False)
    await interaction.response.send_message(embed=embed)

# ═══════════════════════════════════════════════════════════════════════════════
#  HELP
# ═══════════════════════════════════════════════════════════════════════════════

@tree.command(name="help", description="Show all commands")
async def help_cmd(interaction: discord.Interaction):
    embed = discord.Embed(title="🎰 Madara is the best Owner — Commands", color=0x9B59B6)
    embed.add_field(name="💰 Economy", value=(
        "`/balance` — Check your coins\n"
        "`/daily` — Claim 500 free coins (24h cooldown)\n"
        "`/give @user amount` — Send coins to a friend\n"
        "`/leaderboard` — Top 10 richest players"
    ), inline=False)
    embed.add_field(name="🎮 Games", value=(
        "`/coinflip heads/tails bet` — 2× payout\n"
        "`/dice bet` — Roll higher than the bot\n"
        "`/slots bet` — Spin the slot machine (min 10)\n"
        "`/blackjack bet` then `/hit` or `/stand`\n"
        "`/roulette red/black/odd/even/number bet`"
    ), inline=False)
    embed.set_footer(text=f"All new players start with {STARTING_BALANCE:,} 🪙")
    await interaction.response.send_message(embed=embed)

# ─── RUN ──────────────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user} — Slash commands synced!")
    await bot.change_presence(activity=discord.Game(name="Madara is the best Owner 🎰"))

bot.run(TOKEN)
