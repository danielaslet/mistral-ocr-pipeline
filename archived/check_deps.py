try:
    import fitz

    print("✅ fitz (PyMuPDF) OK:", fitz.__version__)
except ImportError:
    print("❌ fitz not found! Did you `pip install pymupdf`?")
