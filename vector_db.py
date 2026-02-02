
from qdrant_client import QdrantClient
from qdrant_client.http import models
import uuid

import numpy as np

COLLECTION_NAME = "music_collection"
VECTOR_SIZE = 200

def get_client():
    # Connect to Qdrant server (Docker)
    # Fails if server is not running, which helps debug Docker issues
    try:
        return QdrantClient(host="localhost", port=6333)
    except:
        print("Could not connect to Qdrant on localhost:6333. Falling back to local file.")
        return QdrantClient(path="./qdrant_data")

def init_collection(client):
    collections = client.get_collections()
    exists = any(c.name == COLLECTION_NAME for c in collections.collections)
    
    if not exists:
        print(f"Creating collection {COLLECTION_NAME}...")
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=models.VectorParams(
                size=VECTOR_SIZE,
                distance=models.Distance.COSINE
            )
        )
        print("Collection created.")
    else:
        print(f"Collection {COLLECTION_NAME} already exists.")

def upload_track(client, filename, embedding):
    """Uploads a single track's embedding to Qdrant."""
    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, filename))
    
    client.upsert(
        collection_name=COLLECTION_NAME,
        points=[
            models.PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload={"filename": filename}
            )
        ]
    )

def upload_batch(client, items):
    """
    Uploads a batch of items to Qdrant.
    Items can be:
    1. (filename, embedding) -> Legacy/Full track
    2. (id, vector, payload) -> Explicit full point control
    """
    points = []
    
    for item in items:
        if len(item) == 2:
            # Legacy: (filename, embedding)
            filename, embedding = item
            point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, filename))
            points.append(models.PointStruct(
                id=point_id,
                vector=embedding.tolist(),
                payload={"filename": filename, "type": "full"}
            ))
        elif len(item) == 3:
            # New: (id, vector, payload)
            pid, vector, payload = item
            points.append(models.PointStruct(
                id=pid,
                vector=vector.tolist(),
                payload=payload
            ))

    client.upsert(collection_name=COLLECTION_NAME, points=points)

def get_collection_info(client):
    try:
        return client.get_collection(COLLECTION_NAME)
    except:
        return None

def get_random_tracks(client, limit=1, avoid_ids=None):
    """
    Retrieves random tracks by generating a random vector and searching for nearest neighbors.
    This provides a good approximation of random sampling in the vector space.
    """
    # Generate a random vector of the same dimension
    random_vector = np.random.rand(VECTOR_SIZE).tolist()
    
    # Filter to exclude played songs (avoid_ids)
    query_filter = None
    if avoid_ids:
        query_filter = models.Filter(
            must_not=[
                models.FieldCondition(
                    key="id",
                    match=models.MatchAny(any=list(avoid_ids))
                )
            ]
        )

    # Use query_points which is more universally available on older/local clients
    # search() helper might be missing on some versions
    try:
        results = client.query_points(
            collection_name=COLLECTION_NAME,
            query=random_vector,
            query_filter=query_filter,
            limit=limit,
            with_vectors=True,
            with_payload=True
        ).points
    except Exception as e:
        print(f"Random Track Search fallback error: {e}")
        # Extreme fallback: Scroll
        return []

    return [
        {
            "id": point.id,
            "filename": point.payload["filename"],
            "score": point.score,
            "vector": point.vector
        }
        for point in results
    ]

def get_track_by_id(client, point_id):
    points = client.retrieve(
        collection_name=COLLECTION_NAME,
        ids=[point_id],
        with_vectors=True 
    )
    if points:
        p = points[0]
        return {
            "id": p.id,
            "filename": p.payload["filename"],
            "vector": p.vector
        }
    return None

def recommend_tracks(client, positive_vectors, negative_vectors=None, avoid_ids=None, limit=1):
    """
    Uses Qdrant's recommendation API to find tracks similar to positive_vectors
    and dissimilar to negative_vectors.
    """
    if negative_vectors is None:
        negative_vectors = []
    
    # Filter to exclude played songs (avoid_ids)
    query_filter = None
    if avoid_ids:
        query_filter = models.Filter(
            must_not=[
                models.FieldCondition(
                    key="id",
                    match=models.MatchAny(any=list(avoid_ids)) # Ensure list
                )
            ]
        )
    # If we have a single positive vector and no negatives, this is a Search query (Nearest Neighbor)
    if not negative_vectors and len(positive_vectors) == 1 and isinstance(positive_vectors[0], list):
        # Normalize just in case? Qdrant handles it usually.
        try:
            results = client.query_points(
                collection_name=COLLECTION_NAME,
                query=positive_vectors[0],
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
                with_vectors=True
            ).points
            # Normalize output
            return [
                {
                    "id": point.id,
                    "filename": point.payload["filename"],
                    "score": point.score,
                    "vector": point.vector
                }
                for point in results
            ]
        except Exception as e:
            print(f"Search failed: {e}")
            # Fall through to try other methods if needed, or return empty
            pass

    # For complex queries (Negatives or Multiple Positives), use Recommend
    try:
        # Check if client has recommend method
        if hasattr(client, 'recommend'):
             results = client.recommend(
                collection_name=COLLECTION_NAME,
                positive=positive_vectors,
                negative=negative_vectors,
                query_filter=query_filter,
                limit=limit,
                with_vectors=True,
                with_payload=True
            )
        else:
            # Fallback for clients without recommend (e.g. very old or weird local mode)
            # We try query_points with explicit raw vector if it was a basic search, 
            # but here we have negatives.
            # We will just fallback to search on the first positive vector to avoid crashing.
            print("Warning: client.recommend not found. Falling back to search (ignoring negatives).")
            target = positive_vectors[0] if positive_vectors else np.random.rand(VECTOR_SIZE).tolist()
            if isinstance(target, list) and len(target) > 0 and isinstance(target[0], list):
                 target = target[0] # Handle list of lists
                 
            results = client.query_points(
                collection_name=COLLECTION_NAME,
                query=target,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
                with_vectors=True
            ).points
            
        return [
            {
                "id": point.id,
                "filename": point.payload["filename"],
                "score": point.score,
                "vector": point.vector
            }
            for point in results
        ]
    except Exception as e:
        print(f"Recommendation failed: {e}")
        return []

def get_all_vectors(client):
    """Retrieves all vectors and metadata from the collection."""
    all_points = []
    offset = None
    
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            scroll_filter=None,
            limit=100,
            with_vectors=True,
            with_payload=True,
            offset=offset
        )
        all_points.extend(points)
        if offset is None:
            break
            
    return [
        {
            "id": p.id,
            "filename": p.payload["filename"],
            "vector": p.vector
        }
        for p in all_points
    ]


