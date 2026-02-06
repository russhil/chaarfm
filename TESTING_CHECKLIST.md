# ChaarFM Revamp Testing Checklist

## Pre-Deployment Verification

### ✅ Code Quality
- [x] Python syntax validated (`py_compile` passed)
- [x] Backup created (`user_recommender.py.backup`)
- [x] No import errors
- [ ] Lint errors checked and resolved

### 🔄 Unit Tests

#### Test 1: Neighborhood Validation
```python
# Test that _validate_neighborhood_density works correctly

# Test Case A: Track with dense neighborhood (should pass)
track_id = "popular_punjabi_track"
is_valid, count, avg_sim = recommender._validate_neighborhood_density(track_id)
assert is_valid == True
assert count >= 20
assert avg_sim >= 0.85

# Test Case B: Track with sparse neighborhood (should fail)
track_id = "obscure_track"
is_valid, count, avg_sim = recommender._validate_neighborhood_density(track_id)
assert is_valid == False
assert count < 20
```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Passed | [ ] Failed

---

#### Test 2: User Vector Optimization
```python
# Test that _optimize_for_user_vector filters correctly

# Setup: Create user vector pointing in specific direction
recommender.user_vector = test_vector

# Add candidates with varying alignment
candidates = [
    track_a,  # alignment 0.92 (should pass)
    track_b,  # alignment 0.65 (should fail)
    track_c,  # alignment 0.78 (should pass)
]

optimized = recommender._optimize_for_user_vector(candidates)

# Verify only aligned tracks remain
assert len(optimized) == 2
assert track_b not in optimized
```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Passed | [ ] Failed

---

#### Test 3: Hard Negative Filtering
```python
# Test that persistent negatives are properly filtered

# Setup: Add persistent negative
user_db.add_cluster_negative(user_id, cluster_id, negative_vector, track_id)

# Get recommendations
recommendations = recommender._recommend_similar(
    target_vecs=[target],
    avoid_ids=set(),
    limit=20
)

# Verify no recommendation is >0.80 similar to negative
for rec in recommendations:
    for neg_vec in [negative_vector]:
        sim = calculate_similarity(rec['vector'], neg_vec)
        assert sim <= 0.80
```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Passed | [ ] Failed

---

#### Test 4: Find Track by Vector
```python
# Test that _find_track_by_vector correctly identifies tracks

track = recommender.track_map['test_track_123']
found_id = recommender._find_track_by_vector(track['vector'])

assert found_id == 'test_track_123'
```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Passed | [ ] Failed

---

#### Test 5: Vector-Aligned Cluster Switch
```python
# Test that _find_best_aligned_cluster selects correctly

# Setup: Create user vector aligned with cluster 7
recommender.user_vector = cluster_7_aligned_vector

# Find best cluster (skipping cluster 5)
best_cluster = recommender._find_best_aligned_cluster(skip_clusters={5})

assert best_cluster == 7
```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Passed | [ ] Failed

---

### 🔄 Integration Tests

#### Scenario 1: Cluster Exhaustion Recovery
```
Steps:
1. Start session with 5 liked Punjabi tracks in Cluster 3
2. Skip 3 tracks in a row
3. Verify: User vector optimization triggers
4. Verify: System finds <10 aligned tracks in Cluster 3
5. Verify: System switches to best-aligned cluster (e.g., Cluster 7)
6. Verify: Next recommendation is from Cluster 7
7. Verify: Recommendation is relevant

Expected Logs:
- "[ALGO] Skip Optimization: Checking cluster viability..."
- "[ALGO] ❌ Cluster exhausted after optimization. Switching clusters."
- "[ALGO] Cluster Switch: Selected Cluster 7 (alignment: 0.91)"
```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Passed | [ ] Failed

**Notes:**

---

#### Scenario 2: Dense Neighborhood Validation
```
Steps:
1. User likes track with sparse neighborhood (8 neighbors)
2. System attempts to use as anchor
3. Verify: Neighborhood validation fails
4. Verify: System selects different anchor with 25+ neighbors
5. Verify: All recommended tracks have 15+ neighbors

Expected Logs:
- "[ALGO] ❌ Insufficient Neighborhood: Track X has only 8/20 neighbors"
- "[ALGO] ✅ Dense Neighborhood: Track Y has 25 neighbors"
- "[ALGO] Selected anchor from 3/5 validated dense-neighborhood tracks"
```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Passed | [ ] Failed

**Notes:**

---

#### Scenario 3: Persistent Negative Respect
```
Steps:
1. User dislikes "Sad Bollywood Song A" in Cluster 5 (session 1)
2. System stores vector in cluster_negatives table
3. End session 1
4. Start session 2, user enters Cluster 5
5. Verify: System loads persistent negatives
6. Verify: "Sad Bollywood Song B" (0.88 similar) is filtered out
7. Verify: User never receives Song B in recommendations

Expected Logs:
- "[ALGO] Loaded 1 persistent negatives for Cluster 5"
- "[ALGO] Hard Filtered: Removed 7 tracks similar to persistent negatives (>0.80 similarity)"
```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Passed | [ ] Failed

**Notes:**

---

