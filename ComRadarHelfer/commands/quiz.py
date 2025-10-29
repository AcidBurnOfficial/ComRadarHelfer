# =============================================
# 📂 Einstellungen & Konstanten
# =============================================
import discord
from discord.ext import commands, tasks
from discord import app_commands
import json, os, random
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

QUESTIONS_FILE = os.path.join(DATA_DIR, "quizfragen.json")
POOL_FILE = os.path.join(DATA_DIR, "quizpool.json")
ANSWERS_FILE = os.path.join(DATA_DIR, "quiz_answers.json")
SCORES_FILE = os.path.join(DATA_DIR, "quiz_scores.json")
GUILD_FILE = os.path.join(DATA_DIR, "guild_settings.json")
BERLIN_TZ = ZoneInfo("Europe/Berlin")

# =============================================
# 🔧 Hilfsfunktionen
# =============================================
def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_quiz_channel(bot, guild_id):
    guilds = load_json(GUILD_FILE)
    channel_id = guilds.get(str(guild_id), {}).get("QUIZ_CHANNEL_ID")
    return bot.get_channel(channel_id) if channel_id else None

# =============================================
# 🎟️ Antwort-Buttons
# =============================================
class QuizAnswerButton(discord.ui.Button):
    def __init__(self, label, option, date, guild_id):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.option = option
        self.date = date
        self.guild_id = guild_id

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        answers = load_json(ANSWERS_FILE)
        scores = load_json(SCORES_FILE)
        today_data = answers.setdefault(self.date, {}).setdefault(str(self.guild_id), {})

        if user_id in today_data:
            await interaction.response.send_message("⚠️ Du hast heute schon geantwortet!", ephemeral=True)
            return

        questions = load_json(QUESTIONS_FILE)
        question_info = questions[self.date][str(self.guild_id)]
        correct_answer = question_info["korrekt"]
        loesung = question_info.get("loesung", "Keine Begründung angegeben.")
        is_correct = (self.option == correct_answer)

        today_data[user_id] = {"antwort": self.option, "richtig": is_correct}
        save_json(ANSWERS_FILE, answers)

        # Punkte speichern
        guild_scores = scores.setdefault(str(self.guild_id), {})
        if is_correct:
            guild_scores[user_id] = guild_scores.get(user_id, 0) + 1
            save_json(SCORES_FILE, scores)

        # Immer Embed mit richtiger Antwort + Begründung (ephemeral)
        embed = discord.Embed(
            title="✅ Richtige Antwort!" if is_correct else "❌ Falsche Antwort!",
            description=(
                f"**Deine Antwort:** {self.option}\n"
                f"**Richtige Antwort:** {correct_answer}\n"
                f"🧠 **Begründung:** {loesung}"
            ),
            color=discord.Color.green() if is_correct else discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class QuizAnswerView(discord.ui.View):
    def __init__(self, date, options, guild_id):
        super().__init__(timeout=None)
        for i, opt in enumerate(options):
            self.add_item(QuizAnswerButton(chr(65+i), opt, date, guild_id))

# =============================================
# 🎯 Haupt-Cog
# =============================================
class DailyQuiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_question_task.start()
        self.daily_winner_task.start()

    def cog_unload(self):
        self.daily_question_task.cancel()
        self.daily_winner_task.cancel()

    # -----------------------------------------
    # 🕛 Jeden Tag automatisch neue Frage posten
    # -----------------------------------------
    @tasks.loop(minutes=1)
    async def daily_question_task(self):
        now = datetime.now(BERLIN_TZ)
        if now.hour == 0 and now.minute == 0:
            for guild_id in load_json(GUILD_FILE).keys():
                await self.post_daily_question(int(guild_id))

    async def post_daily_question(self, guild_id: int, category: str = None):
        pool = load_json(POOL_FILE)
        used = load_json(QUESTIONS_FILE)
        today = datetime.now().strftime("%Y-%m-%d")

        used.setdefault(today, {})
        if str(guild_id) in used[today]:
            return

        # 🔹 Kategorie filtern
        available = {k:v for k,v in pool.items() if (not category or v.get("kategorie")==category)}
        if not available:
            return

        key = random.choice(list(available.keys()))
        question_data = available[key]
        pool.pop(key)
        save_json(POOL_FILE, pool)

        used[today][str(guild_id)] = question_data
        save_json(QUESTIONS_FILE, used)

        channel = get_quiz_channel(self.bot, guild_id)
        if not channel:
            return

        question = question_data["frage"]
        options = question_data["optionen"]

        embed = discord.Embed(
            title=f"🎉 Quiz für {datetime.now().strftime('%d.%m.%Y')}",
            description=f"**{question}**\n\n" + "\n".join([f"{chr(65+i)}️⃣ {opt}" for i,opt in enumerate(options)]),
            color=discord.Color.gold()
        )
        embed.set_footer(text="Wähle die richtige Antwort! Du hast nur einen Versuch.")
        await channel.send(embed=embed, view=QuizAnswerView(today, options, guild_id))

    # -----------------------------------------
    # /quiz_post – Admin kann Kategorie wählen
    # -----------------------------------------
    @app_commands.command(name="quiz_start", description="Postet die heutige Quizfrage manuell im Quiz-Channel.")
    @app_commands.describe(category="Kategorie auswählen (z.B. Adventsquiz, Filmquiz)")
    async def quiz_post(self, interaction: discord.Interaction, category: str = None):
        await self.post_daily_question(interaction.guild.id, category)
        await interaction.response.send_message(f"✅ Quizfrage für Kategorie '{category or 'All'}' gepostet!", ephemeral=True)

    # -----------------------------------------
    # 🧩 Neue Frage zum Pool hinzufügen
    # -----------------------------------------
    @app_commands.command(name="quiz_add", description="Fügt eine neue Quizfrage in den Fragenpool hinzu.")
    @app_commands.describe(
        frage="Die Quizfrage",
        option_a="Antwort A",
        option_b="Antwort B",
        option_c="Antwort C",
        korrekt="Welche Antwort ist korrekt? (A, B oder C)",
        loesung="Begründung oder Erklärung zur richtigen Antwort",
        kategorie="Kategorie der Frage (z.B. Adventsquiz, Sommerquiz, Filmquiz)"
    )
    async def add_question(
        self,
        interaction: discord.Interaction,
        frage: str,
        option_a: str,
        option_b: str,
        option_c: str,
        korrekt: str,
        loesung: str,
        kategorie: str
    ):
        korrekt = korrekt.strip().upper()
        if korrekt not in ["A","B","C"]:
            await interaction.response.send_message("❌ Bitte gib A, B oder C als richtige Antwort an!", ephemeral=True)
            return

        pool = load_json(POOL_FILE)
        new_id = str(len(pool)+1)
        korrekte_option = {"A": option_a, "B": option_b, "C": option_c}[korrekt]
        pool[new_id] = {
            "frage": frage,
            "optionen": [option_a, option_b, option_c],
            "korrekt": korrekte_option,
            "loesung": loesung,
            "kategorie": kategorie
        }
        save_json(POOL_FILE, pool)

        embed = discord.Embed(
            title="✅ Neue Frage hinzugefügt",
            description=(
                f"**Frage:** {frage}\n"
                f"A️⃣ {option_a}\nB️⃣ {option_b}\nC️⃣ {option_c}\n"
                f"✅ **Korrekte Antwort:** {korrekte_option}\n"
                f"🧠 **Begründung:** {loesung}\n"
                f"📂 **Kategorie:** {kategorie}"
            ),
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -----------------------------------------
    # 🕛 Täglicher Gewinner wird automatisch gezogen
    # -----------------------------------------
    @tasks.loop(minutes=1)
    async def daily_winner_task(self):
        now = datetime.now(BERLIN_TZ)
        if now.hour == 0 and now.minute == 0:
            yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
            answers = load_json(ANSWERS_FILE)
            scores = load_json(SCORES_FILE)

            for guild_id in load_json(GUILD_FILE).keys():
                guild_answers = answers.get(yesterday, {}).get(guild_id, {})
                if not guild_answers:
                    continue

                correct_users = [uid for uid, info in guild_answers.items() if info["richtig"]]
                channel = get_quiz_channel(self.bot, int(guild_id))
                if not channel:
                    continue

                if not correct_users:
                    await channel.send(f"❌ Kein Gewinner für den {yesterday} – niemand hatte die richtige Antwort!")
                    continue

                winner_id = random.choice(correct_users)
                winner = channel.guild.get_member(int(winner_id))
                await channel.send(f"🏆 **Tagesgewinner ({yesterday})** ist {winner.mention}! Glückwunsch 🎉")

                # Punkte zählen
                guild_scores = scores.setdefault(guild_id, {})
                for uid in correct_users:
                    guild_scores[uid] = guild_scores.get(uid,0)+1
                save_json(SCORES_FILE, scores)

    # -----------------------------------------
    # /quiz_end – Gesamtsieger
    # -----------------------------------------
    @app_commands.command(name="quiz_end", description="Beendet das Quiz und ermittelt den Gesamtsieger.")
    async def end_quiz(self, interaction: discord.Interaction):
        scores = load_json(SCORES_FILE).get(str(interaction.guild.id), {})
        if not scores:
            await interaction.response.send_message("❌ Keine Teilnehmer gefunden!", ephemeral=True)
            return

        max_points = max(scores.values())
        winners = [uid for uid, pts in scores.items() if pts==max_points]
        final_winner = random.choice(winners) if len(winners)>1 else winners[0]
        member = interaction.guild.get_member(int(final_winner))

        embed = discord.Embed(
            title="🏁 Quiz-Gesamtsieger",
            description=f"🎉 {member.mention} hat das Quiz gewonnen!\nPunkte: **{max_points}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        channel = get_quiz_channel(self.bot, interaction.guild.id)
        if channel:
            await channel.send(embed=embed)

# -----------------------------------------
# ⚙️ Setup
# -----------------------------------------
async def setup(bot):
    await bot.add_cog(DailyQuiz(bot))
