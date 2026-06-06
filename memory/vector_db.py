import os
from typing import List, Dict, Any
from config.logging import logger
from config.config import config

try:
    import chromadb
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

class VectorMemory:
    def __init__(self):
        self.enabled = CHROMA_AVAILABLE
        if not self.enabled:
            logger.warning("ChromaDB not installed. Vector memory disabled.")
            return

        # Initialize local persistent Chroma client
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        db_path = os.path.join(project_root, "chroma_db")
        os.makedirs(db_path, exist_ok=True)
        
        try:
            self.client = chromadb.PersistentClient(path=db_path)
            # Default embedding function is all-MiniLM-L6-v2 ONNX
            self.collection = self.client.get_or_create_collection(name="aurora_skills")
            logger.info(f"VectorMemory initialized at {db_path} with {self.collection.count()} skills.")
        except Exception as e:
            logger.error(f"Failed to initialize ChromaDB: {e}")
            self.enabled = False

    def teach_skill(self, skill_name: str, instructions: str, tags: List[str] = None) -> bool:
        """Stores a new skill instruction into the vector database."""
        if not self.enabled:
            return False
            
        try:
            # Delete if exists to update
            existing = self.collection.get(ids=[skill_name])
            if existing and existing['ids']:
                self.collection.delete(ids=[skill_name])
                
            metadata = {"type": "skill"}
            if tags:
                metadata["tags"] = ",".join(tags)
                
            # Document is the actual instructions. The query will semantically match the document content.
            # We prefix the document with the skill name to ensure exact matches score highly.
            document = f"Skill: {skill_name}\nInstructions: {instructions}"
            
            self.collection.add(
                documents=[document],
                metadatas=[metadata],
                ids=[skill_name]
            )
            logger.info(f"Taught new skill to VectorMemory: '{skill_name}'")
            return True
        except Exception as e:
            logger.error(f"Failed to teach skill '{skill_name}': {e}")
            return False

    def search_skills(self, query: str, n_results: int = 2) -> List[str]:
        """Queries the vector database for skills related to the query."""
        if not self.enabled:
            return []
            
        try:
            if self.collection.count() == 0:
                return []
                
            n = min(n_results, self.collection.count())
            results = self.collection.query(
                query_texts=[query],
                n_results=n
            )
            
            documents = results.get('documents', [[]])[0]
            distances = results.get('distances', [[]])[0]
            
            valid_skills = []
            for doc, dist in zip(documents, distances):
                # Using default L2 distance. Lower is better. Typical matches are < 1.5.
                if dist < 1.7: 
                    valid_skills.append(doc)
                    
            return valid_skills
        except Exception as e:
            logger.error(f"Failed to search skills for '{query}': {e}")
            return []

vector_memory = VectorMemory()
