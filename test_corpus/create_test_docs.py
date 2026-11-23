import os
import csv
from pypdf import PdfWriter
from docx import Document
from pptx import Presentation
from openpyxl import Workbook

TEST_DIR = r"d:\Atlas\test_corpus"
os.makedirs(TEST_DIR, exist_ok=True)

# 1. TXT
with open(os.path.join(TEST_DIR, "os_notes.txt"), "w", encoding="utf-8") as f:
    f.write("Operating System Process Scheduling, Semaphore, Mutex and Deadlock Prevention Algorithms.")

# 2. MD
with open(os.path.join(TEST_DIR, "database_guide.md"), "w", encoding="utf-8") as f:
    f.write("# Database Systems\n\nRelational Database Normalization Third Normal Form and Boyce Codd BCNF Rules.")

# 3. CSV
with open(os.path.join(TEST_DIR, "inventory_records.csv"), "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["ItemID", "ItemName", "Category", "Quantity", "Price"])
    writer.writerow(["SKU-8821", "Wireless Quantum Sensor", "Electronics Hardware", "45", "129.99"])
    writer.writerow(["SKU-9932", "Fiber Optic Transceiver", "Networking Gear", "12", "499.50"])

# 4. DOCX
doc = Document()
doc.add_heading("Artificial Intelligence Ethics", 0)
doc.add_paragraph("Machine learning models, neural network training, ethical guidelines, and bias mitigation strategies.")
doc.save(os.path.join(TEST_DIR, "ai_ethics_framework.docx"))

# 5. PPTX
prs = Presentation()
slide = prs.slides.add_slide(prs.slide_layouts[0])
title = slide.shapes.title
subtitle = slide.placeholders[1]
title.text = "Computer Networks and Protocols"
subtitle.text = "Transmission Control Protocol TCP IP, routing tables, and socket programming."
prs.save(os.path.join(TEST_DIR, "networking_lecture.pptx"))

# 6. XLSX
wb = Workbook()
ws = wb.active
ws.title = "Financials"
ws.append(["Department", "Q1 Revenue", "Q2 Revenue", "Net Margin", "Notes"])
ws.append(["Cloud Services", 1500000, 1850000, "24.5%", "Enterprise Cloud Infrastructure growth"])
ws.append(["AI Research", 800000, 950000, "15.2%", "Natural Language Processing compute budget"])
wb.save(os.path.join(TEST_DIR, "quarterly_budget_analysis.xlsx"))

# 7. PDF
pdf_bytes = (
    b'%PDF-1.4\n'
    b'1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n'
    b'2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n'
    b'3 0 obj\n<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>\nendobj\n'
    b'4 0 obj\n<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>\nendobj\n'
    b'5 0 obj\n<</Length 82>>\nstream\n'
    b'BT\n/F1 12 Tf\n72 712 Td\n(Distributed Systems Consensus Protocols Paxos and Raft) Tj\nET\n'
    b'endstream\nendobj\n'
    b'xref\n0 6\n'
    b'0000000000 65535 f \n'
    b'0000000009 00000 n \n'
    b'0000000058 00000 n \n'
    b'0000000115 00000 n \n'
    b'0000000228 00000 n \n'
    b'0000000299 00000 n \n'
    b'trailer\n<</Size 6/Root 1 0 R>>\nstartxref\n432\n%%EOF\n'
)
with open(os.path.join(TEST_DIR, "distributed_systems.pdf"), "wb") as f:
    f.write(pdf_bytes)

# 8. Corrupted file (for resilience testing)
with open(os.path.join(TEST_DIR, "corrupted_document.pdf"), "wb") as f:
    f.write(b"NOT A REAL PDF FILE HEADER JUST GARBAGE %PDF-9999999 RANDOM CORRUPT DATA")

# 9. Legacy DOC test
# Create a dummy .doc file with plain text or binary header to test graceful handling
with open(os.path.join(TEST_DIR, "legacy_project_spec.doc"), "wb") as f:
    f.write(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"Legacy Word 97-2003 OLE binary container test document")

print("Created test corpus in", TEST_DIR)
