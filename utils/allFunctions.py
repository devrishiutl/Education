from sentence_transformers import SentenceTransformer  
from sklearn.metrics.pairwise import cosine_similarity

class AllFunctions:
    def __init__(self):
        self.model = SentenceTransformer('BAAI/bge-m3')

    def get_embedding(self, text):
        """Get embedding from OpenAI API with caching"""
        text = text.lower()
        embedding = self.model.encode([text], normalize_embeddings=True)[0]
        return embedding.tolist()  # Convert numpy array to list    

    def semantic_similarity(self, embedding1, embedding2):
        """Returns semantic similarity between two titles (0 to 1)"""
        return float(cosine_similarity([embedding1], [embedding2])[0][0])
    
    def get_similarity_score(self, text1, text2):
        embedding1 = self.get_embedding(text1)
        embedding2 = self.get_embedding(text2)
        return self.semantic_similarity(embedding1, embedding2)
    
    async def paginate(self, collection, query, projection, page: int, page_size: int):
        skip = (page - 1) * page_size
        cursor = collection.find(query, projection).skip(skip).limit(page_size)

        results = []
        async for doc in cursor:
            results.append(doc)

        total = await collection.count_documents(query)
        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "results": results
        }