#!/usr/bin/env python3
"""
Erweiterte Discord Bot Version mit Kontext-Management und Bildanalyse
- Chatübergreifender Kontext
- Bildanalyse mit Gemini Vision
- Intelligente @-Erwähnungen
- Verbesserte Antwortqualität
"""

import discord
from discord.ext import commands
import google.generativeai as genai
import os
import logging
import asyncio
import aiohttp
import base64
from collections import defaultdict, deque
from datetime import datetime, timedelta
from knowledge_base import KnowledgeBase
from text_chunker import TextChunker

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Globale Variablen
knowledge_base = None
text_chunker = None
gemini_model = None
gemini_vision_model = None

# Kontext-Speicher: {channel_id: deque([(user_id, message, timestamp), ...])}
channel_context = defaultdict(lambda: deque(maxlen=20))
# User-spezifischer Kontext: {user_id: deque([message, ...])}
user_context = defaultdict(lambda: deque(maxlen=10))

# Konfiguration
CONTEXT_EXPIRE_MINUTES = 30
MAX_CONTEXT_MESSAGES = 15

@bot.event
async def on_ready():
    """Bot ist bereit"""
    global knowledge_base, text_chunker, gemini_model, gemini_vision_model
    
    logger.info(f'🤖 Bot {bot.user} ist online!')
    
    # Setup Gemini API
    try:
        api_key = os.getenv('GEMINI_API_KEY')
        if not api_key:
            logger.error("GEMINI_API_KEY nicht gefunden!")
            return
        
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel('gemini-1.5-pro-latest')
        gemini_vision_model = genai.GenerativeModel('gemini-1.5-pro-latest')
        logger.info("✅ Gemini Pro + Vision konfiguriert")
    except Exception as e:
        logger.error(f"Gemini API Fehler: {e}")
        return
    
    # Wissensdatenbank laden
    try:
        knowledge_base = KnowledgeBase()
        text_chunker = TextChunker()
        await knowledge_base.load_knowledge_base()
        
        file_count = len(knowledge_base.get_loaded_files())
        logger.info(f"✅ {file_count} Wissensdateien geladen")
        
        # Bot Status setzen
        await bot.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="@erwähnungen und Fragen"
            )
        )
        
    except Exception as e:
        logger.error(f"Wissensdatenbank Fehler: {e}")

def store_message_context(channel_id, user_id, message_content):
    """Speichert Nachricht im Kontext"""
    timestamp = datetime.now()
    
    # Channel-Kontext speichern
    channel_context[channel_id].append((user_id, message_content, timestamp))
    
    # User-Kontext speichern
    user_context[user_id].append((message_content, timestamp))

def get_relevant_context(channel_id, user_id, current_message):
    """Holt relevanten Kontext für bessere Antworten"""
    context_parts = []
    
    # Aktuelle Zeit
    now = datetime.now()
    expire_time = now - timedelta(minutes=CONTEXT_EXPIRE_MINUTES)
    
    # Channel-Kontext (letzte Nachrichten in diesem Channel)
    recent_channel_messages = []
    for uid, msg, timestamp in reversed(channel_context[channel_id]):
        if timestamp > expire_time:
            recent_channel_messages.append(f"User {uid}: {msg}")
        if len(recent_channel_messages) >= 5:
            break
    
    if recent_channel_messages:
        context_parts.append("AKTUELLER CHAT-KONTEXT:\n" + "\n".join(reversed(recent_channel_messages)))
    
    # User-spezifischer Kontext
    user_messages = []
    for msg, timestamp in reversed(user_context[user_id]):
        if timestamp > expire_time and msg != current_message:
            user_messages.append(msg)
        if len(user_messages) >= 3:
            break
    
    if user_messages:
        context_parts.append("VORHERIGE FRAGEN DIESES USERS:\n" + "\n".join(reversed(user_messages)))
    
    return "\n\n".join(context_parts)

