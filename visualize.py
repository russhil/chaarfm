
import numpy as np
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from qdrant_client import QdrantClient
from vector_db import COLLECTION_NAME, get_client

def visualize():
    client = get_client()
    
    # 1. Fetch all points (limit to 100 for speed/clarity)
    # Scroll API is better for larger datasets
    try:
        response = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=100,
            with_vectors=True,
            with_payload=True
        )
        points = response[0]
    except Exception as e:
        print(f"Error fetching points: {e}")
        return

    if not points:
        print("No points found in collection. Run main.py first to index some music!")
        return

    vectors = np.array([p.vector for p in points])
    filenames = [p.payload.get('filename', 'unknown') for p in points]
    
    print(f"Fetched {len(vectors)} vectors.")

    # 2. Reduce dimensionality
    # If we have enough points, use t-SNE, otherwise PCA is safer
    if len(vectors) > 5:
        print("Running dimensionality reduction...")
        # Reduce to 50 dims with PCA first if high dim, but 200 is small enough for t-SNE directly
        # perplexity must be < n_samples
        perp = min(30, len(vectors) - 1)
        reducer = TSNE(n_components=2, perplexity=perp, random_state=42, init='pca', learning_rate='auto')
        coords = reducer.fit_transform(vectors)
    else:
        print("Not enough points for t-SNE, using PCA.")
        reducer = PCA(n_components=2)
        coords = reducer.fit_transform(vectors)

    # 3. Plot
    plt.figure(figsize=(10, 8))
    plt.scatter(coords[:, 0], coords[:, 1], c='blue', alpha=0.6)
    
    for i, txt in enumerate(filenames):
        plt.annotate(txt, (coords[i, 0], coords[i, 1]), fontsize=8, alpha=0.8)
        
    plt.title(f"Music Vector Map ({len(vectors)} tracks)")
    plt.xlabel("Dimension 1")
    plt.ylabel("Dimension 2")
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    
    output_file = "music_map.png"
    plt.savefig(output_file)
    print(f"Map saved to {output_file}")
    # plt.show() # processing usually headless, safer to save

if __name__ == "__main__":
    visualize()
