"""
Device Code Flow implementation for OAuth 2.0 device authorization grant (RFC 8628).
"""

import json
import time
from typing import Dict
from typing import Optional

import requests
from pydantic import BaseModel

from anaconda_auth.client import BaseClient
from anaconda_auth.config import AnacondaAuthSite
from anaconda_auth.exceptions import DeviceFlowDenied
from anaconda_auth.exceptions import DeviceFlowError
from anaconda_auth.exceptions import DeviceFlowTimeout


class DeviceAuthorizationResponse(BaseModel):
    device_code: str
    user_code: str
    verification_uri: str
    verification_uri_complete: str
    expires_in: int = 60
    interval: int = 5


class DeviceCodeFlow:
    """
    OAuth 2.0 Device Code Flow implementation.

    This implements RFC 8628 for devices that are either browserless
    or have limited input capabilities.
    """

    config: AnacondaAuthSite
    authorize_response: Optional[DeviceAuthorizationResponse]

    def __init__(self, config: AnacondaAuthSite):
        """
        Initialize device code flow.

        Args:
            config: Configuration for the client
        """
        self.config = config
        self.client = BaseClient(site=config)

        # Device authorization response data
        self.authorize_response = None

    def initiate_device_authorization(self) -> DeviceAuthorizationResponse:
        """
        Initiate device authorization request.

        Returns:
            Tuple of (user_code, verification_uri) to display to user
        """

        data = {"client_id": self.config.client_id, "scope": "openid"}

        if self.config.oidc.device_authorization_endpoint is None:
            raise DeviceFlowError("Server does not support device authorization")

        try:
            response = self.client.post(
                self.config.oidc.device_authorization_endpoint,
                data=data,
                verify=self.config.ssl_verify,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()

            auth_response = response.json()

            self.authorize_response = DeviceAuthorizationResponse(**auth_response)
            return self.authorize_response

        except requests.RequestException as e:
            raise DeviceFlowError(f"Device authorization request failed: {e}")
        except KeyError as e:
            raise DeviceFlowError(f"Missing required field in response: {e}")

    def poll_for_token(self) -> Dict[str, str]:
        """
        Poll the token endpoint until authorization is complete.

        Returns:
            Token response containing access_token, etc.
        """
        if not self.authorize_response:
            raise DeviceFlowError("Must call initiate_device_authorization first")

        start_time = time.time()
        expires_in = self.authorize_response.expires_in
        interval = self.authorize_response.interval

        while time.time() - start_time < expires_in:
            try:
                token_response = self._request_token()
                return token_response

            except DeviceFlowTimeout:
                raise
            except DeviceFlowDenied:
                raise
            except DeviceFlowError as e:
                # Check for authorization_pending
                if "authorization_pending" in str(e).lower():
                    time.sleep(interval)
                    continue
                elif "slow_down" in str(e).lower():
                    # Server asked us to slow down
                    interval = min(interval + 5, 30)
                    time.sleep(interval)
                    continue
                else:
                    raise

        raise DeviceFlowTimeout("Device authorization timed out")

    def _request_token(self) -> Dict[str, str]:
        """Make a single token request."""
        if not self.authorize_response:
            raise DeviceFlowError("Must call initiate_device_authorization first")

        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "device_code": self.authorize_response.device_code,
            "client_id": self.config.client_id,
        }

        response = self.client.post(
            self.config.oidc.token_endpoint,
            data=data,
            verify=self.config.ssl_verify,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code == 200:
            return response.json()

        # Handle error responses
        try:
            error_data = response.json()
            error_code = error_data.get("error", "unknown_error")
            error_description = error_data.get("error_description", "")

            if error_code == "authorization_pending":
                raise DeviceFlowError("authorization_pending")
            elif error_code == "slow_down":
                raise DeviceFlowError("slow_down")
            elif error_code == "expired_token":
                raise DeviceFlowTimeout("Device code expired")
            elif error_code == "access_denied":
                raise DeviceFlowDenied("User denied authorization")
            else:
                raise DeviceFlowError(
                    f"Token request failed: {error_code} - {error_description}"
                )

        except json.JSONDecodeError:
            response.raise_for_status()

        raise DeviceFlowError("Token request failed")
