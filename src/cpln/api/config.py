from dataclasses import asdict, dataclass

from ..constants import (
    DEFAULT_CPLN_API_URL,
    DEFAULT_CPLN_API_VERSION,
    DEFAULT_TIMEOUT_SECONDS,
)


@dataclass
class APIConfig:
    """
    Configuration class for the Control Plane API client.

    This class holds the configuration parameters needed to interact with the Control Plane API,
    including authentication details, organization information, and API settings.

    Args:
        token (str): Authorization token for accessing the API
        org (str): Organization name in Control Plane
        base_url (str, optional): Base URL for the Control Plane API. Defaults to DEFAULT_CPLN_API_URL
        version (str, optional): API version to use. Defaults to DEFAULT_CPLN_API_VERSION
        timeout (int, optional): Request timeout in seconds. Defaults to DEFAULT_TIMEOUT_SECONDS
        org_url (str, optional): Organization-specific API URL. Will be automatically set based on base_url and org
    """

    token: str
    org: str
    base_url: str = DEFAULT_CPLN_API_URL
    version: str = DEFAULT_CPLN_API_VERSION
    timeout: int = DEFAULT_TIMEOUT_SECONDS
    org_url: str = None

    def __post_init__(self):
        """
        Post-initialization hook that sets the organization URL.
        """
        if self.org_url is None:
            self.org_url = self.get_org_url()

    def get_org_url(self) -> str:
        """
        Constructs and returns the organization-specific API URL.

        Returns:
            str: The complete URL for the organization's API endpoint
        """
        return f"{self.base_url}/org/{self.org}"

    def asdict(self):
        """
        Converts the configuration object to a dictionary.

        Returns:
            dict: A dictionary containing all configuration parameters
        """
        return asdict(self)
