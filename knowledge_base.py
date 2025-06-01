"""
Wissensdatenbank-Manager für den Discord Bot
Lädt und verarbeitet PDF- und Text-Dateien aus dem data/ Ordner
"""

import os
import logging
import asyncio
from pathlib import Path
import fitz  # PyMuPDF für PDF-Verarbeitung
from typing import List, Dict

logger = logging.getLogger(__name__)

class KnowledgeBase:
    """
    Verwaltet die Wissensdatenbank aus PDF- und Text-Dateien
    """
    
    def __init__(self, data_folder: str = "user_knowledge"):
        self.data_folder = Path(data_folder)
        self.loaded_content: Dict[str, str] = {}
        self.supported_extensions = {'.txt', '.pdf', '.md'}
        
        # Data-Ordner erstellen falls nicht vorhanden
        self.data_folder.mkdir(exist_ok=True)
    
    async def load_knowledge_base(self):
        """
        Lädt alle unterstützten Dateien aus dem data/ Ordner asynchron
        """
        try:
            logger.info(f"📁 Durchsuche Ordner: {self.data_folder}")
            
            # Alle Dateien im data-Ordner finden
            files = [f for f in self.data_folder.rglob("*") 
                    if f.is_file() and f.suffix.lower() in self.supported_extensions]
            
            if not files:
                logger.warning(f"⚠️ Keine unterstützten Dateien in {self.data_folder} gefunden!")
                logger.info(f"Unterstützte Formate: {', '.join(self.supported_extensions)}")
                return
            
            logger.info(f"📄 {len(files)} Dateien gefunden")
            
            # Dateien parallel verarbeiten für bessere Performance
            tasks = [self._process_file(file) for file in files]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Ergebnisse auswerten
            successful_loads = 0
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"❌ Fehler beim Verarbeiten von {files[i].name}: {result}")
                else:
                    successful_loads += 1
            
            logger.info(f"✅ {successful_loads}/{len(files)} Dateien erfolgreich geladen")
            
        except Exception as e:
            logger.error(f"❌ Kritischer Fehler beim Laden der Wissensdatenbank: {e}")
            raise
    
    async def _process_file(self, file_path: Path) -> str:
        """
        Verarbeitet eine einzelne Datei basierend auf ihrem Typ
        """
        try:
            file_extension = file_path.suffix.lower()
            
            logger.info(f"📖 Verarbeite: {file_path.name}")
            
            if file_extension == '.pdf':
                content = await self._extract_pdf_content(file_path)
            elif file_extension in {'.txt', '.md'}:
                content = await self._extract_text_content(file_path)
            else:
                raise ValueError(f"Nicht unterstütztes Dateiformat: {file_extension}")
            
            # Leere Dateien abfangen
            if not content or not content.strip():
                logger.warning(f"⚠️ Datei {file_path.name} ist leer oder konnte nicht gelesen werden")
                return ""
            
            # Inhalt in Dictionary speichern
            self.loaded_content[str(file_path.name)] = content
            
            logger.info(f"✅ {file_path.name}: {len(content)} Zeichen geladen")
            return content
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Verarbeiten von {file_path.name}: {e}")
            raise
    
    async def _extract_pdf_content(self, file_path: Path) -> str:
        """
        Extrahiert Text aus PDF-Dateien mit PyMuPDF
        """
        try:
            # PDF-Verarbeitung in separatem Thread für bessere Performance
            content = await asyncio.get_event_loop().run_in_executor(
                None, self._extract_pdf_sync, file_path
            )
            return content
            
        except Exception as e:
            logger.error(f"PDF-Verarbeitungsfehler für {file_path.name}: {e}")
            raise
    
    def _extract_pdf_sync(self, file_path: Path) -> str:
        """
        Synchrone PDF-Textextraktion mit PyMuPDF
        """
        try:
            doc = fitz.open(str(file_path))
            text_content = []
            
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                page_text = page.get_text()
                
                if page_text.strip():  # Nur nicht-leere Seiten hinzufügen
                    text_content.append(f"--- Seite {page_num + 1} ---\n{page_text}")
            
            doc.close()
            
            return "\n\n".join(text_content)
            
        except Exception as e:
            raise Exception(f"PyMuPDF Fehler: {str(e)}")
    
    async def _extract_text_content(self, file_path: Path) -> str:
        """
        Lädt Text aus .txt und .md Dateien
        """
        try:
            # Verschiedene Encodings probieren
            encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
            
            for encoding in encodings:
                try:
                    content = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: file_path.read_text(encoding=encoding)
                    )
                    
                    logger.debug(f"Datei {file_path.name} mit {encoding} Encoding gelesen")
                    return content
                    
                except UnicodeDecodeError:
                    continue
            
            # Wenn alle Encodings fehlschlagen
            raise Exception("Datei konnte mit keinem unterstützten Encoding gelesen werden")
            
        except Exception as e:
            logger.error(f"Text-Verarbeitungsfehler für {file_path.name}: {e}")
            raise
    
    def get_combined_content(self) -> str:
        """
        Gibt den kombinierten Inhalt aller geladenen Dateien zurück
        """
        if not self.loaded_content:
            return ""
        
        combined_parts = []
        for filename, content in self.loaded_content.items():
            combined_parts.append(f"=== DATEI: {filename} ===\n{content}")
        
        return "\n\n".join(combined_parts)
    
    def get_loaded_files(self) -> List[str]:
        """
        Gibt eine Liste der erfolgreich geladenen Dateinamen zurück
        """
        return list(self.loaded_content.keys())
    
    def get_file_content(self, filename: str) -> str:
        """
        Gibt den Inhalt einer bestimmten Datei zurück
        """
        return self.loaded_content.get(filename, "")
    
    def get_content_stats(self) -> Dict[str, int]:
        """
        Gibt Statistiken über die geladenen Inhalte zurück
        """
        stats = {
            "total_files": len(self.loaded_content),
            "total_characters": sum(len(content) for content in self.loaded_content.values()),
            "average_file_size": 0
        }
        
        if stats["total_files"] > 0:
            stats["average_file_size"] = stats["total_characters"] // stats["total_files"]
        
        return stats
