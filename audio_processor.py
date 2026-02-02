
import os
import numpy as np
import essentia.standard as es
import urllib.request
import ssl

# Constants
MODEL_URL = "https://essentia.upf.edu/models/feature-extractors/musicnn/msd-musicnn-1.pb"
MODEL_PATH = "msd-musicnn-1.pb"
SAMPLE_RATE = 16000

def download_model():
    """Download the pre-trained musicnn model if it doesn't exist."""
    if not os.path.exists(MODEL_PATH):
        print(f"Downloading model from {MODEL_URL}...")
        
        # Bypass SSL verification
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        try:
            with urllib.request.urlopen(MODEL_URL, context=ctx) as response, open(MODEL_PATH, 'wb') as out_file:
                out_file.write(response.read())
            print("Model downloaded.")
        except Exception as e:
            print(f"Failed to download model: {e}")
            if os.path.exists(MODEL_PATH):
                os.remove(MODEL_PATH)
            raise e

class MusicNNExtractor:
    def __init__(self):
        """Initialize the MusiCNN model."""
        if not os.path.exists(MODEL_PATH):
            download_model()
            
        print("Initializing TensorflowPredictMusiCNN...")
        # Use simple wrapper
        self.model = es.TensorflowPredictMusiCNN(graphFilename=MODEL_PATH, 
                                                output="model/dense/BiasAdd")

    def extract(self, file_path):
        """
        Analyzes the track to find segments (Vibe Switches) and the overall average.
        Returns: 
        {
            "average_vector": np.array,
            "segments": [
                {"vector": np.array, "start": float, "end": float}
            ]
        }
        """
        # Load audio (mono, 16kHz)
        loader = es.MonoLoader(filename=file_path, sampleRate=SAMPLE_RATE)
        audio = loader()
        
        # 1. Macro-Level Analysis (Whole song in one go, if fits in memory)
        # MusiCNN usually takes ~3s chunks.
        # Essentia's TensorflowPredictMusiCNN can take the whole stream and returns [time, 200]
        full_embeddings = self.model(audio) # Shape: (N_patches, 200)
        
        # Global Average (The "Song Vibe")
        average_vector = np.mean(full_embeddings, axis=0)
        
        # 2. Vibe Switch Detection
        # User logic: "Compare each second/timegap vector with the entire average map... extreme relative shift"
        # full_embeddings is roughly 1 vector per ~3 seconds (MusiCNN patch).
        # Let's clean this up into cleaner segments.
        
        # We will process the raw embeddings into "Segments".
        # Simple Clustering / Change Point Detection
        
        segments = []
        n_patches = full_embeddings.shape[0]
        
        # Calculate distance of each patch from average
        # using Euclidean for simplicity, or Cosine
        
        if n_patches < 2:
            # Too short, just one segment
            segments.append({
                "vector": average_vector,
                "start": 0,
                "end": len(audio) / SAMPLE_RATE
            })
            return {"average_vector": average_vector, "segments": segments}
            
        # Group patches into segments based on similarity
        # Simple greedy approach: 
        # Start segment. Add patches. If a patch is too far from segment mean, break.
        # OR: Just strictly follow user request: 
        # "position of the vector in the average song map... indicator of moments where flow meaningfully changes"
        
        # Let's just store "Significant Segments".
        # For simplicity in this iteration:
        # We will create fixed windows (e.g. 30s) OR
        # We will actally implement a simple change detector.
        
        # Let's do a sliding window check against average.
        # If dot_product(patch, average) < threshold, it's a "Deviant" segment (e.g. the Drop vs Intro).
        
        # Better: Clustering on the patches?
        # "creating two seperate or more cluster of second/timegap vectors for one single mp3 file"
        
        from sklearn.cluster import KMeans
        
        # Try to cluster patches into k=3 (Intro, Verse, Chorus/Drop?)
        # Only if song is long enough (>30s)
        duration_sec = len(audio) / SAMPLE_RATE
        n_clusters = 1
        if duration_sec > 30: n_clusters = 2
        if duration_sec > 120: n_clusters = 3
        if duration_sec > 240: n_clusters = 4
        
        try:
             kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init='auto')
             labels = kmeans.fit_predict(full_embeddings)
             
             # Group contiguous labels into segments
             # This naturally finds "vibe blocks"
             
             # Convert patches to time: roughly 3 sec per patch?
             # MusiCNN: input 16khz. Patch hop? 
             # Essentia documentation: output is [N, 200].
             # We can infer time step. 
             time_step = duration_sec / n_patches
             
             current_label = labels[0]
             start_idx = 0
             
             for i in range(1, n_patches):
                 if labels[i] != current_label:
                     # End of segment
                     end_idx = i
                     seg_vec = np.mean(full_embeddings[start_idx:end_idx], axis=0)
                     segments.append({
                         "vector": seg_vec,
                         "start": start_idx * time_step,
                         "end": end_idx * time_step,
                         "label": int(current_label) # Just for debug
                     })
                     
                     current_label = labels[i]
                     start_idx = i
             
             # Last segment
             seg_vec = np.mean(full_embeddings[start_idx:], axis=0)
             segments.append({
                 "vector": seg_vec,
                 "start": start_idx * time_step,
                 "end": duration_sec,
                 "label": int(current_label)
             })
             
        except Exception as e:
            print(f"Clustering failed: {e}. Fallback to average.")
            segments.append({
                "vector": average_vector,
                "start": 0,
                "end": duration_sec
            })

        return {
            "average_vector": average_vector,
            "segments": segments
        }
