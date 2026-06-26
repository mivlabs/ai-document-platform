from pypdf import PdfReader
from typing import List
import tiktoken

class PDFParserService:
    def __init__(self):
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
    
    def extract_text(self, file_path: str) -> str:
        """Извлекает текст из PDF."""
        reader = PdfReader(file_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text() + "\n"
        return text
    
    def chunk_text(self, text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Разбивает текст на чанки с перекрытием."""
        tokens = self.tokenizer.encode(text)
        chunks = []
        
        for i in range(0, len(tokens), chunk_size - overlap):
            chunk_tokens = tokens[i:i + chunk_size]
            chunk_text = self.tokenizer.decode(chunk_tokens)
            chunks.append(chunk_text)
        
        return chunks

pdf_parser = PDFParserService()