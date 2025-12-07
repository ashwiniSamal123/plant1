import json
import sqlite3
import urllib.parse
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).parent
DB_PATH = ROOT / "inspection.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
  id TEXT PRIMARY KEY,
  user TEXT,
  inspectionDate TEXT,
  manufactureName TEXT,
  address TEXT,
  country TEXT,
  city TEXT,
  pincode TEXT,
  tacId TEXT,
  plantInspectionReportNumber TEXT,
  testReportNumber TEXT,
  packModel TEXT,
  remark TEXT,
  createdAt INTEGER
);
"""

def init_db():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(SCHEMA)
        conn.commit()
    finally:
        conn.close()

def insert_report(payload):
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            """
            INSERT INTO reports (id, user, inspectionDate, manufactureName, address, country, city, pincode, tacId,
              plantInspectionReportNumber, testReportNumber, packModel, remark, createdAt)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.get("id"), payload.get("user"), payload.get("inspectionDate"),
                payload.get("manufactureName"), payload.get("address"), payload.get("country"),
                payload.get("city"), payload.get("pincode"), payload.get("tacId"),
                payload.get("plantInspectionReportNumber"), payload.get("testReportNumber"),
                payload.get("packModel"), payload.get("remark"), payload.get("createdAt")
            )
        )
        conn.commit()
    finally:
        conn.close()

def query_reports(filters):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        where = []
        params = []
        def add_like(col, key):
            v = (filters.get(key) or "").strip()
            if v:
                where.append(f"{col} LIKE ?")
                params.append(f"%{v}%")
        add_like("tacId", "tacId")
        add_like("plantInspectionReportNumber", "plantInspectionReportNumber")
        add_like("testReportNumber", "testReportNumber")
        add_like("packModel", "packModel")
        sql = "SELECT * FROM reports"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY createdAt DESC"
        cur = conn.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]
        return rows
    finally:
        conn.close()

def stats():
    conn = sqlite3.connect(DB_PATH)
    try:
        tac_count = conn.execute("SELECT COUNT(DISTINCT tacId) FROM reports WHERE tacId IS NOT NULL AND TRIM(tacId) <> ''").fetchone()[0]
        test_count = conn.execute("SELECT COUNT(*) FROM reports WHERE testReportNumber IS NOT NULL AND TRIM(testReportNumber) <> ''").fetchone()[0]
        return {"tacIssued": int(tac_count or 0), "testReportIssued": int(test_count or 0)}
    finally:
        conn.close()

class Handler(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/health":
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            return
        if parsed.path == "/api/reports":
            qs = urllib.parse.parse_qs(parsed.query)
            filters = {k: (qs.get(k, [""])[0] or "") for k in ["tacId", "plantInspectionReportNumber", "testReportNumber", "packModel"]}
            items = query_reports(filters)
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(items).encode("utf-8"))
            return
        if parsed.path == "/api/stats":
            s = stats()
            self.send_response(200)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(s).encode("utf-8"))
            return
        if parsed.path == "/" or parsed.path == "/index.html":
            file_path = ROOT / "index.html"
            if file_path.exists():
                content = file_path.read_bytes()
                self.send_response(200)
                self._cors()
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(content)
                return
        self.send_response(404)
        self._cors()
        self.end_headers()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path == "/api/reports":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body.decode("utf-8"))
            insert_report(payload)
            self.send_response(201)
            self._cors()
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"ok": True}).encode("utf-8"))
            return
        self.send_response(404)
        self._cors()
        self.end_headers()

def main():
    init_db()
    port = int(os.environ.get("PORT", "5000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"Server running at http://localhost:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