async def download_image(url):
    """Lädt Bild herunter und konvertiert zu Base64"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    return base64.b64encode(image_data).decode('utf-8')
        return None
    except Exception as e:
        logger.error(f"Fehler beim Bilddownload: {e}")
        return None

async def analyze_image_with_context(image_data, question, context):
    """Analysiert Bild mit Kontext und Dropshipping-Wissen"""
    global gemini_vision_model, knowledge_base, text_chunker
    
    try:
        # Relevante Wissensinhalte für Bildanalyse
        relevant_chunks = []
        if knowledge_base and question:
            relevant_chunks = text_chunker.get_relevant_chunks(
                knowledge_base.get_combined_content(),
                question,
                max_tokens=6000
            )
        
        knowledge_context = ""
        if relevant_chunks:
            knowledge_context = f"\nRELEVANTES FACHWISSEN:\n{chr(10).join(relevant_chunks[:3])}"
        
        prompt = f"""Du bist Eddie von Mavenport - der direkte, kompromisslose Dropshipping-Experte. Du hast Millionen mit E-Commerce verdient und lehrst deine "Hustlers" in der Mavenport Community.

{context}

FRAGE/KONTEXT: {question}
{knowledge_context}

EDDIE'S PERSÖNLICHKEIT:
- Direkt und authentisch - sagst es wie es ist
- Manchmal hart wenn Leute dumme Sachen machen
- Nennst deine Community "Hustlers"
- Hast keine Geduld für faule Ausreden oder Quick-Money-Träumer
- Verwendest gelegentlich starke Sprache um Punkte zu machen
- Stolz auf deine Gray-Hat Methoden und kontroversen Strategien
- Erwartest dass Leute umsetzen was du lehrst

BILDANALYSE WIE EDDIE:
- Sag direkt was Scheiße ist und was gut funktioniert
- Bei Store-Screenshots: brutale UX/Design-Kritik mit klaren Fixes
- Bei Ad-Creatives: schonungslose Bewertung von Hook, Zielgruppe, CTA
- Bei Metriken: knallharte Interpretation - was skalieren, was killen
- Bei Produkten: ob es sich verkauft oder Müll ist
- Wenn es nicht E-Commerce/Dropshipping ist: "Das ist nicht mein Ding, ich mache Dropshipping und Facebook Ads"

Antworte wie Eddie - direkt, ohne Beschönigung, mit echter Expertise. Verwende "Hustler" wenn du die Person ansprichst."""

        # Erstelle Bild-Teil für Gemini
        image_part = {
            "mime_type": "image/jpeg",
            "data": image_data
        }
        
        response = gemini_vision_model.generate_content([prompt, image_part])
        
        if response and response.text:
            return response.text
        return "Entschuldigung, ich konnte das Bild nicht analysieren."
        
    except Exception as e:
        logger.error(f"Bildanalyse Fehler: {e}")
        return "Fehler bei der Bildanalyse. Bitte versuche es erneut."

@bot.command(name='frage')
async def frage_command(ctx, *, question: str = None):
    """Beantwortet Fragen mit Kontext"""
    if not question:
        await ctx.send("❓ Bitte stelle eine Frage! Beispiel: `!frage Wie teste ich Facebook Ads?`")
        return
    
    # Kontext speichern
    store_message_context(ctx.channel.id, ctx.author.id, question)
    
    await handle_question_with_context(ctx, question)

async def handle_question_with_context(ctx, question):
    """Verarbeitet Frage mit vollständigem Kontext"""
    global knowledge_base, text_chunker, gemini_model
    
    if not knowledge_base or not gemini_model:
        await ctx.send("❌ Bot nicht vollständig initialisiert.")
        return
    
    logger.info(f"Frage mit Kontext von {ctx.author}: {question}")
    
    async with ctx.typing():
        try:
            # Kontext abrufen
            context = get_relevant_context(ctx.channel.id, ctx.author.id, question)
            
            # Relevante Wissensinhalte finden
            knowledge_content = knowledge_base.get_combined_content()
            relevant_chunks = text_chunker.get_relevant_chunks(
                knowledge_content,
                question + " " + context,  # Kontext in Suche einbeziehen
                max_tokens=7000
            )
            
            if not relevant_chunks:
                await ctx.send("🔍 Keine relevanten Informationen gefunden.")
                return
            
            # Prüfe ob es eine einfache Begrüßung ist
            greeting_words = ['hallo', 'hi', 'hey', 'guten tag', 'moin', 'servus', 'wie geht', 'wie läuft']
            is_greeting = any(word in question.lower() for word in greeting_words) and len(question.split()) <= 6
            
            if is_greeting:
                # Spracherkennung für Begrüßung
                is_english = any(word in question.lower() for word in ['hello', 'hi', 'hey', 'how are you'])
                
                if is_english:
                    greeting_responses = [
                        "What's up! Eddie here. What do you need help with? I teach dropshipping, Facebook ads, and how to actually make money online.",
                        "Hey there, hustler. I'm here to help you scale your business. What's your question about e-commerce?",
                        "Hello. I'm Eddie from Mavenport. Let's talk business - what do you want to know about dropshipping or Facebook ads?"
                    ]
                else:
                    greeting_responses = [
                        "Was geht ab! Eddie hier. Womit kann ich dir helfen? Ich lehre Dropshipping, Facebook Ads und wie man richtig Geld online verdient.",
                        "Hey Hustler. Ich bin hier um dir beim Skalieren zu helfen. Was ist deine Frage zum E-Commerce?",
                        "Hallo. Ich bin Eddie von Mavenport. Lass uns über Business reden - was willst du über Dropshipping oder Facebook Ads wissen?"
                    ]
                
                import random
                response_text = random.choice(greeting_responses)
                await send_long_message(ctx, response_text)
                return
            
            # Erweiterten Prompt für fachliche Fragen erstellen
            combined_knowledge = '\n\n'.join(relevant_chunks)
            
            # Spracherkennung
            is_english = any(word in question.lower() for word in ['what', 'how', 'when', 'why', 'where', 'can', 'could', 'would', 'should', 'do', 'does', 'did', 'will', 'are', 'is', 'the', 'and', 'or', 'but'])
            
            if is_english:
                prompt = f"""You are Eddie from Mavenport - the straight-talking, no-bullshit dropshipping expert who built one of the most successful e-commerce communities and made millions in dropshipping.

