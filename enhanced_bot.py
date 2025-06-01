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
import json
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

# Global variable for configuration
CONFIG_DETAILS = {}

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
    global knowledge_base, text_chunker, gemini_model, gemini_vision_model, CONFIG_DETAILS
    
    logger.info(f'🤖 Bot {bot.user} ist online!')
    
    # Setup Gemini API
    try:
        api_key = CONFIG_DETAILS.get('GEMINI_API_KEY')
        if not api_key:
            logger.error("❌ GEMINI_API_KEY not found in config.json or environment!")
            # Allow bot to start, but Gemini features will fail.
            # This is handled by subsequent checks for gemini_model.
            return # Or raise an error if Gemini is critical for startup
        
        genai.configure(api_key=api_key)
        gemini_model = genai.GenerativeModel('gemini-1.5-pro-latest')
        gemini_vision_model = genai.GenerativeModel('gemini-1.5-pro-latest')
        logger.info("✅ Gemini Pro + Vision configured using key from config.json.")
    except Exception as e:
        logger.error(f"Gemini API Fehler: {e}")
        # Bot will continue running, but Gemini features will not work.
        return
    
    # Wissensdatenbank laden
    try:
        # global CONFIG_DETAILS is already specified for on_ready
        knowledge_dir_from_config = CONFIG_DETAILS.get('KNOWLEDGE_BASE_DIR')

        if knowledge_dir_from_config:
            logger.info(f"📚 Using custom knowledge base directory: {knowledge_dir_from_config}")
            knowledge_base = KnowledgeBase(data_folder=knowledge_dir_from_config)
        else:
            logger.info("📚 Using default knowledge base directory 'user_knowledge/'.")
            knowledge_base = KnowledgeBase() # Uses the new default "user_knowledge"

        text_chunker = TextChunker() # Assuming TextChunker doesn't need path
        await knowledge_base.load_knowledge_base()
        
        # Update the log message to reflect the actual path used by knowledge_base instance
        file_count = len(knowledge_base.get_loaded_files())
        logger.info(f"✅ {file_count} Wissensdateien geladen aus '{knowledge_base.data_folder}'")
        
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
        
        prompt = f'''You are a helpful AI assistant. Analyze the provided image based on the user's question and the conversation context.

CONVERSATION CONTEXT:
{context}

USER'S QUESTION/REQUEST: {question}
{knowledge_context}

IMAGE ANALYSIS INSTRUCTIONS:
- Objectively describe the image.
- If the user asks a specific question about the image, answer it to the best of your ability.
- If custom knowledge is available and relevant, use it to inform your analysis.
- Maintain a helpful and neutral tone.

Respond clearly and concisely.
'''

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
                        "Hello! How can I assist you today?",
                        "Hi there! What can I help you with?",
                        "Greetings! I'm here to help. What's your question?"
                    ]
                else:
                    greeting_responses = [
                        "Hallo! Wie kann ich Ihnen heute behilflich sein?",
                        "Hallo! Womit kann ich Ihnen helfen?",
                        "Guten Tag! Ich bin hier, um zu helfen. Was ist Ihre Frage?"
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
                prompt = f'''You are a helpful AI assistant.

CONVERSATION CONTEXT:
{context}

AVAILABLE KNOWLEDGE (if any):
{combined_knowledge}

CURRENT QUESTION: {question}

INSTRUCTIONS:
- Answer the user's question directly and clearly.
- Use the provided knowledge if it's relevant to the question.
- If the question is outside your capabilities or knowledge, politely say so.
- Maintain a neutral and helpful tone.
- Respond in the language of the current question (English).'''
            else:
                prompt = f'''Sie sind ein hilfreicher KI-Assistent.

GESPRÄCHSKONTEXT:
{context}

VERFÜGBARES WISSEN (falls vorhanden):
{combined_knowledge}

AKTUELLE FRAGE: {question}

ANWEISUNGEN:
- Beantworten Sie die Frage des Benutzers direkt und klar.
- Nutzen Sie das bereitgestellte Wissen, wenn es für die Frage relevant ist.
- Wenn die Frage außerhalb Ihrer Fähigkeiten oder Ihres Wissens liegt, teilen Sie dies höflich mit.
- Behalten Sie einen neutralen und hilfsbereiten Ton bei.
- Antworten Sie in der Sprache der aktuellen Frage (Deutsch).'''

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
            stats = knowledge_base.get_content_stats() # This line might be problematic if file_count is 0, ensure kb_value logic handles this
            
            embed = discord.Embed(
                title="🤖 General AI Bot - Information",
                description="A helpful AI assistant powered by Google Gemini.",
                color=0x00ff00
            )
            
            # Wissensdatenbank field
            if knowledge_base and knowledge_base.get_loaded_files():
                file_count = len(knowledge_base.get_loaded_files())
                # stats already defined if knowledge_base is true, but might be empty if no files.
                # get_content_stats() should ideally handle empty content gracefully.
                stats = knowledge_base.get_content_stats() # Re-fetch or ensure it's correctly scoped
                kb_value = f"{file_count} Dateien geladen aus '{knowledge_base.data_folder}'.\n{stats.get('total_characters', 0):,} Zeichen.\n(Nutzerkonfigurierbar)"
            else:
                kb_value = "Keine Wissensdatenbank geladen.\n(Verzeichnis über GUI konfigurierbar)"
            embed.add_field(name="📚 Wissensdatenbank", value=kb_value, inline=True)
            
            embed.add_field(
                name="🧠 KI-Fähigkeiten",
                value="• Gemini 1.5 Pro (Text)\n• Gemini Vision (Bilder)\n• Kontext-Management",
                inline=True
            )
            
            embed.add_field(
                name="💡 Features", # Renamed from "Neue Features"
                value="• Kontext-Management\n• Bildanalyse (allgemein)\n• Unterstützung für @-Erwähnungen\n• Laden von benutzerdefiniertem Wissen",
                inline=False
            )
            
            embed.add_field(
                name="🔧 Befehle",
                value="`!frage [text]` - Stelle eine Frage\n`!info` - Bot Informationen\n`!themen` - Bot Fähigkeiten\n`@Bot + Nachricht` - Direkte Ansprache",
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
            title="📚 Bot Capabilities",
            description="Ich kann Ihnen bei Folgendem helfen:",
            color=0x0099ff
        )
        
        topics = [
           "💬 Beantwortung Ihrer Fragen (mit oder ohne benutzerdefinierte Wissensdatenbank).",
           "🖼️ Analyse von Bildern, die Sie hochladen.",
           "🗣️ Verstehen und Antworten in Deutsch und Englisch.",
           "🧠 Erinnerung an den Kontext unserer aktuellen Unterhaltung."
        ]
        
        for i, topic in enumerate(topics, 1):
            embed.add_field(
                name=f"{i}.", # Keeping the numbering for structure
                value=topic,
                inline=False
            )
        
        embed.set_footer(text="Erwähnen Sie mich mit @ oder verwenden Sie !frage.")
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
                        "Hello! I'm doing well, thank you. How can I help you?",
                        "Hi! Everything is fine. What can I do for you today?",
                        "Hello! I'm operational and ready to assist."
                    ]
                else:
                    greeting_responses = [
                        "Hallo! Mir geht es gut, danke. Wie kann ich Ihnen helfen?",
                        "Hi! Alles in Ordnung. Was kann ich heute für Sie tun?",
                        "Hallo! Ich bin einsatzbereit und stehe zur Verfügung."
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
            # Spracherkennung für die Antwortsprache (aus der Frage abgeleitet)
            is_english = any(word in question.lower() for word in ['what', 'how', 'when', 'why', 'where', 'can', 'could', 'would', 'should', 'do', 'does', 'did', 'will', 'are', 'is', 'the', 'and', 'or', 'but'])

            prompt = f'''You are a helpful AI assistant.

CONVERSATION CONTEXT:
{context}

AVAILABLE KNOWLEDGE (if any):
{combined_knowledge}

CURRENT QUESTION: {question}

INSTRUCTIONS:
- Answer the user's question directly and clearly.
- Use the provided knowledge if it's relevant to the question.
- If the question is outside your capabilities or knowledge, politely say so.
- Maintain a neutral and helpful tone.
- Respond in the language of the current question (Detected: {'English' if is_english else 'German'}).
- If the question involves links, state that you cannot open them but can discuss the text content if provided.'''

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

# Function to load configuration into the global CONFIG_DETAILS
def load_config_into_global():
    global CONFIG_DETAILS # Declare that this function modifies the global CONFIG_DETAILS

    loaded_config = {}
    try:
        with open('config.json', 'r') as f:
            loaded_config = json.load(f)
        CONFIG_DETAILS.update(loaded_config) # Update the global dictionary
    except FileNotFoundError:
        logger.error("❌ config.json not found! Please create it with your API keys and token. See README for format.")
        # CONFIG_DETAILS remains empty or partially updated
    except json.JSONDecodeError:
        logger.error("❌ Error decoding config.json! Please check its format.")
        # CONFIG_DETAILS remains empty or partially updated

if __name__ == "__main__":
    load_config_into_global() # Populate CONFIG_DETAILS

    # Now, only read from CONFIG_DETAILS in this scope
    discord_token = CONFIG_DETAILS.get('DISCORD_TOKEN')

    if not discord_token:
        logger.error("❌ DISCORD_TOKEN not found in config.json! The bot requires this to start.")
        exit(1) # Critical error, bot cannot start

    # GEMINI_API_KEY presence (or absence) is handled in on_ready.
    # If config.json was not found or was invalid, CONFIG_DETAILS might be empty
    # or lack GEMINI_API_KEY, which on_ready will handle.

    logger.info("🚀 Starting Bot...")
    bot.run(discord_token)