import os
import sys
import time
import sqlite3

# Ensure atlas root is on sys.path
sys.path.insert(0, r"d:\Atlas")

from database.db import (
    create_database,
    save_indexed_location,
    save_files,
    search_files,
    quick_scan_location,
    extract_text_from_file,
    index_file_content,
    index_all_content,
    natural_language_search,
    generate_all_embeddings,
    generate_file_embedding,
    get_search_suggestions,
    get_indexing_status,
    CONTENT_EXTENSIONS
)
from scanner.scan import scan_folder

TEST_DIR = r"d:\Atlas\test_corpus"

print("==========================================================")
print(" ATLAS COMPLETE THREE-LAYER SEARCH & INDEXING TEST SUITE")
print("==========================================================")

test_results = []

def record_test(name, expected, actual, passed):
    status = "PASS" if passed else "FAIL"
    test_results.append({
        "name": name,
        "expected": expected,
        "actual": str(actual),
        "status": status
    })
    print(f"[{status}] {name}")
    if not passed:
        print(f"   Expected: {expected}")
        print(f"   Actual:   {actual}")

# ----------------------------------------------------------------
# Step 1: Initialize Database & Schema Verification
# ----------------------------------------------------------------
try:
    create_database()
    conn = sqlite3.connect("atlas.db")
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(files)")
    cols = [r[1] for r in cur.fetchall()]
    has_cols = "file_content" in cols and "content_last_indexed" in cols
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='files_fts'")
    has_fts = cur.fetchone() is not None
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='file_embeddings'")
    has_emb = cur.fetchone() is not None
    conn.close()
    record_test(
        "Database initialization, schema migration & FTS5/Embeddings tables",
        "file_content, content_last_indexed, files_fts, file_embeddings present",
        f"cols={has_cols}, fts={has_fts}, emb={has_emb}",
        has_cols and has_fts and has_emb
    )
except Exception as e:
    record_test("Database initialization, schema migration & FTS5/Embeddings tables", "Success", str(e), False)

# ----------------------------------------------------------------
# Step 2: Index Test Corpus Folder
# ----------------------------------------------------------------
try:
    loc_id = save_indexed_location(TEST_DIR)
    scanned_files = scan_folder(TEST_DIR)
    save_files(scanned_files, loc_id)
    record_test("Folder scanning and file metadata indexing", f"Scanned files >= 8", f"Scanned {len(scanned_files)} files", len(scanned_files) >= 8)
except Exception as e:
    record_test("Folder scanning and file metadata indexing", "Success", str(e), False)

# ----------------------------------------------------------------
# Step 3: Test Direct Content Extraction per Format
# ----------------------------------------------------------------
formats = [
    ("TXT", os.path.join(TEST_DIR, "os_notes.txt"), ".txt", "Process Scheduling"),
    ("MD", os.path.join(TEST_DIR, "database_guide.md"), ".md", "Boyce Codd"),
    ("CSV", os.path.join(TEST_DIR, "inventory_records.csv"), ".csv", "SKU-8821"),
    ("DOCX", os.path.join(TEST_DIR, "ai_ethics_framework.docx"), ".docx", "neural network"),
    ("PPTX", os.path.join(TEST_DIR, "networking_lecture.pptx"), ".pptx", "Transmission Control Protocol"),
    ("XLSX", os.path.join(TEST_DIR, "quarterly_budget_analysis.xlsx"), ".xlsx", "Natural Language Processing"),
    ("PDF", os.path.join(TEST_DIR, "distributed_systems.pdf"), ".pdf", "Consensus Protocols"),
]

for fmt_name, path, ext, expected_keyword in formats:
    try:
        text = extract_text_from_file(path, ext)
        found = expected_keyword.lower() in text.lower()
        record_test(f"{fmt_name} content extraction ({ext})", f"Contains '{expected_keyword}'", f"Found keyword (len={len(text)})", found)
    except Exception as e:
        record_test(f"{fmt_name} content extraction ({ext})", f"Contains '{expected_keyword}'", f"Error: {e}", False)

# ----------------------------------------------------------------
# Step 4: Test Legacy DOC Handling
# ----------------------------------------------------------------
doc_path = os.path.join(TEST_DIR, "legacy_project_spec.doc")
try:
    text = extract_text_from_file(doc_path, ".doc")
    # legacy_doc handles Word 97-2003 or returns empty gracefully without crashing
    record_test("Legacy DOC handling (.doc)", "Graceful text extraction or fallback without error", f"Returned text len={len(text)}", True)
