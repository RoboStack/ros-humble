import logging
import uuid
import warnings
import webbrowser
from typing import Optional
from typing import Union
from urllib.parse import urlencode

import pkce

from anaconda_auth import __version__
from anaconda_auth.client import BaseClient
from anaconda_auth.config import AnacondaAuthConfig
from anaconda_auth.config import AnacondaAuthSite
from anaconda_auth.device_flow import DeviceCodeFlow
from anaconda_auth.exceptions import AuthenticationError
from anaconda_auth.exceptions import DeviceFlowError
from anaconda_auth.exceptions import TokenNotFoundError
from anaconda_auth.handlers import capture_auth_code
from anaconda_auth.token import TokenInfo
from anaconda_cli_base.console import console

logger = logging.getLogger(__name__)


def make_auth_code_request_url(
    code_challenge: str, state: str, config: Optional[AnacondaAuthSite] = None
) -> str:
    """Build the authorization code request URL."""

    if config is None:
        config = AnacondaAuthConfig()

    authorization_endpoint = config.oidc.authorization_endpoint
    client_id = config.client_id
    redirect_uri = config.redirect_uri

    params = dict(
        client_id=client_id,
        response_type="code",
        scope="openid email profile offline_access",
        state=state,
        redirect_uri=redirect_uri,
        code_challenge=code_challenge,
        code_challenge_method="S256",
    )
    encoded_params = urlencode(params)
    url = f"{authorization_endpoint}?{encoded_params}"

    return url


def _send_auth_code_request(
    code_challenge: str, state: str, config: AnacondaAuthSite
) -> None:
    """Open the authentication flow in the browser."""
    url = make_auth_code_request_url(code_challenge, state, config)
    webbrowser.open(url)


def refresh_access_token(refresh_token: str, config: AnacondaAuthSite) -> str:
    """Refresh and save the tokens."""
    client = BaseClient(site=config)
    response = client.post(
        config.oidc.token_endpoint,
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": config.client_id,
        },
        auth=False,  # type: ignore
    )
    response.raise_for_status()
    response_data = response.json()

    access_token = response_data["access_token"]
    return access_token


def request_access_token(
    auth_code: str, code_verifier: str, config: AnacondaAuthSite
) -> str:
    """Request an access token using the provided authorization code and code verifier."""
    token_endpoint = config.oidc.token_endpoint
    client_id = config.client_id
    redirect_uri = config.redirect_uri

    client = BaseClient(site=config)
    response = client.post(
        token_endpoint,
        data=dict(
            grant_type="authorization_code",
            client_id=client_id,
            code=auth_code,
            redirect_uri=redirect_uri,
            code_verifier=code_verifier,
        ),
        auth=False,  # type: ignore
    )
    result = response.json()

    if "error" in result:
        raise AuthenticationError(
            f"Error getting JWT: {result.get('error')} - {result.get('error_description')}"
        )

    access_token = result.get("access_token")
    return access_token


def _do_device_flow(config: Optional[AnacondaAuthSite] = None) -> str:
    """Login using OAuth 2.0 device code flow."""
    config = config or AnacondaAuthConfig()

    # Initialize device flow
    device_flow = DeviceCodeFlow(config=config)

    # Step 1: Initiate device authorization
    device_authorization = device_flow.initiate_device_authorization()

    # Step 2: Display instructions to user
    console.print(
        "Attempting to automatically open the authorization page in your default browser."
    )
    console.print(
        "If the browser does not open or you wish to use a different device to authorize this request, open the following URL:"
    )
    console.print()
    console.print(device_authorization.verification_uri)
    console.print()
    console.print("Then enter the code:")
    console.print()
    console.print(device_authorization.user_code)
    console.print()

    # Try to open browser automatically
    try:
        webbrowser.open(device_authorization.verification_uri_complete)
    except Exception:
        pass

    status = console.status("Waiting for authorization (CTRL-C to cancel)")

    try:
        # Step 3: Poll for token
        status.start()
        token_response = device_flow.poll_for_token()
        status.stop()
        console.print("✓ Login successful!")
        # return access token
        return token_response["access_token"]
    except KeyboardInterrupt:
        status.stop()
        raise
    except DeviceFlowError:
        status.stop()
        raise


def _do_auth_flow(config: Optional[AnacondaAuthSite] = None) -> str:
    """Do the browser-based auth flow and return the short-lived access_token and id_token tuple."""
    config = config or AnacondaAuthConfig()

    state = str(uuid.uuid4())
    code_verifier, code_challenge = pkce.generate_pkce_pair(code_verifier_length=128)

    _send_auth_code_request(code_challenge, state, config)

    # Listen for the response
    auth_code = capture_auth_code(config.redirect_uri, state=state, config=config)
    logger.debug("Authentication successful! Getting JWT token.")

    # Do auth code exchange
    return request_access_token(auth_code, code_verifier, config)


