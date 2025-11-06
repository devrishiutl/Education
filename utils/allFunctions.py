# from sentence_transformers import SentenceTransformer
# from sklearn.metrics.pairwise import cosine_similarity


async def paginate(collection, query, projection, page: int, page_size: int):
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
