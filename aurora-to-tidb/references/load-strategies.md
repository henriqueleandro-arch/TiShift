# Data Loading Strategies

This reference is loaded by the SKILL.md during Phase 6 (Load Data).
The strategy is selected based on total data size from the Phase 2.5 checklist.

## Strategy Selection

```
IF total_data_mb < 102400 THEN                                          # < 100 GB
    strategy = "direct"
ELSE IF total_data_mb < 1048576 THEN                                    # 100 GB - 1 TB
    strategy = "dms"
ELSE IF $DEPLOYMENT_TARGET = "cloud" AND total_data_mb >= 1048576 THEN  # >= 1 TB, Cloud
    strategy = "cloud_import"
ELSE                                                                     # >= 1 TB, self-hosted
    strategy = "lightning"
```

---

## Strategy 1: Direct Loading (< 100 GB)

Best for small-to-medium databases. Uses mysqldump for export and mysql client for import.
Simple, no extra infrastructure needed.

**Step 1 — Create schema on target first:**
Run the converted DDL files from Phase 5 against the target:
```
mysql -h $TARGET_HOST -P $TARGET_PORT -u $TARGET_USER $DB < 01-create-tables.sql
```

**Step 2 — Drop secondary indexes on target (speeds up load 3-5x):**
```
mysql -h $TARGET_HOST -P $TARGET_PORT -u $TARGET_USER -e "SELECT CONCAT('ALTER TABLE ', table_name, ' DROP INDEX ', index_name, ';') FROM information_schema.statistics WHERE table_schema='$DB' AND index_name != 'PRIMARY' GROUP BY table_name, index_name"
```
Save the output, then run the generated DROP INDEX statements.

**Step 3 — Dump source data (schema excluded, data only):**
```
mysqldump -h $SOURCE_HOST -P $SOURCE_PORT -u $SOURCE_USER --single-transaction --set-gtid-purged=OFF --no-tablespaces --no-create-info $DB > data-dump.sql
```

**Step 4 — Load into target:**
```
mysql -h $TARGET_HOST -P $TARGET_PORT -u $TARGET_USER $DB < data-dump.sql
```

**Step 5 — Recreate secondary indexes:**
```
mysql -h $TARGET_HOST -P $TARGET_PORT -u $TARGET_USER $DB < 02-create-indexes.sql
```

**Step 6 — Add foreign keys:**
```
mysql -h $TARGET_HOST -P $TARGET_PORT -u $TARGET_USER $DB < 04-foreign-keys.sql
```

**Error recovery:** If Step 4 fails mid-load, truncate the partially loaded tables and retry.
mysqldump with `--single-transaction` ensures a consistent snapshot even if the source is active.

---

## Strategy 2: AWS DMS (100 GB - 1 TB)

Best for medium-to-large databases. AWS Database Migration Service handles the transfer
with built-in monitoring, error handling, and optional CDC for ongoing replication.

**Prerequisites:**
- AWS DMS replication instance (recommend `dms.r5.xlarge` or larger)
- Source and target endpoints configured in DMS
- Security groups allowing DMS instance to reach both databases
- Source must have `binlog_format=ROW` if CDC is needed later

**Step 1 — Create DMS replication instance:**
```
aws dms create-replication-instance \
  --replication-instance-identifier tishift-migration \
  --replication-instance-class dms.r5.xlarge \
  --allocated-storage 100 \
  --no-multi-az
```

**Step 2 — Create source endpoint:**
```
aws dms create-endpoint \
  --endpoint-identifier aurora-source \
  --endpoint-type source \
  --engine-name mysql \
  --server-name $SOURCE_HOST \
  --port $SOURCE_PORT \
  --username $SOURCE_USER \
  --password $SOURCE_PASS \
  --database-name $DB
```

**Step 3 — Create target endpoint:**
```
aws dms create-endpoint \
  --endpoint-identifier tidb-target \
  --endpoint-type target \
  --engine-name mysql \
  --server-name $TARGET_HOST \
  --port $TARGET_PORT \
  --username $TARGET_USER \
  --password $TARGET_PASS \
  --database-name $DB
```

**Step 4 — Test connections:**
```
aws dms test-connection --replication-instance-arn $REP_INSTANCE_ARN --endpoint-arn $SOURCE_ARN
aws dms test-connection --replication-instance-arn $REP_INSTANCE_ARN --endpoint-arn $TARGET_ARN
```

**Step 5 — Create and start migration task (full load):**
```
aws dms create-replication-task \
  --replication-task-identifier tishift-full-load \
  --source-endpoint-arn $SOURCE_ARN \
  --target-endpoint-arn $TARGET_ARN \
  --replication-instance-arn $REP_INSTANCE_ARN \
  --migration-type full-load \
  --table-mappings '{"rules":[{"rule-type":"selection","rule-id":"1","rule-name":"include-all","object-locator":{"schema-name":"'$DB'","table-name":"%"},"rule-action":"include"}]}' \
  --replication-task-settings '{"TargetMetadata":{"BatchApplyEnabled":true},"FullLoadSettings":{"MaxFullLoadSubTasks":8}}'
```

**Step 6 — Monitor progress:**
```
aws dms describe-replication-tasks --filters Name=replication-task-arn,Values=$TASK_ARN --query 'ReplicationTasks[0].{Status:Status,Progress:ReplicationTaskStats.FullLoadProgressPercent}'
```

**Error recovery:** DMS tracks table-level progress. If the task fails, check the task log in CloudWatch,
fix the issue, and resume — DMS will pick up from the last completed table.

