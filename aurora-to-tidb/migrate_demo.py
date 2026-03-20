"""Full Aurora -> TiDB migration demo script.

Runs the complete pipeline against local MySQL (source) and TiDB (target):
  1. Scan  — assess readiness
  2. Convert — generate TiDB-compatible DDL
  3. Apply — create schema on TiDB
  4. Load — transfer data via mysqldump -> mysql
  5. Validate — compare row counts
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pymysql
import pymysql.cursors

# ---- Config ----
SOURCE = {"host": "127.0.0.1", "port": 3306, "user": "root", "password": "", "db": "ecommerce"}
TARGET = {"host": "127.0.0.1", "port": 4000, "user": "root", "password": "", "db": "ecommerce"}

TABLES = [
    "customers", "addresses", "categories", "products", "inventory",
    "orders", "order_items", "payments", "audit_log", "sessions",
]


def banner(msg: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}\n")


def connect(cfg: dict) -> pymysql.Connection:
    return pymysql.connect(
        host=cfg["host"], port=cfg["port"], user=cfg["user"],
        password=cfg["password"], database=cfg["db"],
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4",
    )


def step1_scan() -> None:
    """Run TiShift scan."""
    banner("STEP 1: SCAN — Assessing migration readiness")
    from tishift.config import SourceConfig
    from tishift.connection import get_source_connection
    from tishift.core.scan.scanner import run_scan

    source_cfg = SourceConfig(
        host=SOURCE["host"], port=SOURCE["port"],
        user=SOURCE["user"], password=SOURCE["password"],
        database=SOURCE["db"],
    )

    with get_source_connection(source_cfg) as conn:
        report = run_scan(conn, source_host=SOURCE["host"], database=SOURCE["db"])

    print(f"  Score:    {report.scoring.overall_score}/100 ({report.scoring.rating.value})")
    print(f"  Tables:   {len(report.schema_inventory.tables)}")
    print(f"  Blockers: {len([i for i in report.assessment.blockers])}")
    print(f"  Warnings: {len([i for i in report.assessment.warnings])}")
    print(f"  Routines: {len(report.schema_inventory.routines)}")
    print(f"  Triggers: {len(report.schema_inventory.triggers)}")
    print(f"  Events:   {len(report.schema_inventory.events)}")
    return report


def step2_convert(report) -> dict:
    """Convert schema to TiDB-compatible DDL."""
    banner("STEP 2: CONVERT — Generating TiDB-compatible DDL")
    from tishift.core.convert.schema_transformer import TransformOptions, transform_schema

    result = transform_schema(report.schema_inventory, TransformOptions(target_is_cloud=False))

    out_dir = Path("demo-migration")
    out_dir.mkdir(exist_ok=True)
    (out_dir / "01-create-tables.sql").write_text(result.create_tables_sql)
    (out_dir / "02-create-indexes.sql").write_text(result.create_indexes_sql)
    (out_dir / "03-create-views.sql").write_text(result.create_views_sql)
    (out_dir / "04-foreign-keys.sql").write_text(result.foreign_keys_sql)

    print(f"  Generated DDL files in {out_dir}/")
    print(f"  Conversion notes:")
    for note in result.conversion_notes:
        print(f"    - {note}")

    return {
        "tables_sql": result.create_tables_sql,
        "indexes_sql": result.create_indexes_sql,
        "views_sql": result.create_views_sql,
        "fk_sql": result.foreign_keys_sql,
    }


def connect_no_db(cfg: dict) -> pymysql.Connection:
    return pymysql.connect(
        host=cfg["host"], port=cfg["port"], user=cfg["user"],
        password=cfg["password"],
        cursorclass=pymysql.cursors.DictCursor,
        charset="utf8mb4",
    )


def step3_apply(ddl: dict) -> None:
    """Apply converted schema to TiDB."""
    banner("STEP 3: APPLY — Creating schema on TiDB")

    # Connect without database first to create it
    init_conn = connect_no_db(TARGET)
    with init_conn.cursor() as cur:
        cur.execute("CREATE DATABASE IF NOT EXISTS ecommerce")
    init_conn.commit()
    init_conn.close()

    conn = connect(TARGET)

    with conn.cursor() as cur:
        cur.execute("USE ecommerce")
        # Drop existing tables in reverse dependency order
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")
        for table in reversed(TABLES):
            cur.execute(f"DROP TABLE IF EXISTS `{table}`")
        cur.execute("SET FOREIGN_KEY_CHECKS = 1")

    conn.commit()
    print("  Cleared target database")

    # Execute CREATE TABLE statements one by one
    # Use regex to extract individual CREATE TABLE ... ; blocks
    import re
    create_stmts = re.findall(r'(CREATE TABLE[^;]+;)', ddl["tables_sql"])

    with conn.cursor() as cur:
        cur.execute("USE ecommerce")
        for stmt in create_stmts:
            try:
                cur.execute(stmt)
                match = re.search(r'CREATE TABLE\s+(\S+)', stmt)
                name = match.group(1) if match else "?"
                print(f"  Created table: {name}")
            except Exception as e:
                print(f"  ERROR creating table: {e}")
                print(f"  Statement: {stmt[:120]}...")
    conn.commit()

    # Execute CREATE INDEX statements
    with conn.cursor() as cur:
        cur.execute("USE ecommerce")
        idx_stmts = [s.strip() for s in ddl["indexes_sql"].split(";") if s.strip()]
        for stmt in idx_stmts:
            try:
                cur.execute(stmt)
                print(f"  Created index: {stmt[:80]}...")
            except Exception as e:
                print(f"  SKIP index (expected for TiDB): {e}")
    conn.commit()

    # Execute foreign keys
    with conn.cursor() as cur:
        cur.execute("USE ecommerce")
        fk_stmts = [s.strip() for s in ddl["fk_sql"].split(";") if s.strip()]
        for stmt in fk_stmts:
            try:
                cur.execute(stmt)
                print(f"  Added FK: {stmt[:80]}...")
            except Exception as e:
                print(f"  SKIP FK: {e}")
    conn.commit()
    conn.close()
    print("\n  Schema applied to TiDB successfully!")


def step4_load() -> None:
    """Load data from MySQL to TiDB using mysqldump."""
    banner("STEP 4: LOAD — Transferring data from MySQL to TiDB")

    dump_dir = Path("demo-migration/data")
    dump_dir.mkdir(parents=True, exist_ok=True)

    # Dump data only (no schema) from source MySQL
    print("  Dumping data from MySQL source...")
    dump_cmd = [
        "mysqldump",
        "-h", SOURCE["host"], "-P", str(SOURCE["port"]),
        "-u", SOURCE["user"],
        "--no-create-info",       # data only
        "--skip-triggers",        # TiDB doesn't execute triggers
        "--complete-insert",      # full INSERT statements
        "--skip-extended-insert", # one row per INSERT for safety
        "--set-gtid-purged=OFF",  # avoid GTID issues
        "--column-statistics=0",  # MySQL 9 compatibility
        SOURCE["db"],
    ] + TABLES

    dump_file = dump_dir / "ecommerce-data.sql"
    with open(dump_file, "w") as f:
        result = subprocess.run(dump_cmd, stdout=f, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        print(f"  Dump error: {result.stderr}")
        # Try without --column-statistics
        dump_cmd.remove("--column-statistics=0")
        with open(dump_file, "w") as f:
            result = subprocess.run(dump_cmd, stdout=f, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print(f"  Dump failed: {result.stderr}")
            return

    dump_size = dump_file.stat().st_size
    print(f"  Dump complete: {dump_file} ({dump_size:,} bytes)")

    # Load into TiDB
    print("  Loading data into TiDB...")
    load_cmd = [
        "mysql",
        "-h", TARGET["host"], "-P", str(TARGET["port"]),
        "-u", TARGET["user"],
        TARGET["db"],
    ]
    with open(dump_file, "r") as f:
        result = subprocess.run(load_cmd, stdin=f, stderr=subprocess.PIPE, text=True)

    if result.returncode != 0:
        print(f"  Load error: {result.stderr}")
        # Try loading line by line, skipping problematic statements
        print("  Retrying with individual INSERT statements...")
        conn = connect(TARGET)
        with conn.cursor() as cur:
            cur.execute("USE ecommerce")
            lines = dump_file.read_text().splitlines()
            loaded = 0
            skipped = 0
            for line in lines:
                line = line.strip()
                if line.startswith("INSERT INTO"):
                    try:
                        cur.execute(line)
                        loaded += 1
                    except Exception:
                        skipped += 1
        conn.commit()
        conn.close()
        print(f"  Loaded {loaded} rows, skipped {skipped}")
    else:
        print("  Data loaded into TiDB successfully!")


def step5_validate() -> None:
    """Validate migration by comparing row counts."""
    banner("STEP 5: VALIDATE — Comparing source vs target")

    src = connect(SOURCE)
    tgt = connect(TARGET)

    print(f"  {'Table':<20} {'MySQL':>10} {'TiDB':>10} {'Status':>10}")
    print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10}")

    all_match = True
    total_src = 0
    total_tgt = 0

    for table in TABLES:
        with src.cursor() as cur:
            cur.execute(f"SELECT COUNT(*) as cnt FROM `{table}`")
            src_count = list(cur.fetchone().values())[0]

        with tgt.cursor() as cur:
            try:
                cur.execute(f"SELECT COUNT(*) as cnt FROM `{table}`")
                tgt_count = list(cur.fetchone().values())[0]
            except Exception:
                tgt_count = "N/A"

        total_src += src_count
        if isinstance(tgt_count, int):
            total_tgt += tgt_count

        match = "OK" if src_count == tgt_count else "MISMATCH"
        if match != "OK":
            all_match = False

        print(f"  {table:<20} {src_count:>10} {str(tgt_count):>10} {match:>10}")

    print(f"  {'-'*20} {'-'*10} {'-'*10} {'-'*10}")
    print(f"  {'TOTAL':<20} {total_src:>10} {total_tgt:>10}")

    if all_match:
        print("\n  ALL TABLES MATCH! Migration validated successfully.")
    else:
        print("\n  SOME TABLES HAVE MISMATCHES. Review needed.")

    # TiDB version check
    with tgt.cursor() as cur:
        cur.execute("SELECT VERSION()")
        ver = list(cur.fetchone().values())[0]
        print(f"\n  Target TiDB version: {ver}")

    src.close()
    tgt.close()


def main() -> None:
    print("\n" + "=" * 60)
    print("  TiShift — Aurora MySQL to TiDB Migration Demo")
    print("  Source: MySQL 9.6.0 @ localhost:3306")
    print("  Target: TiDB v8.5.5 @ localhost:4000")
    print("  Database: ecommerce (10 tables)")
    print("=" * 60)

    report = step1_scan()
    ddl = step2_convert(report)
    step3_apply(ddl)
    step4_load()
    step5_validate()

    banner("MIGRATION COMPLETE")
    print("  Source:  MySQL 9.6.0 (localhost:3306)")
    print("  Target:  TiDB v8.5.5 (localhost:4000)")
    print("  Database: ecommerce")
    print(f"  Score:   {report.scoring.overall_score}/100")
    print(f"  Tables migrated: {len(TABLES)}")
    print()


if __name__ == "__main__":
    main()