except Exception as e:
    record_test("Legacy DOC handling (.doc)", "No crash", f"Crashed: {e}", False)

# ----------------------------------------------------------------
# Step 5: Test Corrupted File Handling
# ----------------------------------------------------------------
corrupt_path = os.path.join(TEST_DIR, "corrupted_document.pdf")
try:
    text = extract_text_from_file(corrupt_path, ".pdf")
    record_test("Corrupted file resilience", "Returns empty string without crashing", f"Returned safely (len={len(text)})", text == "")
except Exception as e:
    record_test("Corrupted file resilience", "No unhandled crash", f"Crashed: {e}", False)

# ----------------------------------------------------------------
# Step 6: Content Indexing for Test Corpus
# ----------------------------------------------------------------
try:
    conn = sqlite3.connect("atlas.db")
    cur = conn.cursor()
    cur.execute("SELECT id, file_path, extension FROM files WHERE indexed_location_id = ?", (loc_id,))
    test_files = cur.fetchall()
    conn.close()

    indexed_success = 0
    for fid, fpath, fext in test_files:
        if fext and fext.lower() in CONTENT_EXTENSIONS:
            if index_file_content(fid, fpath, fext.lower()):
                indexed_success += 1

    record_test("Content indexing into SQLite FTS5", "Indexed >= 7 documents", f"Indexed {indexed_success} files", indexed_success >= 7)
except Exception as e:
    record_test("Content indexing into SQLite FTS5", "Success", f"Error: {e}", False)

# ----------------------------------------------------------------
# Step 7: Layer 1 — Filename Search
# ----------------------------------------------------------------
res_fname = search_files("os_notes", search_mode="filename")
has_fname = any("os_notes.txt" in r[0] for r in res_fname)
record_test("Layer 1: Filename search ('os_notes')", "Finds os_notes.txt", f"Matches: {[r[0] for r in res_fname[:3]]}", has_fname)

# ----------------------------------------------------------------
# Step 8: Layer 2 — Content Search for each format
# ----------------------------------------------------------------
content_queries = [
    ("TXT Content", "Semaphore Mutex", "os_notes.txt"),
    ("MD Content", "Boyce Codd BCNF", "database_guide.md"),
    ("CSV Content", "Wireless Quantum Sensor", "inventory_records.csv"),
    ("DOCX Content", "mitigation strategies", "ai_ethics_framework.docx"),
    ("PPTX Content", "Transmission Control Protocol", "networking_lecture.pptx"),
    ("XLSX Content", "Enterprise Cloud Infrastructure", "quarterly_budget_analysis.xlsx"),
    ("PDF Content", "Consensus Protocols Paxos", "distributed_systems.pdf"),
]

for label, query, expected_filename in content_queries:
    res = search_files(query, search_mode="content")
    matched = any(expected_filename.lower() in r[0].lower() for r in res)
    match_type = next((r[4] for r in res if expected_filename.lower() in r[0].lower()), None)
    record_test(
        f"Layer 2: {label} Search ('{query}')",
        f"Matches {expected_filename} with match_type in ('content', 'both')",
        f"Matches: {[r[0] for r in res[:2]]}, match_type={match_type}",
        matched and match_type in ("content", "both")
    )

# ----------------------------------------------------------------
# Step 9: Combined Layer 1 + 2 Search (Match Type Distinction)
# ----------------------------------------------------------------
res_combined = search_files("database")
db_match = next((r for r in res_combined if "database_guide.md" in r[0]), None)
record_test(
    "Layer 1+2: Combined search distinguishes filename vs content",
    "Returns match_type in result tuple",
    f"Found: {db_match[0] if db_match else 'None'}, match_type: {db_match[4] if db_match else 'None'}",
    db_match is not None and len(db_match) >= 5
)

# ----------------------------------------------------------------
# Step 10: Extension & Drive Filters, Sorting
# ----------------------------------------------------------------
res_ext = search_files("", file_type=".xlsx")
only_xlsx = all(r[0].lower().endswith(".xlsx") for r in res_ext) and len(res_ext) > 0
record_test("Extension filter (file_type='.xlsx')", "Only returns .xlsx files", f"Count: {len(res_ext)}", only_xlsx)