EDDIE'S PERSONALITY:
- Direct and authentic - you tell it like it is
- Sometimes blunt or harsh when people ask stupid questions or don't read your materials
- Call your community members "hustlers"
- Zero patience for people who want quick money without work
- Occasionally use strong language when making a point
- Proud of your gray-hat methods and controversial strategies
- Expect people to actually implement what you teach
- Call out lazy thinking and bad strategies

CONVERSATION CONTEXT:
{context}

YOUR MAVENPORT KNOWLEDGE:
{combined_knowledge}

CURRENT QUESTION: {question}

INSTRUCTIONS:
- Respond like Eddie would - be direct, actionable, don't sugarcoat
- If someone asks something basic covered in your materials, call them out for not reading
- If it's outside dropshipping/e-commerce, tell them that's not your thing
- Give real, practical advice based on your actual experience
- Use "hustler" when addressing the person
- If they're asking good questions, be helpful but still direct"""
            else:
                prompt = f"""Du bist Eddie von Mavenport - der direkte, kompromisslose Dropshipping-Experte der eine der erfolgreichsten E-Commerce Communities aufgebaut und Millionen mit Dropshipping verdient hat.

EDDIE'S PERSÖNLICHKEIT:
- Direkt und authentisch - sagst es wie es ist
- Manchmal hart oder rau wenn Leute dumme Fragen stellen oder deine Materialien nicht lesen
- Nennst deine Community-Mitglieder "Hustlers"
- Null Geduld für Leute die schnelles Geld ohne Arbeit wollen
- Verwendest gelegentlich starke Sprache um Punkte zu machen
- Stolz auf deine Gray-Hat Methoden und kontroversen Strategien
- Erwartest dass Leute tatsächlich umsetzen was du lehrst
- Konfrontierst faules Denken und schlechte Strategien

GESPRÄCHSKONTEXT:
{context}

DEIN MAVENPORT WISSEN:
{combined_knowledge}

AKTUELLE FRAGE: {question}

ANWEISUNGEN:
- Antworte wie Eddie es würde - direkt, umsetzbar, ohne Beschönigung
- Wenn jemand etwas Grundlegendes fragt was in deinen Materialien steht, konfrontiere sie damit
- Wenn es außerhalb Dropshipping/E-Commerce liegt, sag dass das nicht dein Ding ist
- Gib echte, praktische Ratschläge basierend auf deiner tatsächlichen Erfahrung
- Verwende "Hustler" wenn du die Person ansprichst
- Wenn sie gute Fragen stellen, sei hilfreich aber trotzdem direkt"""

            # Gemini API Anfrage
            response = gemini_model.generate_content(prompt)
            
            if response and response.text:
                await send_long_message(ctx, response.text)
            else:
                await ctx.send("❌ Keine Antwort von der KI erhalten.")
                
        except Exception as e:
            logger.error(f"Fehler bei kontextbasierter Frage: {e}")
            await ctx.send("❌ Fehler bei der Verarbeitung deiner Frage.")

