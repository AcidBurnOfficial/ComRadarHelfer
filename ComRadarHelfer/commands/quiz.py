import discord
from discord.ext import commands, tasks
from discord import app_commands
import json
import os
import random
from datetime import datetime, timedelta
from config import GIVEAWAY_CHANNEL_ID, TEST_GUILD_ID

# 📁 Datenpfade
QUESTIONS_FILE = "data/quizfragen.json"  # bereits gepostete Fragen (nach Datum)
POOL_FILE = "data/quizpool.json"          # Pool aus dem täglich gewählt wird
ANSWERS_FILE = "data/quiz_answers.json"
SCORES_FILE = "data/quiz_scores.json"
os.makedirs("data", exist_ok=True)


# 🧠 Hilfsfunktionen
def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)


# -------------------------------------------------
# 🎯 Haupt-Cog
# -------------------------------------------------
class DailyQuiz(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.daily_winner_task.start()
        self.daily_question_task.start()

    def cog_unload(self):
        self.daily_winner_task.cancel()
        self.daily_question_task.cancel()

    # -------------------------------------------------
    # 🕛 Jeden Tag automatisch neue Frage posten
    # -------------------------------------------------
    @tasks.loop(minutes=1)
    async def daily_question_task(self):
        now = datetime.now()
        if now.hour == 0 and now.minute == 0:  # 00:00 Uhr
            await self.post_daily_question()

    async def post_daily_question(self):
        pool = load_json(POOL_FILE)
        used = load_json(QUESTIONS_FILE)
        today = datetime.now().strftime("%Y-%m-%d")

        if today in used:
            return  # Frage für heute schon vorhanden

        if not pool:
            print("⚠️ Keine Fragen mehr im Pool vorhanden!")
            return

        # 🔀 Zufällige Frage aus dem Pool ziehen
        key = random.choice(list(pool.keys()))
        question_data = pool.pop(key)
        used[today] = question_data

        save_json(POOL_FILE, pool)
        save_json(QUESTIONS_FILE, used)

        channel = self.bot.get_channel(GIVEAWAY_CHANNEL_ID)
        if not channel:
            print("⚠️ Giveaway-Channel nicht gefunden!")
            return

        question = question_data["frage"]
        options = question_data["optionen"]

        embed = discord.Embed(
            title=f"🎉 Tägliches Gewinnspiel – {today}",
            description=f"**{question}**\n\n"
                        + "\n".join([f"{chr(65+i)}️⃣ {opt}" for i, opt in enumerate(options)]),
            color=discord.Color.gold(),
        )
        embed.set_footer(text="Wähle die richtige Antwort! Du hast nur einen Versuch.")
        view = QuizAnswerView(today, options)
        await channel.send(embed=embed, view=view)

        await channel.send("🕐 Viel Erfolg! Morgen gibt’s die nächste Frage ✨")

    # -------------------------------------------------
    # 📆 Manuelles Posten der Tagesfrage (Admin)
    # -------------------------------------------------
    @app_commands.command(name="quiz_post", description="Postet die heutige Quizfrage manuell im Giveaway-Kanal.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    @app_commands.checks.has_permissions(administrator=True)
    async def post_quiz(self, interaction: discord.Interaction):
        await self.post_daily_question()
        await interaction.response.send_message("✅ Quizfrage wurde manuell gestartet.", ephemeral=True)

    # -------------------------------------------------
    # 🧩 Neue Frage zum Pool hinzufügen
    # -------------------------------------------------
    @app_commands.command(name="quiz_addfrage", description="Fügt eine neue Quizfrage in den Fragenpool hinzu.")
    @app_commands.describe(
        frage="Die Quizfrage",
        option_a="Antwort A",
        option_b="Antwort B",
        option_c="Antwort C",
        korrekt="Welche Antwort ist korrekt? (A, B oder C)",
        loesung="Begründung oder Erklärung zur richtigen Antwort"
    )
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    @app_commands.checks.has_permissions(administrator=True)
    async def add_question(
        self,
        interaction: discord.Interaction,
        frage: str,
        option_a: str,
        option_b: str,
        option_c: str,
        korrekt: str,
        loesung: str
    ):
        korrekt = korrekt.strip().upper()
        if korrekt not in ["A", "B", "C"]:
            await interaction.response.send_message("❌ Bitte gib A, B oder C als richtige Antwort an!", ephemeral=True)
            return

        pool = load_json(POOL_FILE)
        new_id = str(len(pool) + 1)

        korrekte_option = {"A": option_a, "B": option_b, "C": option_c}[korrekt]
        pool[new_id] = {
            "frage": frage,
            "optionen": [option_a, option_b, option_c],
            "korrekt": korrekte_option,
            "loesung": loesung
        }
        save_json(POOL_FILE, pool)

        embed = discord.Embed(
            title="✅ Neue Frage hinzugefügt",
            description=f"**Frage:** {frage}\n\n"
                        f"A️⃣ {option_a}\nB️⃣ {option_b}\nC️⃣ {option_c}\n\n"
                        f"✅ **Korrekte Antwort:** {korrekte_option}\n"
                        f"🧠 **Begründung:** {loesung}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    # -------------------------------------------------
    # 🕛 Täglicher Gewinner wird automatisch gezogen
    # -------------------------------------------------
    @tasks.loop(minutes=1)
    async def daily_winner_task(self):
        now = datetime.now()
        if now.hour == 0 and now.minute == 0:  # 00:00 Uhr
            answers = load_json(ANSWERS_FILE)
            scores = load_json(SCORES_FILE)
            today = (now - timedelta(days=1)).strftime("%Y-%m-%d")

            if today not in answers:
                return  # Kein Quiz gestern

            day_answers = answers[today]
            correct_users = [uid for uid, info in day_answers.items() if info["richtig"]]

            channel = self.bot.get_channel(GIVEAWAY_CHANNEL_ID)
            if not channel:
                return

            if not correct_users:
                await channel.send(f"❌ Kein Gewinner für den {today} – niemand hatte die richtige Antwort!")
                return

            # 🎯 Tagesgewinner auslosen
            winner_id = random.choice(correct_users)
            winner = channel.guild.get_member(int(winner_id))
            await channel.send(f"🏆 **Tagesgewinner ({today})** ist {winner.mention}! Glückwunsch 🎉")

            # 🎁 Punkte zählen
            for uid in correct_users:
                scores[str(uid)] = scores.get(str(uid), 0) + 1
            save_json(SCORES_FILE, scores)

    # -------------------------------------------------
    # 🏁 Gesamtsieger am Ende des Quizzeitraums
    # -------------------------------------------------
    @app_commands.command(name="quiz_end", description="Beendet das Quiz und ermittelt den Gesamtsieger.")
    @app_commands.guilds(discord.Object(id=TEST_GUILD_ID))
    @app_commands.checks.has_permissions(administrator=True)
    async def end_quiz(self, interaction: discord.Interaction):
        scores = load_json(SCORES_FILE)
        if not scores:
            await interaction.response.send_message("❌ Keine Teilnehmer gefunden!", ephemeral=True)
            return

        max_points = max(scores.values())
        winners = [uid for uid, pts in scores.items() if pts == max_points]

        if len(winners) > 1:
            final_winner = random.choice(winners)
            tie = True
        else:
            final_winner = winners[0]
            tie = False

        guild = interaction.guild
        member = guild.get_member(int(final_winner))
        embed = discord.Embed(
            title="🏁 Quiz-Gesamtsieger",
            description=f"🎉 {member.mention} hat das Quiz gewonnen!\n\n"
                        f"Punkte: **{max_points}** {'(ausgelost bei Gleichstand)' if tie else ''}",
            color=discord.Color.green(),
        )
        await interaction.response.send_message(embed=embed)
        await guild.get_channel(GIVEAWAY_CHANNEL_ID).send(embed=embed)


# -------------------------------------------------
# 💬 Antwort-Buttons
# -------------------------------------------------
class QuizAnswerView(discord.ui.View):
    def __init__(self, date, options):
        super().__init__(timeout=None)
        for i, opt in enumerate(options):
            self.add_item(QuizAnswerButton(chr(65 + i), opt, date))


class QuizAnswerButton(discord.ui.Button):
    def __init__(self, label, option, date):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.option = option
        self.date = date

    async def callback(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        answers = load_json(ANSWERS_FILE)
        questions = load_json(QUESTIONS_FILE)
        today_data = answers.setdefault(self.date, {})

        if user_id in today_data:
            await interaction.response.send_message("⚠️ Du hast heute schon geantwortet!", ephemeral=True)
            return

        question_info = questions[self.date]
        correct_answer = question_info["korrekt"]
        loesung = question_info.get("loesung", "Keine Begründung angegeben.")
        is_correct = (self.option == correct_answer)

        today_data[user_id] = {"antwort": self.option, "richtig": is_correct}
        save_json(ANSWERS_FILE, answers)

        if is_correct:
            embed = discord.Embed(
                title="✅ Richtige Antwort!",
                description=f"Super gemacht!\n\n🧠 **Begründung:** {loesung}",
                color=discord.Color.green(),
            )
        else:
            embed = discord.Embed(
                title="❌ Sorry aber das war die falsche Antwort!",
                description=f"Die richtige Lösung war: **{correct_answer}**\n\n🧠 **Begründung:** {loesung}",
                color=discord.Color.red(),
            )

        await interaction.response.send_message(embed=embed, ephemeral=True)


# -------------------------------------------------
# ⚙️ Setup
# -------------------------------------------------
async def setup(bot):
    await bot.add_cog(DailyQuiz(bot))
