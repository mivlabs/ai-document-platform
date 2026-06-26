from openai import AsyncOpenAI
from typing import List
import os

class EmbeddingsService:
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY not set in environment")
            self._client = AsyncOpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key
            )
        return self._client
    
    async def create_embeddings(self, texts: List[str]) -> List[List[float]]:
        embeddings = []
        batch_size = 100
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = await self.client.embeddings.create(
                model="openai/text-embedding-3-small",
                input=batch
            )
            batch_embeddings = [item.embedding for item in response.data]
            embeddings.extend(batch_embeddings)
        return embeddings

embeddings_service = EmbeddingsService()