@bot.command(name='info')
async def info_command(ctx):
    """Zeigt erweiterte Bot-Informationen"""
    global knowledge_base
    
    try:
        if knowledge_base:
            files = knowledge_base.get_loaded_files()
            file_count = len(files)
            stats = knowledge_base.get_content_stats()
            
            embed = discord.Embed(
                title="🤖 Eddie from Mavenport - Bot Information",
                description="The straight-talking dropshipping expert teaching real E-Commerce strategies",
                color=0x00ff00
            )
            
            embed.add_field(
                name="📚 Wissensdatenbank",
                value=f"{file_count} Dateien\n{stats.get('total_characters', 0):,} Zeichen",
                inline=True
            )
            
            embed.add_field(
                name="🧠 KI-Fähigkeiten",
                value="• Gemini 1.5 Pro (Text)\n• Gemini Vision (Bilder)\n• Kontext-Management",
                inline=True
            )
            
            embed.add_field(
                name="💡 Neue Features",
                value="• Chatübergreifender Kontext\n• Bildanalyse\n• @-Erwähnungen\n• Intelligente Antworten",
                inline=False
            )
            
            embed.add_field(
                name="🔧 Befehle",
                value="`!frage [text]` - Frage mit Kontext\n`!themen` - Verfügbare Themen\n`@Bot + Nachricht` - Direktansprache",
                inline=False
            )
            
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Wissensdatenbank nicht geladen.")
            
    except Exception as e:
        logger.error(f"Info-Command Fehler: {e}")
        await ctx.send("❌ Fehler beim Abrufen der Informationen.")

@bot.command(name='themen')
async def themen_command(ctx):
    """Zeigt verfügbare Wissensthemen"""
    try:
        embed = discord.Embed(
            title="📚 Verfügbare Wissensthemen",
            description="Ich kann dir bei folgenden Themen helfen:",
            color=0x0099ff
        )
        
        topics = [
            "📈 **Facebook Ads Optimierung**\nTesting, Scaling, Metriken, ROAS",
            "🛍️ **Dropshipping Strategien**\nProduktrecherche, Supplier, Profit-Margins",
            "🏪 **Shopify Store Setup**\nThemes, Metafields, Conversion-Optimierung", 
            "🎯 **Content Creation**\nVideo-Ads, Copywriting, Creative-Strategien",
            "📊 **Performance Tracking**\nUTM-Parameter, Analytics, KPI-Monitoring",
            "💰 **Scaling Strategien**\nBudget-Management, Account-Struktur, CBO",
            "🖼️ **Bildanalyse**\nStore-Screenshots, Ad-Creatives, Metriken",
            "🔧 **Tools & Resources**\nSoftware, Extensions, Automatisierung"
        ]
        
        for i, topic in enumerate(topics, 1):
            embed.add_field(
                name=f"{i}.",
                value=topic,
                inline=False
            )
        
        embed.set_footer(text="Erwähne mich mit @ oder stelle direkte Fragen!")
        await ctx.send(embed=embed)
        
    except Exception as e:
        logger.error(f"Themen-Command Fehler: {e}")
        await ctx.send("❌ Fehler beim Laden der Themen.")

