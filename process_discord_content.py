#!/usr/bin/env python3
"""
Discord HTML Content Processor
Extrahiert relevanten Text aus Discord HTML-Dateien für die Wissensdatenbank
"""

import re
from bs4 import BeautifulSoup
from pathlib import Path
import html

def extract_text_from_discord_html(html_file):
    """Extrahiert Text-Inhalte aus Discord HTML-Dateien"""
    try:
        with open(html_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        soup = BeautifulSoup(content, 'html.parser')
        
        # Finde alle Nachrichten-Container
        messages = soup.find_all('div', class_='chatlog__message-container')
        
        extracted_content = []
        
        for message in messages:
            # Extrahiere Autor
            author_elem = message.find('span', class_='chatlog__author')
            author = author_elem.get_text().strip() if author_elem else "Unbekannt"
            
            # Extrahiere Nachrichteninhalt - verwende verschiedene Selektoren
            content_elem = message.find('div', class_='chatlog__content')
            if not content_elem:
                content_elem = message.find('span', class_='chatlog__markdown-preserve')
            
            if content_elem:
                # Entferne HTML-Tags aber behalte Text
                message_text = content_elem.get_text(separator=' ', strip=True)
                
                # Bereinige Text von Emoji-Codes und überflüssigen Leerzeichen
                message_text = re.sub(r'\s+', ' ', message_text)
                message_text = html.unescape(message_text)
                
                # Entferne leere Unicode-Zeichen
                message_text = re.sub(r'ㅤ', '', message_text)
                message_text = message_text.strip()
                
                # Filter kurze/unwichtige Nachrichten
                if len(message_text) > 15 and not message_text.startswith('http') and message_text != '':
                    extracted_content.append(f"{author}: {message_text}")
        
        return '\n\n'.join(extracted_content)
    
    except Exception as e:
        print(f"Fehler beim Verarbeiten von {html_file}: {e}")
        return ""

def main():
    """Verarbeitet alle Discord HTML-Dateien"""
    
    attached_folder = Path("attached_assets")
    data_folder = Path("data")
    
    # Stelle sicher, dass data/ Ordner existiert
    data_folder.mkdir(exist_ok=True)
    
    html_files = list(attached_folder.glob("*.html"))
    
    for html_file in html_files:
        print(f"Verarbeite: {html_file.name}")
        
        # Extrahiere Text-Inhalt
        content = extract_text_from_discord_html(html_file)
        
        if content:
            # Erstelle Ausgabedatei-Namen
            output_name = html_file.stem.replace("Mavenport - ", "").replace(" ", "_")
            output_name = re.sub(r'[^\w\-_]', '', output_name)
            output_file = data_folder / f"{output_name}.txt"
            
            # Speichere extrahierten Inhalt
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"# Discord Channel: {html_file.stem}\n\n")
                f.write(content)
            
            print(f"✅ Gespeichert: {output_file}")
        else:
            print(f"❌ Kein Inhalt extrahiert aus: {html_file.name}")

if __name__ == "__main__":
    main()