**Cost note:** DMS replication instances are billed hourly. Delete the instance after migration completes.

---

## Strategy 3: TiDB Lightning (>= 1 TB)

Best for large databases. TiDB Lightning's physical import mode writes SST files directly
to TiKV, bypassing the SQL layer entirely. This is 5-10x faster than SQL-based loading
but requires the target cluster to be offline during import.

**Prerequisites:**
- TiDB Lightning binary installed on a machine with fast disk (SSD recommended)
- Network access to both PD and TiKV nodes (not just the TiDB SQL port)
- Target TiDB cluster should be idle — physical import mode takes exclusive access
- Data exported as CSV or SQL dump files

**Step 1 — Export source data as CSV (faster than SQL dump for Lightning):**
```
mysqldump -h $SOURCE_HOST -P $SOURCE_PORT -u $SOURCE_USER \
  --single-transaction --set-gtid-purged=OFF --no-tablespaces \
  --tab=/data/export --fields-terminated-by=',' --fields-enclosed-by='"' \
  --lines-terminated-by='\n' $DB
```
Or use `tidb-lightning`'s built-in mydumper mode:
```
dumpling -h $SOURCE_HOST -P $SOURCE_PORT -u $SOURCE_USER -p $SOURCE_PASS \
  --filetype csv --threads 16 --output /data/export --database $DB
```

**Step 2 — Create Lightning configuration (`tidb-lightning.toml`):**
```toml
[lightning]
level = "info"
file = "tidb-lightning.log"

[tikv-importer]
backend = "local"                        # Physical import mode
sorted-kv-dir = "/data/sorted-kv"       # Temp directory — needs 2x data size free

[mydumper]
data-source-dir = "/data/export"         # Path to exported CSV/SQL files

[tidb]
host = "$TARGET_HOST"
port = $TARGET_PORT
user = "$TARGET_USER"
password = "$TARGET_PASS"

[checkpoint]
enable = true                            # Enables resume after failure
driver = "file"
dsn = "/data/lightning-checkpoint.pb"
```

**Step 3 — Run TiDB Lightning:**
```
tidb-lightning -config tidb-lightning.toml
```

**Step 4 — Post-import: recreate indexes and analyze tables:**
Lightning creates tables and loads data, but statistics need refreshing:
```
mysql -h $TARGET_HOST -P $TARGET_PORT -u $TARGET_USER -e "ANALYZE TABLE $DB.$TABLE_NAME"
```
Run ANALYZE for each table, or use:
```
mysql -h $TARGET_HOST -P $TARGET_PORT -u $TARGET_USER -e "SELECT CONCAT('ANALYZE TABLE ', table_schema, '.', table_name, ';') FROM information_schema.tables WHERE table_schema='$DB' AND table_type='BASE TABLE'"
```

**Error recovery:** With `checkpoint.enable = true`, Lightning saves progress. If it fails mid-import,
fix the issue and re-run the same command — it resumes from the last checkpoint automatically.

**Performance tips:**
- Use SSD for `sorted-kv-dir` — this is the bottleneck
- Allocate 2x the data size for temporary sorted KV storage
- Use Dumpling (not mysqldump) for parallel CSV export — 4-8x faster
- After import completes, run `ADMIN CHECK TABLE` to verify data integrity

---

## Strategy 4: TiDB Cloud Import (>= 1 TB, Cloud target)

Best for large databases migrating to TiDB Cloud. Uses TiDB Cloud's built-in Import
feature to ingest data directly from S3 — no Lightning binary, no TiKV access,
no cluster downtime.

**Prerequisites:**
- TiDB Cloud cluster (Dedicated tier for >= 1 TB imports)
- Data exported to S3 as CSV or SQL dump files
- IAM role or access key granting TiDB Cloud read access to the S3 bucket
- `ticloud` CLI installed (optional, for automation)

**Step 1 — Export source data to S3 using Dumpling:**
```
dumpling -h $SOURCE_HOST -P $SOURCE_PORT -u $SOURCE_USER -p $SOURCE_PASS \
  --filetype csv --threads 16 --output s3://$BUCKET/$PREFIX --database $DB
```

**Step 2 — Create import task via TiDB Cloud Console:**
- Go to your cluster > Import > Import Data
- Select "Amazon S3" as the data source
- Enter the S3 bucket URI and configure IAM access
- Map source files to target tables
- Start the import

**Step 3 — Or use the ticloud CLI for automation:**
```
ticloud serverless import start \
  --source-type S3 --source-url s3://$BUCKET/$PREFIX \
  --cluster-id $CLUSTER_ID
```

**Step 4 — Monitor progress:**
```
ticloud serverless import describe --import-id $IMPORT_ID
```
Or monitor in the TiDB Cloud Console — progress, throughput, and errors are visible in real-time.

**Step 5 — Post-import verification:**
```
mysql -h $TARGET_HOST -P $TARGET_PORT -u $TARGET_USER -e "ANALYZE TABLE $DB.$TABLE_NAME"
```

**Error recovery:** TiDB Cloud Import tracks progress per file. If the import fails, fix the issue
(usually S3 permissions or file format) and restart — already-imported files are skipped.

**Advantages over TiDB Lightning:**
- No Lightning binary or TiKV/PD infrastructure to set up
- No cluster downtime during import
- Fully managed — progress tracking, automatic retries, error reporting in console
- Direct S3-to-TiDB pipeline with no intermediate storage
- Works with Dedicated and Serverless tiers

**Get started:** https://tidbcloud.com/free-trial — free Starter tier, no credit card required