@bot.event
async def on_message(message):
    """Erweiterte Nachrichtenverarbeitung mit Kontext und Bildanalyse"""
    # Ignoriere Bot-Nachrichten
    if message.author.bot:
        return
    
    # Verarbeite Commands zuerst
    await bot.process_commands(message)
    
    # Speichere alle Nachrichten für Kontext (außer Commands)
    if not message.content.startswith('!'):
        store_message_context(message.channel.id, message.author.id, message.content)
    
    # Prüfe auf Bot-Erwähnung oder Fragen
    bot_mentioned = bot.user.mentioned_in(message)
    is_question = any(word in message.content.lower() for word in 
                     ['?', 'wie', 'was', 'wann', 'wo', 'warum', 'welche', 'kann', 'soll', 'hilfe'])
    
    # Verarbeite Bilder wenn Bot erwähnt wurde
    if bot_mentioned and message.attachments:
        await handle_image_analysis(message)
        return
    
    # Verarbeite Text-Fragen (einschließlich Links)
    if (bot_mentioned or is_question) and len(message.content.strip()) > 5 and not message.content.startswith('!'):
        question = message.content.replace(f'<@{bot.user.id}>', '').strip()
        
        # Prüfe auf Links in der Nachricht
        import re
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', question)
        if urls:
            # Füge Kontext über Links hinzu
            question = f"{question}\n\nHinweis: Die Nachricht enthält Links, die ich nicht direkt öffnen kann."
        
        await handle_auto_question_with_context(message, question)

async def handle_image_analysis(message):
    """Verarbeitet Bildanalyse mit Kontext"""
    try:
        # Prüfe ob Bilder vorhanden sind
        images = [att for att in message.attachments if att.content_type and att.content_type.startswith('image/')]
        
        if not images:
            await message.reply("Ich sehe keine Bilder zum Analysieren. Lade ein Bild hoch und erwähne mich!")
            return
        
        async with message.channel.typing():
            # Analysiere erstes Bild
            image_url = images[0].url
            image_data = await download_image(image_url)
            
            if not image_data:
                await message.reply("❌ Konnte das Bild nicht laden. Bitte versuche es erneut.")
                return
            
            # Kontext für Bildanalyse
            context = get_relevant_context(message.channel.id, message.author.id, message.content)
            question_context = message.content.replace(f'<@{bot.user.id}>', '').strip()
            
            if not question_context:
                question_context = "Analysiere dieses Bild im E-Commerce/Dropshipping Kontext"
            
            # Bildanalyse durchführen
            analysis = await analyze_image_with_context(image_data, question_context, context)
            
            # Antwort senden
            await send_long_message_reply(message, f"🖼️ **Bildanalyse:**\n\n{analysis}")
            
    except Exception as e:
        logger.error(f"Bildanalyse Fehler: {e}")
        await message.reply("❌ Fehler bei der Bildanalyse. Bitte versuche es erneut.")

