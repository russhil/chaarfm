#!/usr/bin/env python3
"""
Consolidated Debug and Testing Tools for ChaarFM
Contains all debugging utilities in one place with a CLI interface
"""
import sys
import argparse


def check_essentia():
    """Check Essentia installation and available algorithms"""
    print("=== Checking Essentia ===")
    try:
        import essentia.standard as es
        print("✓ Essentia imported successfully")
        print(f"Has TensorflowPredict: {hasattr(es, 'TensorflowPredict')}")
        print(f"Has TensorflowPredictMusiCNN: {hasattr(es, 'TensorflowPredictMusiCNN')}")
        print(f"Has TensorflowPredictVGGish: {hasattr(es, 'TensorflowPredictVGGish')}")
        print("\nTensor/Predict related methods:")
        print([x for x in dir(es) if 'Tensor' in x or 'Predict' in x])
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def check_musicnn():
    """Check MusicNN installation"""
    print("=== Checking MusicNN ===")
    try:
        import musicnn
        from musicnn.tagger import top_tags
        print("✓ musicnn imported successfully")
    except Exception as e:
        print(f"✗ Error importing musicnn: {e}")
        import traceback
        traceback.print_exc()


def check_tkinter():
    """Test Tkinter GUI availability"""
    print("=== Checking Tkinter ===")
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
        root = tk.Tk()
        root.withdraw()
        print("✓ Tkinter initialized successfully")
        root.destroy()
    except Exception as e:
        print(f"✗ Tkinter failed: {e}")


