#!/usr/bin/env python3
"""
Test script to verify optimization improvements.
Tests the neighborhood pre-computation and batch loading performance.
"""

import time
import sys
import user_db

# Initialize DB first
user_db.init_db()

from user_recommender import UserRecommender

def test_initialization_time():
    """Test how long it takes to initialize a recommender with pre-computation."""
    print("\n" + "="*60)
    print("TEST 1: Initialization Time with Pre-computation")
    print("="*60)
    
    start = time.time()
    recommender = UserRecommender(user_id="test_user", collection_name="music_averaged", youtube_mode=False)
    elapsed = time.time() - start
    
    print(f"\n✅ Initialization completed in {elapsed:.2f} seconds")
    
    # Check if neighborhood cache was populated
    cache_size = len(recommender.cluster_manager.neighborhood_cache)
    print(f"✅ Neighborhood cache size: {cache_size} tracks")
    
    if cache_size > 0:
        print("✅ Pre-computation successful!")
    else:
        print("❌ Pre-computation failed - cache is empty")
        return False
    
    return recommender, elapsed

def test_batch_generation(recommender):
    """Test how long it takes to generate a batch of recommendations."""
    print("\n" + "="*60)
    print("TEST 2: Batch Generation Time")
    print("="*60)
    
    start = time.time()
    batch = recommender.get_next_batch()
    elapsed = time.time() - start
    
    print(f"\n✅ Batch generation completed in {elapsed:.2f} seconds")
    print(f"✅ Batch size: {len(batch)} tracks")
    
    if batch:
        print("\n📋 First 3 tracks:")
        for i, track in enumerate(batch[:3], 1):
            print(f"  {i}. {track['filename']}")
    
    return elapsed

def test_validation_speed(recommender):
    """Test the speed of neighborhood validation with cache."""
    print("\n" + "="*60)
    print("TEST 3: Neighborhood Validation Speed (Cache vs No Cache)")
    print("="*60)
    
    # Get a sample track ID
    sample_track_id = list(recommender.track_map.keys())[0]
    
    # Test with cache
    start = time.time()
    is_valid, count, avg_sim = recommender._validate_neighborhood_density(sample_track_id, silent=True)
    cache_time = time.time() - start
    
    print(f"\n✅ Cached validation: {cache_time*1000:.2f} ms")
    print(f"   Valid: {is_valid}, Neighbors: {count}, Avg Sim: {avg_sim:.3f}")
    
    # Test without cache (slow method)
    start = time.time()
    is_valid2, count2, avg_sim2 = recommender._validate_neighborhood_density_slow(sample_track_id, silent=False)
    slow_time = time.time() - start
    
    print(f"\n✅ Non-cached validation: {slow_time*1000:.2f} ms")
    print(f"   Valid: {is_valid2}, Neighbors: {count2}, Avg Sim: {avg_sim2:.3f}")
    
    speedup = slow_time / cache_time if cache_time > 0 else 0
    print(f"\n🚀 Speedup: {speedup:.1f}x faster with cache!")
    
    return cache_time, slow_time

def main():
    """Run all optimization tests."""
    print("\n" + "🔬 " + "="*58)
    print("    ChaarFM Optimization Test Suite")
    print("="*60 + "\n")
    
    try:
        # Test 1: Initialization
        recommender, init_time = test_initialization_time()
        
        # Test 2: Batch generation
        batch_time = test_batch_generation(recommender)
        
        # Test 3: Validation speed
        cache_time, slow_time = test_validation_speed(recommender)
        
        # Summary
        print("\n" + "="*60)
        print("📊 SUMMARY")
        print("="*60)
        print(f"✅ Initialization: {init_time:.2f}s")
        print(f"✅ Batch generation: {batch_time:.2f}s")
        print(f"✅ Validation speedup: {(slow_time/cache_time):.1f}x")
        
        if batch_time < 30:
            print("\n🎉 OPTIMIZATION SUCCESS! Batch time < 30s")
        else:
            print(f"\n⚠️  Batch time still high: {batch_time:.2f}s (target: <30s)")
        
        print("\n" + "="*60 + "\n")
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
