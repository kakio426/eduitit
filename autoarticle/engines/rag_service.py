

import os
import uuid
from .constants import CHROMA_PATH

class StyleRAGService:
    def __init__(self, persist_directory=None):
        self.persist_directory = persist_directory if persist_directory else CHROMA_PATH
        try:
            import chromadb
            from chromadb.utils import embedding_functions
        except ImportError:
            raise ImportError("ChromaDB is not installed. Please install it to use Style RAG.")
            
        self.client = chromadb.PersistentClient(path=self.persist_directory)
        
        # Use default local embedding (Sentence Transformers)
        self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        
        self.collection = self.client.get_or_create_collection(
            name="school_style_corrections",
            embedding_function=self.embedding_fn
        )

    def learn_style(self, original_text, corrected_text, tags=None):
        """
        Learns from a correction by storing the original/corrected pair.
        The 'document' for retrieval is the 'original_text' (what AI wrote),
        so when AI writes something similar again, we find how it was fixed.
        """
        # We store the "diff" logic context
        metadata = {
            "corrected": corrected_text,
            "tags": tags if tags else "general",
            "timestamp": str(os.path.getmtime(__file__)) # Placeholder timestamp
        }
        
        self.collection.add(
            documents=[original_text],
            metadatas=[metadata],
            ids=[str(uuid.uuid4())]
        )

    def retrieve_style_examples(self, query_text, n_results=3):
        """
        Finds past corrections relevant to the current text.
        Returns a list of dicts with 'original' and 'corrected'.
        """
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results
            )
            
            examples = []
            if results['documents']:
                for i in range(len(results['documents'][0])):
                    examples.append({
                        "original": results['documents'][0][i],
                        "corrected": results['metadatas'][0][i]['corrected'],
                        "tags": results['metadatas'][0][i]['tags']
                    })
            return examples
        except Exception:
            return [] # Return empty if db is empty or error
