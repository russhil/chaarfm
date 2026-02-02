import os
import numpy as np
import essentia.standard as es
import urllib.request
import ssl

# Constants
MODEL_URL = "https://essentia.upf.edu/models/feature-extractors/musicnn/msd-musicnn-1.pb"
# We assume the model is in the project root or we download it to a local cache
MODEL_FILENAME = "msd-musicnn-1.pb"
SAMPLE_RATE = 16000

def get_model_path():
    # Check current directory
    if os.path.exists(MODEL_FILENAME):
        return os.path.abspath(MODEL_FILENAME)
    
    # Check parent directory (if running from module)
    parent_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), MODEL_FILENAME)
    if os.path.exists(parent_path):
        return parent_path
        
    # Check if we should download it to current dir
    return MODEL_FILENAME

def download_model(model_path):
    """Download the pre-trained musicnn model if it doesn't exist."""
    if not os.path.exists(model_path):
        print(f"  Downloading model from {MODEL_URL}...")
        
        # Bypass SSL verification
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        try:
            with urllib.request.urlopen(MODEL_URL, context=ctx) as response, open(model_path, 'wb') as out_file:
                out_file.write(response.read())
            print("  Model downloaded.")
        except Exception as e:
            print(f"  Failed to download model: {e}")
            if os.path.exists(model_path):
                os.remove(model_path)
            raise e

class EssentiaMusicNN:
    _instance = None
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
        
    def __init__(self):
        self.model_path = get_model_path()
        if not os.path.exists(self.model_path):
            download_model(self.model_path)
            
        print(f"  Initializing Essentia TensorflowPredictMusiCNN with {self.model_path}...")
        self.model = es.TensorflowPredictMusiCNN(graphFilename=self.model_path, 
                                                output="model/dense/BiasAdd")

    def vectorize(self, filepath):
        # Load audio (mono, 16kHz)
        # essentia throws runtime error if file cannot be decoded
        try:
            loader = es.MonoLoader(filename=filepath, sampleRate=SAMPLE_RATE)
            audio = loader()
            
            # Extract embeddings (N_patches, 200)
            embeddings = self.model(audio)
            
            # Global Average
            average_vector = np.mean(embeddings, axis=0)
            
            if np.isnan(average_vector).any():
                print("  Warning: Vector contains NaNs.")
                return None
                
            return average_vector.tolist()
            
        except Exception as e:
            print(f"  Essentia Error: {e}")
            return None

def vectorize_audio(filepath):
    """
    Vectorizes audio using Essentia's MusicNN wrapper.
    """
    print(f"  Vectorizing: {os.path.basename(filepath)}...")
    try:
        extractor = EssentiaMusicNN.get_instance()
        return extractor.vectorize(filepath)
    except Exception as e:
        print(f"  Vectorization failed: {e}")
        return None
