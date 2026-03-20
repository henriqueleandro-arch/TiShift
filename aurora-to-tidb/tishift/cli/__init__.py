"""CLI interface — Click commands and Rich formatting."""

import click

from tishift.cli.scan_cmd import scan_command
from tishift.cli.convert_cmd import convert_command
from tishift.cli.load_cmd import load_command
from tishift.cli.sync_cmd import sync_command
from tishift.cli.check_cmd import check_command
from tishift.cli.feedback_cmd import feedback_command


@click.group()
@click.version_option(package_name="tishift")
def main() -> None:
    """TiShift — Aurora MySQL to TiDB migration toolkit."""


main.add_command(scan_command, name="scan")
main.add_command(convert_command, name="convert")
main.add_command(load_command, name="load")
main.add_command(sync_command, name="sync")
main.add_command(check_command, name="check")
main.add_command(feedback_command, name="feedback")