def check_qdrant_models():
    """Check Qdrant models and recommendations"""
    print("=== Checking Qdrant Models ===")
    try:
        from qdrant_client import QdrantClient
        from qdrant_client.http import models
        import numpy as np
        
        print("✓ Qdrant imported successfully")
        print(f"Recommend methods: {[m for m in dir(models) if 'Recommend' in m]}")
        print(f"Has RecommendStrategy: {'RecommendStrategy' in dir(models)}")
        
        # Try to connect to local Qdrant
        try:
            client = QdrantClient(path="./qdrant_data")
            print("✓ Connected to local Qdrant")
            
            # Test query_points
            print("\nTesting query_points (Search)...")
            res = client.query_points(
                collection_name="music_collection",
                query=np.random.rand(200).tolist(),
                limit=1
            )
            print(f"✓ Search successful: {len(res.points)} points returned")
        except Exception as e:
            print(f"⚠ Local Qdrant test failed: {e}")
            
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def inspect_db_schema():
    """Inspect database schema"""
    print("=== Inspecting Database Schema ===")
    try:
        import user_db
        from sqlalchemy import text
        
        print("Inspecting public.vectors_russhil schema...")
        with user_db.engine.connect() as conn:
            # Get column names
            result = conn.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'vectors_russhil'
            """)).fetchall()
            
            print("\nColumns:")
            for col, dtype in result:
                print(f"  {col}: {dtype}")
                
            # Sample row
            print("\nSample Row:")
            row = conn.execute(text('SELECT * FROM public."vectors_russhil" LIMIT 1')).mappings().fetchone()
            if row:
                print(dict(row))
            else:
                print("Table is empty")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def inspect_db_constraints():
    """Inspect database constraints"""
    print("=== Inspecting Database Constraints ===")
    try:
        import user_db
        from sqlalchemy import text
        
        print("Inspecting cluster_affinity constraints...")
        with user_db.engine.connect() as conn:
            # Check table existence
            exists = conn.execute(text("SELECT to_regclass('public.cluster_affinity')")).scalar()
            if not exists:
                print("⚠ Table cluster_affinity does not exist.")
                return

            # Get constraints
            result = conn.execute(text("""
                SELECT conname, pg_get_constraintdef(oid) 
                FROM pg_constraint 
                WHERE conrelid = 'public.cluster_affinity'::regclass
            """)).fetchall()
            
            print("\nConstraints:")
            for name, definition in result:
                print(f"  {name}: {definition}")
                
            # Check Primary Key columns
            pk = conn.execute(text("""
                SELECT a.attname
                FROM   pg_index i
                JOIN   pg_attribute a ON a.attrelid = i.indrelid
                                     AND a.attnum = ANY(i.indkey)
                WHERE  i.indrelid = 'public.cluster_affinity'::regclass
                AND    i.indisprimary
            """)).fetchall()
            print("\nPrimary Key Columns:", [row[0] for row in pk])
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_recommender():
    """Test the recommender system"""
    print("=== Testing Recommender ===")
    try:
        print("Importing user_db...")
        import user_db
        print("Importing UserRecommender...")
        from user_recommender import UserRecommender
        
        print("Initializing UserRecommender for 'vectors_russhil'...")
        rec = UserRecommender("russhil", collection_name="vectors_russhil")
        
        print(f"\n✓ Track Map Size: {len(rec.track_map)}")
        
        if len(rec.track_map) == 0:
            print("✗ CRITICAL: Track map is empty!")
            return
            
        print("Sample Track:")
        first_id = list(rec.track_map.keys())[0]
        print(rec.track_map[first_id])
        
        print("\nTesting get_next_track()...")
        track, reason = rec.get_next_track()
        print(f"✓ Result: {track['filename'] if track else 'None'} | Reason: {reason}")
        
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_s3_buckets():
    """List S3/R2 buckets"""
    print("=== Testing S3/R2 Connection ===")
    try:
        import boto3
        import os
        from dotenv import load_dotenv
        from botocore.config import Config
        
        load_dotenv()
        
        endpoint = os.getenv("S3_ENDPOINT")
        key = os.getenv("S3_ACCESS_KEY")
        secret = os.getenv("S3_SECRET_KEY")
        
        print(f"Connecting to {endpoint}...")
        
        client = boto3.client(
            's3',
            endpoint_url=endpoint,
            aws_access_key_id=key,
            aws_secret_access_key=secret,
            config=Config(signature_version='s3v4'),
            region_name='auto'
        )
        
        response = client.list_buckets()
        print("✓ Buckets found:")
        for bucket in response['Buckets']:
            print(f"  - {bucket['Name']}")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_vectorization():
    """Test audio vectorization"""
    print("=== Testing Vectorization ===")
    try:
        from music_pipeline.vectorizer import extract_embeddings
        import numpy as np
        
        print("✓ Vectorizer imported successfully")
        print("Note: To fully test, provide an audio file path")
        # Add your test file path here if needed
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def test_db_log():
    """Test database interaction logging"""
    print("=== Testing Database Logging ===")
    try:
        import user_db
        from datetime import datetime
        
        user_db.init_db()
        user_db.log_interaction_db(
            session_id="test_session",
            user_id="test_user",
            track_id="test_track",
            filename="test_song.mp3",
            action="play",
            duration=0,
            justification="Testing via debug_tools",
            details="Automated test"
        )
        print("✓ Test log inserted successfully")
    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()


def run_all_checks():
    """Run all diagnostic checks"""
    print("=" * 60)
    print("Running All ChaarFM Diagnostic Checks")
    print("=" * 60)
    
    checks = [
        check_essentia,
        check_musicnn,
        check_tkinter,
        check_qdrant_models,
        inspect_db_schema,
        inspect_db_constraints,
        test_recommender,
        test_s3_buckets,
        test_vectorization,
    ]
    
    for check in checks:
        try:
            check()
            print()
        except Exception as e:
            print(f"✗ Check failed: {e}\n")


def main():
    parser = argparse.ArgumentParser(
        description='ChaarFM Debug and Testing Tools',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Available Commands:
  all                - Run all diagnostic checks
  essentia          - Check Essentia installation
  musicnn           - Check MusicNN installation
  tkinter           - Test Tkinter GUI
  qdrant            - Check Qdrant models
  db-schema         - Inspect database schema
  db-constraints    - Inspect database constraints
  recommender       - Test recommender system
  s3                - Test S3/R2 connection
  vectorization     - Test vectorization
  db-log            - Test database logging

Examples:
  python scripts/debug_tools.py all
  python scripts/debug_tools.py essentia
  python scripts/debug_tools.py recommender
        """
    )
    
    parser.add_argument('command', 
                       choices=['all', 'essentia', 'musicnn', 'tkinter', 'qdrant',
                               'db-schema', 'db-constraints', 'recommender', 's3',
                               'vectorization', 'db-log'],
                       help='Debug command to run')
    
    args = parser.parse_args()
    
    commands = {
        'all': run_all_checks,
        'essentia': check_essentia,
        'musicnn': check_musicnn,
        'tkinter': check_tkinter,
        'qdrant': check_qdrant_models,
        'db-schema': inspect_db_schema,
        'db-constraints': inspect_db_constraints,
        'recommender': test_recommender,
        's3': test_s3_buckets,
        'vectorization': test_vectorization,
        'db-log': test_db_log,
    }
    
    commands[args.command]()


if __name__ == "__main__":
    main()
