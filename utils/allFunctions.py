from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


class AllFunctions:
    def __init__(self):
        self.model = SentenceTransformer("BAAI/bge-m3")

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
        """
        Improved pagination using index-based sort + skip (minimal overhead).
        Works with existing page/page_size params, but performs faster
        due to indexed sorting and selective counting.
        """
        # Ensure deterministic order — must use index on this field
        sort_field = "_id"

        # Create the base cursor with indexed sort
        cursor = (
            collection.find(query, projection)
            .sort(sort_field, 1)  # ensure index usage
            .skip((page - 1) * page_size)
            .limit(page_size)
        )

        # Fetch the page
        results = [doc async for doc in cursor]

        # Use lightweight count — avoids full scan if no filters
        if query:
            total = await collection.count_documents(query)
        else:
            # estimated count avoids scanning the full collection
            total = await collection.estimated_document_count()

        return {
            "page": page,
            "page_size": page_size,
            "total": total,
            "results": results,
        }
