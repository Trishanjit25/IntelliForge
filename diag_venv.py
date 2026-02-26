import sys
import os

print(f"Python Version: {sys.version}")
try:
    import chromadb
    print(f"ChromaDB Version: {chromadb.__version__}")
except ImportError:
    print("ChromaDB not found")
except Exception as e:
    print(f"Error importing ChromaDB: {e}")

print("Venv check finished")