def _login_with_username(config: Optional[AnacondaAuthSite] = None) -> str:
    """Prompt for username and password and log in with the password grant flow."""
    warnings.warn(
        "Basic login with username/password is deprecated and will be disabled soon.",
        UserWarning,
        stacklevel=0,
    )

    if config is None:
        config = AnacondaAuthConfig()

    username = console.input("Please enter your email: ")
    password = console.input("Please enter your password: ", password=True)

    client = BaseClient(site=config)
    response = client.post(
        config.oidc.token_endpoint,
        data={
            "grant_type": "password",
            "username": username,
            "password": password,
        },
        auth=False,  # type: ignore
    )
    response_data = response.json()
    response.raise_for_status()

    access_token = response_data["access_token"]
    return access_token


def _do_login(config: AnacondaAuthSite, basic: bool) -> None:
    if basic:
        access_token = _login_with_username(config=config)
    elif config.use_device_flow:
        access_token = _do_device_flow(config=config)
    else:
        access_token = _do_auth_flow(config=config)

    api_key = get_api_key(
        access_token,
        config=config,
    )

    token_info = TokenInfo(api_key=api_key, domain=config.domain)
    token_info.save()


def get_api_key(
    access_token: str,
    config: Optional[AnacondaAuthSite] = None,
) -> str:
    config = config or AnacondaAuthConfig()
    client = BaseClient(site=config)

    headers = {"Authorization": f"Bearer {access_token}"}

    aau_token = config.aau_token
    if aau_token is not None:
        headers["X-AAU-CLIENT"] = aau_token

    # Retry logic until we stabilize on new API
    urls = [
        f"https://{config.auth_domain}/api/auth/api-keys",
        f"https://{config.domain}/api/iam/api-keys",
    ]
    for url in urls:
        response = client.post(
            url,
            json=dict(
                scopes=["cloud:read", "cloud:write", "repo:read"],
                tags=[f"anaconda-auth/v{__version__}"],
            ),
            headers=headers,
            auth=False,  # type: ignore
        )
        if response.status_code == 201:
            break
    else:
        console.print("Error retrieving an API key")
        raise AuthenticationError
    return response.json()["api_key"]


def _api_key_is_valid(config: AnacondaAuthSite) -> bool:
    try:
        valid = not TokenInfo.load(config.domain).expired
    except TokenNotFoundError:
        valid = False

    return valid


def _get_config(
    site: Optional[Union[str, AnacondaAuthSite]] = None,
) -> AnacondaAuthSite:
    # Prepare the requested or default site config
    if isinstance(site, AnacondaAuthSite):
        config = site
    elif site:
        config = AnacondaAuthConfig(site=site)
    else:
        config = AnacondaAuthConfig()

    return config


def _site_or_config(
    site: Optional[Union[str, AnacondaAuthSite]] = None,
    config: Optional[AnacondaAuthSite] = None,
) -> AnacondaAuthSite:
    if config and site is not None:
        raise ValueError("You cannot set both site= and config= arguments")

    if config:
        warnings.warn(
            "The config= keyword argument is deprecated, please use site=str | AnacondaAuthSite",
            DeprecationWarning,
        )
        return config
    else:
        return _get_config(site)


def login(
    site: Optional[Union[str, AnacondaAuthSite]] = None,
    ssl_verify: Optional[Union[bool, str]] = None,
    basic: bool = False,
    force: bool = False,
    *,
    config: Optional[AnacondaAuthSite] = None,
) -> None:
    """Log into Anaconda Platform and store the token information in the keyring."""
    site_config = _site_or_config(site=site, config=config)

    if ssl_verify is not None:
        site_config = site_config.model_copy(
            update={"ssl_verify": ssl_verify}, deep=True
        )

    if force or not _api_key_is_valid(config=site_config):
        _do_login(config=site_config, basic=basic)


def logout(
    site: Optional[Union[str, AnacondaAuthSite]] = None,
    *,
    config: Optional[AnacondaAuthSite] = None,
) -> None:
    """Log out of Anaconda Platform."""
    site_config = _site_or_config(site=site, config=config)

    try:
        token_info = TokenInfo.load(domain=site_config.domain)
        token_info.delete()
    except TokenNotFoundError:
        pass

    if site_config.domain != "anaconda.com":
        # Since anaconda.com is the default, don't do anything special if
        # User explicitly overrode the configured domain.
        return

    # If the request was for anaconda.com (the default), also remove
    # anaconda.cloud if it exists. This is just an edge case for the
    # likely rare scenario where a user has a stored token for both
    # domains.
    try:
        token_info = TokenInfo.load(domain="anaconda.cloud")
        token_info.delete()
    except TokenNotFoundError:
        pass


def is_logged_in(site: Optional[Union[str, AnacondaAuthSite]] = None) -> bool:
    if isinstance(site, AnacondaAuthSite):
        config = site
    else:
        config = AnacondaAuthConfig(site=site)

    try:
        token_info = TokenInfo.load(domain=config.domain)
    except TokenNotFoundError:
        token_info = None

    return token_info is not None
