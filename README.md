# General Purpose AI Discord Bot

A flexible and user-friendly Discord bot powered by Google Gemini AI, designed to be run locally. It can be configured with your own API keys and an optional custom knowledge base.

## Features

- **Conversational AI**: Engage in natural conversations, answer questions, and assist with various tasks using Google Gemini.
- **Customizable Knowledge Base**: Enhance the bot's responses by providing your own knowledge base. Simply point the bot to a directory containing your `.txt`, `.pdf`, or `.md` files.
- **Image Analysis**: The bot can analyze and discuss images you upload in the chat when you mention it.
- **Context Management**: Remembers the flow of conversation for more relevant and coherent responses.
- **Multi-language Support**: Automatically detects and responds in German or English (can be extended).
- **User-Friendly GUI**: A simple desktop interface allows for easy configuration of API keys, knowledge base directory, and starting/stopping the bot.
- **Local Execution**: Runs on your own machine, giving you full control.

## Prerequisites

- Python 3.9+ (Python 3.11+ recommended)
- Discord Bot Token
- Google Gemini API Key

## Installation

1.  **Clone the Repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```
    (Replace `<repository_url>` and `<repository_directory>` with actual values)

2.  **Install Dependencies:**
    It's recommended to use a virtual environment.
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install discord.py google-generativeai PyMuPDF aiohttp
    ```

## Configuration and Running the Bot

The bot is configured and controlled using a simple graphical user interface (GUI).

1.  **Launch the GUI:**
    ```bash
    python bot_gui.py
    ```
    Ensure you are in the bot's root directory where `bot_gui.py` is located.

2.  **Configure Settings via GUI:**
    *   **Discord Token**: Enter your Discord bot token.
    *   **Gemini API Key**: Enter your Google Gemini API key.
    *   **Knowledge Base Directory (Optional)**:
        *   Click "Browse..." to select a folder containing your custom knowledge files (`.txt`, `.pdf`, `.md`).
        *   If left empty or not specified in `config.json` (e.g., by deleting the line or on first run before saving), the bot will default to looking for a folder named `user_knowledge/` in its root directory. This directory will be created if it doesn't exist. If this folder is empty, the bot will run without a custom knowledge base, relying solely on its general AI capabilities.
    *   **Save Configuration**: Click "Save Configuration". This will create/update a `config.json` file in the bot's directory with your settings.

3.  **Start/Stop the Bot:**
    *   Click "Start Bot" in the GUI to run the bot. Status and logs (including output from `enhanced_bot.py`) will appear in the GUI.
    *   Click "Stop Bot" to shut down the bot.

## Using the Bot on Discord

Once the bot is running and connected to your server:

-   **Ask Questions**:
    -   Type `!frage [your question]`
    -   Or simply mention the bot with your question (e.g., `@YourBotName what is the capital of France?`).
-   **Image Analysis**: Upload an image and mention the bot in the comment (e.g., `@YourBotName describe this image`).
-   **Bot Information**:
    -   `!info`: Shows information about the bot, including loaded knowledge base files (if any) and the directory being used.
-   **Bot Capabilities**:
    -   `!themen`: Lists the general capabilities of the bot.

## Preparing a Custom Knowledge Base (Optional)

1.  Create a folder on your computer (e.g., `my_bot_knowledge`, or use the default `user_knowledge/` which will be created in the bot's directory if not specified otherwise).
2.  Place your knowledge files into this folder. Supported formats are:
    *   `.txt` (plain text files, UTF-8 encoding recommended)
    *   `.pdf` (PDF documents)
    *   `.md` (Markdown files)
3.  In the GUI, set this folder as your "Knowledge Base Directory" and save the configuration.
4.  When the bot starts, it will attempt to load and process these files from the specified directory.

The bot will then use the information from these files to provide more specific and context-aware answers.

---
This project aims to provide a general, locally-runnable, and easily configurable AI Discord bot.
