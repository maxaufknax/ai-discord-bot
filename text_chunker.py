"""
Text-Chunking-System für optimale Token-Nutzung mit Gemini AI
Implementiert intelligente Textaufteilung und Relevanz-Bewertung
"""

import re
import logging
from typing import List, Tuple
import math

logger = logging.getLogger(__name__)

class TextChunker:
    """
    Intelligenter Text-Chunker für optimale AI-Prompt-Erstellung
    """
    
    def __init__(self, max_chunk_size: int = 2000):
        self.max_chunk_size = max_chunk_size
        # Vereinfachte Token-Schätzung: ~4 Zeichen = 1 Token (für deutsche Texte)
        self.chars_per_token = 4
    
    def estimate_tokens(self, text: str) -> int:
        """
        Schätzt die Anzahl der Tokens in einem Text
        Vereinfachte Methode: 4 Zeichen ≈ 1 Token für deutsche Texte
        """
        return len(text) // self.chars_per_token
    
    def split_into_chunks(self, text: str) -> List[str]:
        """
        Teilt einen Text in sinnvolle Chunks auf
        Versucht an Absätzen, Sätzen und Wörtern zu trennen
        """
        if not text or not text.strip():
            return []
        
        # Wenn Text kurz genug ist, direkt zurückgeben
        if len(text) <= self.max_chunk_size:
            return [text]
        
        chunks = []
        
        # Zunächst an doppelten Zeilenwechseln (Absätze) trennen
        paragraphs = text.split('\n\n')
        current_chunk = ""
        
        for paragraph in paragraphs:
            # Wenn Absatz + aktueller Chunk zu lang wäre
            if len(current_chunk) + len(paragraph) + 2 > self.max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""
                
                # Wenn ein einzelner Absatz zu lang ist, weiter aufteilen
                if len(paragraph) > self.max_chunk_size:
                    sub_chunks = self._split_long_paragraph(paragraph)
                    chunks.extend(sub_chunks)
                else:
                    current_chunk = paragraph
            else:
                if current_chunk:
                    current_chunk += "\n\n" + paragraph
                else:
                    current_chunk = paragraph
        
        # Letzten Chunk hinzufügen
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return [chunk for chunk in chunks if chunk.strip()]
    
    def _split_long_paragraph(self, paragraph: str) -> List[str]:
        """
        Teilt lange Absätze an Satzgrenzen auf
        """
        chunks = []
        
        # An Satzenden trennen (. ! ?)
        sentences = re.split(r'[.!?]+\s+', paragraph)
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            # Satzende-Zeichen wieder hinzufügen (außer beim letzten)
            if not sentence.endswith(('.', '!', '?')):
                sentence += '.'
            
            if len(current_chunk) + len(sentence) + 1 > self.max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = sentence
                else:
                    # Einzelner Satz ist zu lang - an Wörtern trennen
                    word_chunks = self._split_long_sentence(sentence)
                    chunks.extend(word_chunks)
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def _split_long_sentence(self, sentence: str) -> List[str]:
        """
        Teilt sehr lange Sätze an Wortgrenzen auf
        """
        words = sentence.split()
        chunks = []
        current_chunk = ""
        
        for word in words:
            if len(current_chunk) + len(word) + 1 > self.max_chunk_size:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = word
            else:
                if current_chunk:
                    current_chunk += " " + word
                else:
                    current_chunk = word
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
    
    def calculate_relevance_score(self, chunk: str, question: str) -> float:
        """
        Berechnet einen Relevanz-Score zwischen Chunk und Frage
        Basiert auf gemeinsamen Wörtern und Begriffen
        """
        # Text normalisieren (lowercase, Interpunktion entfernen)
        chunk_words = set(re.findall(r'\b\w+\b', chunk.lower()))
        question_words = set(re.findall(r'\b\w+\b', question.lower()))
        
        # Deutsche Stoppwörter ausschließen
        stop_words = {
            'der', 'die', 'das', 'und', 'oder', 'aber', 'ein', 'eine', 'einen',
            'ist', 'sind', 'war', 'waren', 'hat', 'haben', 'wird', 'werden',
            'ich', 'du', 'er', 'sie', 'es', 'wir', 'ihr', 'sie', 'mich', 'dich',
            'sich', 'uns', 'euch', 'ihm', 'ihr', 'ihnen', 'sein', 'seine', 'ihre',
            'mit', 'von', 'zu', 'bei', 'auf', 'in', 'an', 'für', 'über', 'unter',
            'durch', 'gegen', 'ohne', 'um', 'während', 'vor', 'nach', 'seit',
            'bis', 'trotz', 'wegen', 'statt', 'anstatt', 'außer', 'innerhalb'
        }
        
        chunk_words -= stop_words
        question_words -= stop_words
        
        if not question_words:
            return 0.0
        
        # Jaccard-Ähnlichkeit berechnen
        intersection = len(chunk_words & question_words)
        union = len(chunk_words | question_words)
        
        if union == 0:
            return 0.0
        
        jaccard_score = intersection / union
        
        # Bonus für direkte Übereinstimmungen in der ursprünglichen Frage
        question_lower = question.lower()
        direct_matches = sum(1 for word in question_words if word in chunk.lower())
        direct_bonus = direct_matches / len(question_words) * 0.3
        
        return min(jaccard_score + direct_bonus, 1.0)
    
    def get_relevant_chunks(self, text: str, question: str, max_tokens: int = 8000) -> List[str]:
        """
        Gibt die relevantesten Text-Chunks für eine Frage zurück
        Berücksichtigt Token-Limit und Relevanz-Scores
        """
        if not text or not question:
            return []
        
        # Text in Chunks aufteilen
        all_chunks = self.split_into_chunks(text)
        
        if not all_chunks:
            return []
        
        logger.info(f"📊 {len(all_chunks)} Text-Chunks erstellt")
        
        # Relevanz-Scores berechnen
        chunk_scores = []
        for chunk in all_chunks:
            score = self.calculate_relevance_score(chunk, question)
            chunk_scores.append((chunk, score))
        
        # Nach Relevanz sortieren (höchste zuerst)
        chunk_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Die besten Chunks bis zum Token-Limit sammeln
        selected_chunks = []
        total_tokens = 0
        
        for chunk, score in chunk_scores:
            chunk_tokens = self.estimate_tokens(chunk)
            
            # Prüfen ob Chunk noch ins Limit passt
            if total_tokens + chunk_tokens <= max_tokens:
                selected_chunks.append(chunk)
                total_tokens += chunk_tokens
                logger.debug(f"✅ Chunk hinzugefügt (Score: {score:.3f}, Tokens: {chunk_tokens})")
            else:
                logger.debug(f"⏭️ Chunk übersprungen - Token-Limit erreicht")
                break
        
        logger.info(f"🎯 {len(selected_chunks)} relevante Chunks ausgewählt ({total_tokens} geschätzte Tokens)")
        
        # Falls keine relevanten Chunks gefunden wurden, die ersten nehmen
        if not selected_chunks and all_chunks:
            logger.warning("⚠️ Keine relevanten Chunks gefunden, verwende erste Chunks")
            total_tokens = 0
            for chunk in all_chunks:
                chunk_tokens = self.estimate_tokens(chunk)
                if total_tokens + chunk_tokens <= max_tokens:
                    selected_chunks.append(chunk)
                    total_tokens += chunk_tokens
                else:
                    break
        
        return selected_chunks
    
    def get_chunk_stats(self, chunks: List[str]) -> dict:
        """
        Gibt Statistiken über eine Liste von Chunks zurück
        """
        if not chunks:
            return {"count": 0, "total_chars": 0, "total_tokens": 0, "avg_chunk_size": 0}
        
        total_chars = sum(len(chunk) for chunk in chunks)
        total_tokens = sum(self.estimate_tokens(chunk) for chunk in chunks)
        
        return {
            "count": len(chunks),
            "total_chars": total_chars,
            "total_tokens": total_tokens,
            "avg_chunk_size": total_chars // len(chunks),
            "avg_tokens_per_chunk": total_tokens // len(chunks)
        }
