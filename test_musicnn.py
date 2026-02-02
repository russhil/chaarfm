try:
    import musicnn
    from musicnn.tagger import top_tags
    print("musicnn imported successfully.")
except Exception as e:
    print(f"Error importing musicnn: {e}")
    import traceback
    traceback.print_exc()
