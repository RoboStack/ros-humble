from __future__ import annotations

from datetime import datetime
from uuid import UUID

import typer
from pydantic import BaseModel
from rich.prompt import Confirm
from rich.table import Table

from anaconda_auth.client import BaseClient
from anaconda_auth.token import RepoToken
from anaconda_auth.token import TokenInfo
from anaconda_cli_base import console
from anaconda_cli_base.console import select_from_list

app = typer.Typer(name="token")


class TokenInfoResponse(BaseModel):
    id: UUID
    expires_at: datetime


class TokenCreateResponse(BaseModel):
    token: str
    expires_at: datetime


class OrganizationData(BaseModel):
    id: UUID
    name: str
    title: str


class SubscriptionData(BaseModel):
    org_id: UUID
    product_code: str


class RepoAPIClient(BaseClient):
    def _get_repo_token_info(self, org_name: str) -> TokenInfoResponse | None:
        """Return the token information, if it exists.

        Args:
            org_name: The name of the organization.

        Returns:
            The token information, including its id and expiration date, or
            None if a token doesn't exist.
        """
        response = self.get(
            f"/api/organizations/{org_name}/ce/current-token",
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return TokenInfoResponse(**response.json())

    def _create_repo_token(self, org_name: str) -> TokenCreateResponse:
        """Create a new repo token.

        Args:
            org_name: The name of the organization.

        Returns:
            The token information, including its value and expiration date.
        """
        response = self.put(
            f"/api/organizations/{org_name}/ce/current-token",
            json={"confirm": "yes"},
        )
        return TokenCreateResponse(**response.json())

    def issue_new_token(self, org_name: str, yes: bool = False) -> str:
        """Issue a new repository token from anaconda.com."""
        existing_token_info = self._get_repo_token_info(org_name=org_name)

        if existing_token_info is not None and not yes:
            console.print(
                f"An existing token already exists for the organization [cyan]{org_name}[/cyan]."
            )
            console.print(
                "Reissuing a new token will revoke and deactivate any existing token access. This action can't be undone."
            )
            should_continue = Confirm.ask("Proceed?", default=False)
            if not should_continue:
                raise typer.Abort()

        response = self._create_repo_token(org_name=org_name)

        console.print(
            f"Your conda token has been installed and expires [cyan]{response.expires_at}[/cyan]. To view your token(s), you can use [cyan]anaconda token list[/cyan]"
        )
        return response.token

    def get_organizations_for_user(self) -> list[OrganizationData]:
        """Get a list of all organizations the user belongs to."""
        response = self.get("/api/organizations/my")
        response.raise_for_status()
        data = response.json()
        return [OrganizationData(**item) for item in data]

    def get_business_organizations_for_user(self) -> list[OrganizationData]:
        """Get a list of all organizations the user belongs to that have a Business subscription."""
        organizations = self.get_organizations_for_user()
        subscriptions = [
            SubscriptionData(**sub) for sub in self.account.get("subscriptions", [])
        ]
        business_subscription_org_ids = [
            sub.org_id for sub in subscriptions if "starter" not in sub.product_code
        ]
        return [org for org in organizations if org.id in business_subscription_org_ids]


def _print_repo_token_table(
    tokens: list[RepoToken], legacy_tokens: dict[str, str]
) -> None:
    table = Table(title="Anaconda Repository Tokens", title_style="green")

    table.add_column("Organization")
    table.add_column("Channel URL")
    table.add_column("Token")

    from anaconda_auth._conda.repo_config import REPO_URL

    for repo_token in tokens:
        channel_url = f"{REPO_URL}{repo_token.org_name}/*"
        table.add_row(repo_token.org_name, channel_url, repo_token.token)

    for url, token in legacy_tokens.items():
        table.add_row(None, url, token)

    console.print(table)


def _select_org_name(client: RepoAPIClient) -> str:
    organizations = client.get_business_organizations_for_user()

    if not organizations:
        console.print("No organizations found.")
        raise typer.Abort()

    if len(organizations) == 1:
        org_name = organizations[0].name
        console.print(
            f"Only one organization found, automatically selecting: {org_name}"
        )
        return org_name

    name_map = {}
    choices = []
    for org in organizations:
        key = f"{org.title} ([cyan]{org.name}[/cyan])"
        name_map[key] = org.name
        choices.append(key)

    org_title = select_from_list(
        "Please select an organization:",
        choices=choices,
    )
    return name_map[org_title]


@app.callback(invoke_without_command=True, no_args_is_help=True)
def main() -> None:
    """Manage your Anaconda repo tokens."""


@app.command(name="list")
def list_tokens() -> None:
    """List all installed repository tokens."""
    from anaconda_auth._conda.repo_config import token_list

    tokens = token_list()

    token_info = TokenInfo.load(create=True)
    repo_tokens = token_info.repo_tokens

    if not (tokens or repo_tokens):
        console.print(
            "No repo tokens are installed. Run [cyan]anaconda token install[/cyan]."
        )
        raise typer.Abort()

    _print_repo_token_table(tokens=repo_tokens, legacy_tokens=tokens)


@app.command(name="install")
def install_token(
    token: str = typer.Argument(
        "", help="Optionally, provide the token received via email or web interface."
    ),
    org_name: str = typer.Option("", "-o", "--org", help="Organization name (slug)."),
    set_default_channels: bool = typer.Option(
        True, help="Automatically configure default channels."
    ),
    yes: bool = typer.Option(False, "-y", "--yes", help="Accept all prompts"),
) -> None:
    """Create and install a new repository token."""
    client = RepoAPIClient()

    if not org_name:
        org_name = _select_org_name(client)

    if not token:
        token = client.issue_new_token(org_name=org_name, yes=yes)

    from anaconda_auth._conda import repo_config

    try:
        repo_config.validate_token(token, no_ssl_verify=False)
    except repo_config.CondaTokenError as e:
        raise typer.Abort(e)

    token_info = TokenInfo.load(create=True)
    token_info.set_repo_token(org_name, token)
    token_info.save()

    msg = "Your token has been installed and validated"

    if set_default_channels:
        repo_config.configure_default_channels(force=yes)
        msg += ", and conda has been configured"

    console.print(f"Success! {msg}.")


@app.command(name="config")
def configure_conda(
    force: bool = typer.Option(
        False, help="Force configuration of default channels without prompt."
    ),
) -> None:
    """Configure conda's default channels to access Anaconda's premium repository."""
    from anaconda_auth._conda import repo_config

    repo_config.configure_default_channels(force=force)


@app.command(name="uninstall")
def uninstall_token(
    org_name: str = typer.Option("", "-o", "--org"),
    all: bool = typer.Option(False, "-a", "--all"),
) -> None:
    """Uninstall a repository token for a specific organization."""

    token_info = TokenInfo.load()
    if all:
        token_info.delete_all_repo_token()
        token_info.save()
        console.print("Successfully deleted [cyan]all[/cyan] repo tokens.")
        return

    if not org_name:
        # TODO: We should try to load this dynamically and present a picker
        console.print("Must explicitly provide an [cyan]--org[/cyan] option")
        raise typer.Abort()

    token_info.delete_repo_token(org_name=org_name)
    token_info.save()

    console.print(
        f"Successfully deleted token for organization: [cyan]{org_name}[/cyan]"
    )


@app.command(name="set")
def set_token(
    token: str = typer.Argument(
        ..., help="Optionally, provide the token received via email or web interface."
    ),
    org_name: str = typer.Option("", "-o", "--org", help="Organization name (slug)."),
    set_default_channels: bool = typer.Option(
        True, help="Automatically configure default channels."
    ),
    file: str = typer.Option(
        "", "-f", "--file", help="Write to the system .condarc file at '~/.condarc'."
    ),
    env: bool = typer.Option(
        False,
        "-e",
        "--env",
        help="Write to the active conda environment .condarc file. If no environment is active, write to the user config file (~/.condarc).",
    ),
    system: bool = typer.Option(
        True, "-s", "--system", help="Organization name (slug)."
    ),
) -> None:
    """Install a new repository token."""
    if org_name:
        install_token(
            token=token, org_name=org_name, set_default_channels=set_default_channels
        )
    from anaconda_auth._conda import repo_config

    repo_config.token_set(token=token, file=file, env=env, system=system)


@app.command(name="remove")
def remove_token(
    file: str = typer.Option(
        "", "-f", "--file", help="Write to the system .condarc file at '~/.condarc'."
    ),
    env: bool = typer.Option(
        False,
        "-e",
        "--env",
        help="Write to the active conda environment .condarc file. If no environment is active, write to the user config file (~/.condarc).",
    ),
    system: bool = typer.Option(
        True, "-s", "--system", help="Organization name (slug)."
    ),
) -> None:
    """Remove binstar token and data from Keyring."""
    from anaconda_auth._conda import repo_config

    repo_config.token_remove(file=file, env=env, system=system)
