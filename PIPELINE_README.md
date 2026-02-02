# MP3 Vectorization Pipeline

## Overview

This pipeline converts MP3 files into 200-dimensional MusiCNN embeddings and stores them in Qdrant vector database.

## Folder Structure

```
/Users/russhil/Desktop/aand pav/
├── russhil/          # 1,385 songs (your collection)
├── sahil/            # 2,029 songs (sahil's collection)
└── songs-downloaded/ # (legacy - 1,461 songs already processed)
```

## Collections Created

| Collection | Description | Status |
|------------|-------------|--------|
| `music_russhil` | Only russhil's 1,385 songs | New |
| `music_sahil` | Only sahil's 2,029 songs | New |
| `music_combined` | Both collections merged (3,414 songs) | New |
| `music_russhil_p03` | Power 0.3 transformed (better clusters) | After transform |
| `music_sahil_p03` | Power 0.3 transformed | After transform |
| `music_combined_p03` | Power 0.3 transformed | After transform |

## Usage

### Step 1: Dry Run (Check files)
```bash
python pipeline_vectorize.py --dry-run
```

### Step 2: Run Full Pipeline
```bash
python pipeline_vectorize.py
```

**Estimated time:** ~3,414 files × 2-3 seconds = ~2-3 hours

### Step 3: Apply Power 0.3 Transformation
```bash
python pipeline_transform.py
```

This creates `_p03` versions of each collection with better cluster separation.

## Requirements

- **Option A (Preferred):** Qdrant running on localhost:6333 (`docker run -p 6333:6333 qdrant/qdrant`)
- **Option B (Fallback):** No setup needed! The scripts will automatically use local storage (`./qdrant_data`) if the server is unreachable.
- essentia library (`pip install essentia`)
- MusiCNN model (auto-downloaded on first run)

## Monitoring Progress

The pipeline uses tqdm for progress bars. You'll see:
```
Processing [russhil] (1385 files)...
  russhil: 100%|████████████| 1385/1385 [45:32<00:00, 1.97s/file]
```

## Resume After Failure

Currently the pipeline doesn't support resume. If it fails midway:
1. The already-uploaded points are safe in Qdrant
2. Re-run with `recreate_collections=False` to append instead of replace
3. Or just re-run (it will overwrite)

## Output

After completion, you'll have 6 Qdrant collections:
- 3 original (200D normalized vectors)
- 3 power-transformed (better for clustering/recommendations)

Use the vector map selector on the login page to choose which collection to use.
