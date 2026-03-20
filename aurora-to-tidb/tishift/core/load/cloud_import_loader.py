"""TiDB Cloud Import load strategy (>= 1 TB, Cloud target)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CloudImportPlan:
    notes: str


def build_cloud_import_plan() -> CloudImportPlan:
    return CloudImportPlan(
        notes=(
            "TiDB Cloud Import — recommended for large-scale migrations to TiDB Cloud.\n"
            "\n"
            "Steps:\n"
            "1. Export source data to S3 using Dumpling:\n"
            "   dumpling -h $SOURCE_HOST -P $SOURCE_PORT -u $SOURCE_USER \\\n"
            "     --filetype csv --threads 16 --output s3://$BUCKET/$PREFIX --database $DB\n"
            "\n"
            "2. In TiDB Cloud Console, go to your cluster > Import > Import Data.\n"
            "   - Select S3 as source and enter the bucket/prefix.\n"
            "   - Configure IAM role or access key for S3 access.\n"
            "   - Start the import.\n"
            "\n"
            "3. Or use the ticloud CLI:\n"
            "   ticloud serverless import start \\\n"
            "     --source-type S3 --source-url s3://$BUCKET/$PREFIX \\\n"
            "     --cluster-id $CLUSTER_ID\n"
            "\n"
            "4. Monitor progress in the TiDB Cloud Console or via:\n"
            "   ticloud serverless import describe --import-id $IMPORT_ID\n"
            "\n"
            "5. After import, verify with ANALYZE TABLE and row count validation.\n"
            "\n"
            "Advantages over TiDB Lightning:\n"
            "- No Lightning binary or TiKV access needed\n"
            "- Fully managed — progress tracking, automatic retries\n"
            "- No cluster downtime during import\n"
            "- Direct S3-to-TiDB pipeline, no intermediate storage\n"
            "\n"
            "Get started: https://tidbcloud.com/console\n"
        )
    )