async def handle_auto_question_with_context(message, question):
    """Behandelt automatisch erkannte Fragen mit Kontext"""
    global knowledge_base, text_chunker, gemini_model
    
    if not knowledge_base or not gemini_model:
        return
    
    logger.info(f"Auto-Frage mit Kontext: {question}")
    
    try:
        async with message.channel.typing():
            # Kontext abrufen
            context = get_relevant_context(message.channel.id, message.author.id, question)
            
            # Relevante Wissensinhalte finden
            knowledge_content = knowledge_base.get_combined_content()
            relevant_chunks = text_chunker.get_relevant_chunks(
                knowledge_content,
                question + " " + context,
                max_tokens=7000
            )
            
            # Prüfe ob es eine einfache Begrüßung ist
            greeting_words = ['hallo', 'hi', 'hey', 'guten tag', 'moin', 'servus', 'wie geht', 'wie läuft']
            is_greeting = any(word in question.lower() for word in greeting_words) and len(question.split()) <= 6
            
            if is_greeting:
                # Spracherkennung für Begrüßung
                is_english = any(word in question.lower() for word in ['hello', 'hi', 'hey', 'how are you'])
                
                if is_english:
                    greeting_responses = [
                        "Hello! I'm doing well, thank you for asking. How can I help you with e-commerce topics?",
                        "Hi! Everything's running smoothly. What questions do you have about dropshipping, Facebook ads, or store optimization?",
                        "Hello! I'm doing great. What can I assist you with in the e-commerce space?"
                    ]
                else:
                    greeting_responses = [
                        "Hallo! Mir geht es gut, danke der Nachfrage. Womit kann ich dir im E-Commerce Bereich helfen?",
                        "Hi! Alles läuft gut bei mir. Was für eine Frage hast du zu Dropshipping, Facebook Ads oder Store-Optimierung?",
                        "Hallo! Mir geht es bestens. Lass hören - wobei kann ich dir behilflich sein?"
                    ]
                
                import random
                response_text = random.choice(greeting_responses)
                await send_long_message_reply(message, response_text)
                return
            
            if not relevant_chunks:
                await message.reply("Keine relevanten Informationen gefunden. Versuche es mit einer spezifischeren Frage.")
                return
            
            # Prompt mit professioneller, authentischer Persönlichkeit
            combined_knowledge = '\n\n'.join(relevant_chunks)
            prompt = f"""Du bist Freedom, ein professioneller E-Commerce Experte mit authentischer, direkter Persönlichkeit. Du bist kompetent, hilfsbereit und ehrlich.

PERSÖNLICHKEIT:
- Professionell und sachkundig im E-Commerce Bereich
- Authentisch und direkt, ohne unnötige Floskeln
- Hilfsbereit und geduldig bei allen Fragen
- Erinnerst dich an vorherige Gespräche
- Keine Emojis oder übertriebene Ausdrücke
- Fokussiert auf praktische, umsetzbare Lösungen
- Ehrlich über Chancen und Risiken

GESPRÄCHSKONTEXT:
{context}

EXPERTENWISSEN:
{combined_knowledge}

AKTUELLE FRAGE: {question}

ANWEISUNGEN:
- Erkenne die Sprache der Frage und antworte in derselben Sprache (Deutsch oder Englisch)
- Verwende einen professionellen, klaren Stil ohne Emojis
- Gehe spezifisch auf die gestellte Frage ein
- Berücksichtige den Gesprächskontext vollständig
- Wenn die Frage nicht E-Commerce bezogen ist: erkläre höflich, dass du auf E-Commerce spezialisiert bist
- Bei Krypto/Trading-Fragen: erkläre, dass dein Expertise-Bereich E-Commerce und Dropshipping ist
- Gib konkrete, praktische Handlungsempfehlungen
- Bei Links oder externen Inhalten: erkläre was du siehst/nicht siehst"""

            # Gemini API Anfrage
            response = gemini_model.generate_content(prompt)
            
            if response and response.text:
                await send_long_message_reply(message, response.text)
                
    except Exception as e:
        logger.error(f"Auto-Frage Kontext Fehler: {e}")

async def send_long_message(ctx, text):
    """Sendet lange Nachrichten in Chunks"""
    if len(text) <= 1900:
        await ctx.send(text)
        return
    
    chunks = []
    current = ""
    
    for sentence in text.split('. '):
        if len(current + sentence + '. ') <= 1900:
            current += sentence + '. '
        else:
            if current:
                chunks.append(current.strip())
            current = sentence + '. '
    
    if current:
        chunks.append(current.strip())
    
    for chunk in chunks:
        await ctx.send(chunk)
        await asyncio.sleep(1)

async def send_long_message_reply(message, text):
    """Sendet lange Nachrichten als Reply in Chunks"""
    if len(text) <= 1900:
        await message.reply(text)
        return
    
    chunks = []
    current = ""
    
    for sentence in text.split('. '):
        if len(current + sentence + '. ') <= 1900:
            current += sentence + '. '
        else:
            if current:
                chunks.append(current.strip())
            current = sentence + '. '
    
    if current:
        chunks.append(current.strip())
    
    if chunks:
        await message.reply(chunks[0])
        for chunk in chunks[1:]:
            await message.channel.send(chunk)
            await asyncio.sleep(1)

if __name__ == "__main__":
    # Discord Token prüfen
    token = os.getenv('DISCORD_TOKEN')
    if not token:
        logger.error("❌ DISCORD_TOKEN nicht gefunden!")
        exit(1)
    
    logger.info("🚀 Starte Enhanced Bot mit Kontext & Vision...")
    bot.run(token)