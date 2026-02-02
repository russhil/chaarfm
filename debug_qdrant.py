from qdrant_client import QdrantClient
from qdrant_client.http import models
import numpy as np

try:
    client = QdrantClient(path="./qdrant_data")
    
    # Check models
    print(f"Has RecommendStrategy? {'RecommendStrategy' in dir(models)}")
    
    # Try query_points for search
    print("Testing query_points (Search)...")
    try:
        res = client.query_points(
            collection_name="music_collection",
            query=np.random.rand(200).tolist(),
            limit=1
        )
        print(f"Search result type: {type(res)}")
        print(f"Search result points: {len(res.points)}")
        if res.points:
             print(f"First point score: {res.points[0].score}")
    except Exception as e:
        print(f"query_points (Search) failed: {e}")

    # Try query_points for recommend
    # Note: In new client, clean recommendation might use 'pre' or 'recommend'
    # Checking if we can pass a special query object
    print("Testing query_points (Recommend)...")
    try:
        # Assuming we need some positive ID, but we can try with vector
        rand_vec = np.random.rand(200).tolist()
        
        # New syntax usually: query=models.RecommendInput or similar?
        # Or just passing named args if supported? No, query_points takes `query`.
        
        # Trying models.RecommendInput or similar if it exists?
        # Actually standard search is just passing a vector.
        # Recommendation usually needs positive/negative.
        
        pass 
    except Exception as e:
        print(f"query_points (Recommend) failed: {e}")

except Exception as e:
    print(f"Error: {e}")
