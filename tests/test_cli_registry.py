from typer.main import get_command
from typer.testing import CliRunner

from matflowkit.cli import app
from matflowkit.menu import MENU
from matflowkit.registry import GROUPS


runner = CliRunner()


def test_registry_matches_cli_and_menu():
    root = get_command(app)
    expected_root = {group.cli_name for group in GROUPS if group.cli_name}
    expected_root.update(
        command.name
        for group in GROUPS
        if group.cli_name is None
        for command in group.commands
    )
    assert set(root.commands) == expected_root

    for group in GROUPS:
        menu_commands = {entry[0] for entry in MENU[group.menu_key][1]}
        expected_commands = {command.name for command in group.commands}
        assert menu_commands == expected_commands
        if group.cli_name is not None:
            assert set(root.commands[group.cli_name].commands) == expected_commands


def test_every_registered_command_has_working_help():
    for group in GROUPS:
        for command in group.commands:
            arguments = (
                [group.cli_name, command.name, "--help"]
                if group.cli_name
                else [command.name, "--help"]
            )
            result = runner.invoke(app, arguments)
            assert result.exit_code == 0, f"{' '.join(arguments)}\n{result.output}"
