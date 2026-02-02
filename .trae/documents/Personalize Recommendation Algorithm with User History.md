I will implement a personalization module that ingests your `music_universe.json` file to fine-tune the recommendation algorithm.

### Plan: Personalize Algorithm with User History
We will modify the `UserRecommender` to "warm start" based on your listening history instead of starting from scratch.

1.  **Ingest `music_universe.json`**:
    *   Create a new method `load_user_profile_from_json(path)` in `UserRecommender`.
    *   This will parse your top tracks and artists from the JSON file.

2.  **Map to Vector Space**:
    *   Match your top tracks (by filename/title) to the existing `track_map` in our system to find their corresponding vectors.
    *   Compute a **User Taste Vector**: A weighted average of your top tracks' vectors (weighted by playcount).

3.  **Fine-Tune the Algorithm**:
    *   **Initialize User Vector**: Set the session's `user_vector` to this calculated Taste Vector immediately. This means the very first recommendation will be aligned with your long-term taste.
    *   **Boost Clusters**: Identify which clusters your favorite songs belong to and "boost" their probability in the Multi-Armed Bandit algorithm (increase `alpha` scores). This ensures the explorer starts in your favorite "zones".

4.  **Verification**:
    *   I will run a test script to load the profile and print out the detected "Favorite Clusters" and the calculated User Vector to confirm it's working.
