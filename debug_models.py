from qdrant_client import QdrantClient
from qdrant_client.http import models

print([m for m in dir(models) if 'Recommend' in m])