#### Scenario 4: Validated Radial Probing
```
Steps:
1. User in Exploit mode with 5 session likes
2. System attempts radial probe injection
3. Verify: Only probes with 15+ neighbors at >0.82 similarity are injected
4. Verify: Sparse probes are rejected
5. Verify: Recommended probes support follow-up recommendations

Expected Logs:
- "[ALGO] Found 47 vividly similar candidates (>0.85 sim)"
- "[ALGO] Validated 18/47 probes with dense neighborhoods"
- "[ALGO] Neighborhood-Validated Probe Injection: 18 candidates"
```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Passed | [ ] Failed

**Notes:**

---

### 📊 Production Monitoring

#### Week 1: Canary Deployment (10% traffic)

**Metrics to Track:**
- [ ] Neighborhood validation success rate (target: >85%)
- [ ] Skip rate after optimization (target: <30%)
- [ ] Hard filtering impact (tracks removed per session)
- [ ] Cluster switch frequency (target: 0.5-1 per session)
- [ ] User engagement time (should increase)

**Log Monitoring:**
```bash
# Success indicators
grep "✅ Dense Neighborhood" server.log | wc -l
grep "✅ Found.*aligned tracks" server.log | wc -l

# Warning indicators
grep "❌ Insufficient Neighborhood" server.log | wc -l
grep "❌ Cluster exhausted" server.log | wc -l
```

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed

**Observations:**

---

#### Week 2: Expanded Rollout (50% traffic)

**Metrics to Compare:**
- [ ] A/B test: Revamped vs. Original algorithm
- [ ] Skip rate comparison
- [ ] Recommendation relevance scores
- [ ] Session duration
- [ ] User satisfaction (if feedback available)

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed

**Observations:**

---

#### Week 3: Full Rollout (100% traffic)

**Final Validation:**
- [ ] All metrics stable
- [ ] No increase in API latency
- [ ] User complaints decreased
- [ ] Engagement metrics improved

**Status:** [ ] Not Started | [ ] In Progress | [ ] Completed

**Observations:**

---

## Performance Benchmarks

### Latency Tests

#### Test 1: Neighborhood Validation Overhead
```python
# Measure time for _validate_neighborhood_density
import time

start = time.time()
is_valid, count, avg_sim = recommender._validate_neighborhood_density(track_id)
elapsed = time.time() - start

# Target: <500ms for 2500 track library
assert elapsed < 0.5
```

**Result:** ___ ms | [ ] Passed | [ ] Failed

---

#### Test 2: User Vector Optimization Overhead
```python
# Measure time for _optimize_for_user_vector
start = time.time()
optimized = recommender._optimize_for_user_vector(candidates)
elapsed = time.time() - start

# Target: <200ms for 250 candidates
assert elapsed < 0.2
```

**Result:** ___ ms | [ ] Passed | [ ] Failed

---

#### Test 3: Hard Filtering Overhead
```python
# Measure time for hard negative filtering
start = time.time()
recommendations = recommender._recommend_similar(...)
elapsed = time.time() - start

# Target: <1000ms including filtering
assert elapsed < 1.0
```

**Result:** ___ ms | [ ] Passed | [ ] Failed

---

#### Test 4: End-to-End Recommendation Time
```python
# Measure total time for get_next_track
start = time.time()
track, justification = recommender.get_next_track()
elapsed = time.time() - start

# Target: <2000ms
assert elapsed < 2.0
```

**Result:** ___ ms | [ ] Passed | [ ] Failed

---

## Edge Cases

### Edge Case 1: No Valid Anchors
```
Scenario: All session likes have sparse neighborhoods (<20 neighbors)
Expected: System switches to EXPLORE mode
Verification: Mode should be "EXPLORE" and justification should mention no valid anchors
```

**Status:** [ ] Not Started | [ ] Passed | [ ] Failed

---

### Edge Case 2: All Tracks Filtered by Negatives
```
Scenario: User has rejected so many tracks that >80% of cluster is filtered
Expected: System switches to different cluster
Verification: Cluster ID should change and fail count should reset
```

**Status:** [ ] Not Started | [ ] Passed | [ ] Failed

---

### Edge Case 3: User Vector Uninitialized
```
Scenario: New user with no likes yet
Expected: System uses EXPLORE mode with centroid anchoring
Verification: No errors, valid recommendations returned
```

**Status:** [ ] Not Started | [ ] Passed | [ ] Failed

---

### Edge Case 4: Single Track in Session Likes
```
Scenario: User has only 1 liked track
Expected: System uses tight variance (0.15) and single-anchor validation
Verification: Recommendations are very similar to the single like
```

**Status:** [ ] Not Started | [ ] Passed | [ ] Failed

---

## Rollback Criteria

**Immediate rollback if:**
- [ ] API latency increases >50%
- [ ] Error rate increases >10%
- [ ] Skip rate increases compared to baseline
- [ ] User complaints increase >20%
- [ ] Critical bug discovered

**Rollback procedure:**
```bash
cd /Users/russhil/Desktop/chaarfm
cp user_recommender.py.backup user_recommender.py
# Restart server
# Monitor logs for stability
```

---

## Sign-Off

### Testing Sign-Off
- [ ] All unit tests passed
- [ ] All integration tests passed
- [ ] Performance benchmarks met
- [ ] Edge cases handled

**Tester:** _______________ | **Date:** _______________

### Production Sign-Off
- [ ] Week 1 canary successful
- [ ] Week 2 expanded rollout successful
- [ ] Week 3 full rollout stable
- [ ] Metrics show improvement

**Product Owner:** _______________ | **Date:** _______________

---

## Notes & Observations

### Known Issues


### Future Improvements


### Lessons Learned

