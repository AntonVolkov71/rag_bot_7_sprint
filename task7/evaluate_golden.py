import csv
import datetime as dt
import requests

API = "http://127.0.0.1:8000"
ASK = f"{API}/ask"

GOLDEN = "task7/golden_questions.tsv"
OUT = "task7/run_logs.csv"

def now_iso():
    return dt.datetime.now().isoformat(timespec="seconds")

def main():
    rows = []
    with open(GOLDEN, "r", encoding="utf-8") as f:
        header = f.readline()
        for line in f:
            if not line.strip():
                continue
            expected, question = line.rstrip("\n").split("\t", 1)

            r = requests.post(ASK, json={"question": question, "k": 3}, timeout=60)
            r.raise_for_status()
            data = r.json()

            found = bool(data.get("found"))
            sources = data.get("sources") or []

            top_sources = ";".join([s.get("source","") for s in sources[:3]])
            top_entities = ";".join([s.get("entity","") for s in sources[:3]])
            chunks_found = len(sources)

            passed = (expected == "answer" and found) or (expected == "unknown" and (not found))

            rows.append({
                "ts": now_iso(),
                "question": question,
                "expected": expected,
                "found": int(found),
                "chunks_found": chunks_found,
                "top_sources": top_sources,
                "top_entities": top_entities,
                "pass": int(passed),
            })

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    total = len(rows)
    ok = sum(r["pass"] for r in rows)
    print(f"Done: {ok}/{total} passed. CSV: {OUT}")

if __name__ == "__main__":
    main()