res_sort = search_files("notes", sort_by="name_asc")
record_test("Sorting functionality (sort_by='name_asc')", "Executes without error", f"Returned {len(res_sort)} results", len(res_sort) > 0)

# ----------------------------------------------------------------
# Step 11: Quick Scan (Modified & Deleted File Handling)
# ----------------------------------------------------------------
# Modify a test file
with open(os.path.join(TEST_DIR, "os_notes.txt"), "a", encoding="utf-8") as f:
    f.write("\nAppended extra keyword: CyberSecurityEncryptionAlgorithm")

res_qs = quick_scan_location(loc_id)
record_test(
    "Quick Scan detection of modified files",
    "modified >= 1",
    f"added={res_qs.get('added')}, modified={res_qs.get('modified')}, deleted={res_qs.get('deleted')}",
    res_qs.get("modified", 0) >= 1
)

# Re-index the modified test file
conn = sqlite3.connect("atlas.db")
cur = conn.cursor()
cur.execute("SELECT id FROM files WHERE file_path = ?", (os.path.join(TEST_DIR, "os_notes.txt"),))
os_file_id = cur.fetchone()[0]
conn.close()

index_file_content(os_file_id, os.path.join(TEST_DIR, "os_notes.txt"), ".txt")

res_mod_search = search_files("CyberSecurityEncryptionAlgorithm", search_mode="content")
has_reindexed = any("os_notes.txt" in r[0] for r in res_mod_search)
record_test(
    "Re-indexed modified file content search",
    "Finds 'CyberSecurityEncryptionAlgorithm' in os_notes.txt",
    f"Matches: {[r[0] for r in res_mod_search]}",
    has_reindexed
)

# ----------------------------------------------------------------
# Step 12: Layer 3 — Natural Language / Semantic Search
# ----------------------------------------------------------------
print("\n--- Generating Embeddings for Test Files ---")
for fid, fpath, fext in test_files:
    generate_file_embedding(fid)

# Also generate for the modified file
generate_file_embedding(os_file_id)

conn = sqlite3.connect("atlas.db")
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM file_embeddings")
emb_count = cur.fetchone()[0]
conn.close()
record_test("Embedding generation for documents", f"Embeddings stored >= 6", f"Stored: {emb_count}", emb_count >= 6)

nl_queries = [
    ("How computers talk to each other across the internet", "networking_lecture.pptx"),
    ("Preventing system freezes and thread deadlocks", "os_notes.txt"),
    ("Company quarterly earnings and revenue margins", "quarterly_budget_analysis.xlsx"),
    ("How to design relational database schemas cleanly", "database_guide.md"),
]

for nl_q, expected_file in nl_queries:
    nl_res = natural_language_search(nl_q, top_k=5)
    found_nl = any(expected_file.lower() in r[0].lower() for r in nl_res)
    top_hit = nl_res[0][0] if nl_res else "None"
    match_type = nl_res[0][4] if nl_res else "None"
    record_test(
        f"Layer 3: Natural Language ('{nl_q}')",
        f"Ranks {expected_file} in top results",
        f"Top hit: {top_hit}, match_type={match_type}",
        found_nl
    )

# ----------------------------------------------------------------
# Step 13: Search Suggestions
# ----------------------------------------------------------------
sugg = get_search_suggestions("os_note")
has_sugg = any("os_notes" in s["name"].lower() for s in sugg)
record_test("Search suggestions", "Returns suggestion for 'os_note'", f"Suggestions: {[s['name'] for s in sugg]}", has_sugg)

# ----------------------------------------------------------------
# Summary Table
# ----------------------------------------------------------------
print("\n==========================================================")
print(" TEST SUMMARY")
print("==========================================================")
total_tests = len(test_results)
passed_tests = sum(1 for t in test_results if t["status"] == "PASS")
failed_tests = total_tests - passed_tests

print(f"Total Tests: {total_tests} | Passed: {passed_tests} | Failed: {failed_tests}")
print("==========================================================")

# Write test results to JSON
import json
with open(r"d:\Atlas\test_results.json", "w") as f:
    json.dump(test_results, f, indent=2)
print("Saved detailed test results to d:\\Atlas\\test_results.json")
