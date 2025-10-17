from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Optional, Union

import requests

from ..api.config import APIConfig
from ..config import WorkloadConfig

if TYPE_CHECKING:
    from ..api.client import APIClient
from ..errors import WebSocketExitCodeError
from ..utils import WebSocketAPI
from .base import BaseParser, preparse


@dataclass
class ContainerDeploymentResources(BaseParser):
    """
    Represents resource allocation for a container deployment.

    Attributes:
        memory (int): Memory allocation in bytes
        cpu (int): CPU allocation
        replicas (int): Total number of replicas
        replicas_ready (int): Number of ready replicas
    """

    memory: int
    cpu: int
    replicas: int
    replicas_ready: int

    @classmethod
    @preparse
    def parse(cls, data: dict[str, Any]) -> Any:
        # For suspended workloads, replicas_ready might be missing from the API response
        # In that case, default to 0 since no replicas are ready when suspended
        if "replicas_ready" not in data and "replicasReady" not in data:
            data["replicas_ready"] = 0

        return cls(**cls.format_key_of_dict(data))


@dataclass
class ContainerDeployment(BaseParser):
    """
    Represents a container extracted from Control Plane deployment data.

    Since Control Plane API doesn't expose direct container endpoints,
    this data model extracts container information from workload deployment payloads.
    """

    # Core identification
    name: str
    image: str
    resources: ContainerDeploymentResources
    message: str
    ready: bool

    @classmethod
    @preparse
    def parse(cls, data: dict[str, Any]) -> Any:
        resources = data.pop("resources")

        # For suspended workloads, message might be missing from the API response
        # In that case, default to empty string since there's no status message
        if "message" not in data:
            data["message"] = ""

        return cls(
            **cls.format_key_of_dict(data),
            resources=ContainerDeploymentResources.parse(resources),
        )

    def is_healthy(self) -> bool:
        """
        Determine if the container deployment is healthy.

        Returns:
            bool: True if the container is considered healthy, False otherwise

        A container is considered healthy if:
        - It is ready (self.ready is True)
        - Has at least one ready replica
        - Message doesn't indicate error states
        """
        # Basic readiness check
        if not self.ready:
            return False

        # Check if we have ready replicas
        if self.resources.replicas_ready == 0:
            return False

        # Check for common error message patterns
        error_keywords = [
            "error",
            "failed",
            "crash",
            "terminated",
            "unhealthy",
            "unavailable",
            "timeout",
        ]

        message_lower = self.message.lower() if self.message else ""
        if any(keyword in message_lower for keyword in error_keywords):
            return False

        return True

    def get_resource_utilization(self) -> dict[str, Optional[float]]:
        """
        Calculate resource utilization percentages for the container.

        Returns:
            dict: Dictionary containing utilization percentages:
                - 'replica_utilization': Percentage of replicas that are ready
                - 'cpu': CPU utilization (placeholder - actual metrics would need monitoring API)
                - 'memory': Memory utilization (placeholder - actual metrics would need monitoring API)

        Note:
            CPU and memory utilization require access to metrics/monitoring APIs
            which are not available through the standard Control Plane deployment API.
            These return None as placeholders for potential future implementation.
        """
        utilization = {
            "replica_utilization": None,
            "cpu": None,  # Would need metrics API access
            "memory": None,  # Would need metrics API access
        }

        # Calculate replica utilization if we have replica data
        if self.resources.replicas > 0:
            utilization["replica_utilization"] = (
                self.resources.replicas_ready / self.resources.replicas
            ) * 100.0
        else:
            utilization["replica_utilization"] = 0.0

        # CPU and memory utilization would require additional API calls
        # to monitoring/metrics endpoints that aren't part of the deployment API
        # For now, these remain None as placeholders

        return utilization


@dataclass
class Version(BaseParser):
    """
    Represents a deployment version from the Control Plane API.

    Attributes:
        message (str): Status message for this version
        name (str): Version name identifier
        ready (bool): Whether this version is ready
        containers (list[ContainerDeployment]): List of container deployments
        created (str): Creation timestamp
        workload (int): The workload version number
        zone (str): Deployment zone
    """

    message: str
    name: str
    ready: bool
    containers: list[ContainerDeployment]
    created: str
    workload: int  # this is the workload version number
    zone: str

    @classmethod
    @preparse
    def parse(cls, data: dict[str, Any]) -> Any:
        containers = data.pop("containers")
        containers_list = [
            ContainerDeployment.parse(container) for _, container in containers.items()
        ]

        # For suspended workloads, name and zone might be missing from the API response
        # In that case, provide default values
        if "name" not in data:
            workload_version = data.get("workload", 0)
            data["name"] = f"version-{workload_version}"

        if "zone" not in data:
            data["zone"] = ""

        return cls(**cls.format_key_of_dict(data), containers=containers_list)


@dataclass
class Internal(BaseParser):
    """
    Represents internal deployment status information.

    Attributes:
        pod_status (dict[str, Any]): Kubernetes pod status information
        pods_valid_zone (bool): Whether pods are in a valid zone
        timestamp (str): Timestamp of status
        ksvc_status (dict[str, Any]): Knative service status information
    """

    pod_status: dict[str, Any] = None
    pods_valid_zone: bool = False
    timestamp: str = ""
    ksvc_status: dict[str, Any] = None

    def __post_init__(self):
        if self.pod_status is None:
            self.pod_status = {}
        if self.ksvc_status is None:
            self.ksvc_status = {}


@dataclass
class Status(BaseParser):
    """
    Represents the status of a deployment.

    Attributes:
        endpoint (str): The deployment endpoint URL
        remote (str): Remote endpoint URL
        last_processed_version (str): Last processed version identifier
        expected_deployment_version (str): Expected deployment version
        message (str): Status message
        internal (Internal): Internal status information
        ready (bool): Whether the deployment is ready
        versions (list[Version]): List of deployment versions
    """

    endpoint: str
    remote: str
    last_processed_version: str
    expected_deployment_version: str
    message: str
    internal: Internal
    ready: bool
    versions: list[Version]

    @classmethod
    @preparse
    def parse(cls, data: dict[str, Any]) -> Any:
        internal = data.pop("internal")
        versions = data.pop("versions")
        endpoint = data.pop("endpoint")
        remote = data.pop("remote")
        last_processed_version = data.pop("lastProcessedVersion")
        expected_deployment_version = data.pop("expectedDeploymentVersion")
        message = data.pop("message")
        ready = data.pop("ready")

        return cls(
            endpoint=endpoint,
            remote=remote,
            last_processed_version=last_processed_version,
            expected_deployment_version=expected_deployment_version,
            message=message,
            ready=ready,
            internal=Internal.parse(internal),
            versions=[Version.parse(version) for version in versions],
        )


@dataclass
class Link(BaseParser):
    """
    Represents a link object from the API response.

    Attributes:
        rel (str): The relationship type of the link
        href (str): The URL of the link
    """

    rel: str
    href: str


# class APIClient(requests.Session):
#     pass


@dataclass
class WorkloadReplica(BaseParser):
    """
    Represents a replica of a workload container.

    Attributes:
        name (str): Name of the replica
        container (str): Container name
        config (WorkloadConfig): Workload configuration
        api_config (APIConfig): API configuration
        remote_wss (str): Remote WebSocket URL
    """

    name: str
    container: str
    config: WorkloadConfig
    api_config: APIConfig
    remote_wss: str

    def exec(
        self,
        command: Union[str, list[str]],
        verbose: bool = False,
    ) -> Any:
        """
        Executes a command in a workload container.

        Args:
            config (WorkloadConfig): Configuration object containing workload details
            command (str): The command to execute

        Returns:
            Any: The result of the command execution

        Raises:
            APIError: If the request fails
        """
        error_message = []
        if self.config.container is None and self.container is None:
            error_message.append("Container")
        if self.config.replica is None and self.name is None:
            error_message.append("Replica")
        if self.config.remote_wss is None and self.remote_wss is None:
            error_message.append("Remote WSS")
        if error_message:
            raise ValueError(", ".join(error_message) + " not set")

        request = {
            "token": self.api_config.token,
            "org": self.api_config.org,
            "gvc": self.config.gvc,
            "container": self.container or self.config.container,
            "pod": self.name or self.config.replica,  # TODO: check if this is correct
            "command": command.split(" ") if isinstance(command, str) else command,
        }
        websocket_api = WebSocketAPI(
            self.remote_wss or self.config.remote_wss, verbose=verbose
        )
        try:
            return websocket_api.exec(**request)
        except WebSocketExitCodeError as e:
            print(f"Command failed with exit code: {e}")
            raise

    def ping(self, verbose: bool = False) -> None:
        self.exec(["echo", "ping"], verbose=verbose)


@dataclass
class Deployment(BaseParser):
    """
    Represents a deployment in the Control Plane system.

    This class encapsulates deployment information including status, metadata,
    and provides methods for interacting with deployment replicas.

    Attributes:
        name (str): Name of the deployment
        status (Status): Current deployment status
        last_modified (str): Last modification timestamp
        kind (str): Type/kind of the deployment
        links (list[Link]): Related links for this deployment
        api_client (Optional[APIClient]): API client for making requests
        config (Optional[WorkloadConfig]): Workload configuration
    """

    name: str
    status: Status
    last_modified: str
    kind: str
    links: list[Link]
    api_client: Optional["APIClient"] = None
    config: Optional[WorkloadConfig] = None

    def __post_init__(self):
        # Don't modify the original API client at all
        # We'll create a separate config only when needed for replica operations
        pass

    def export(self) -> dict[str, Any]:
        data = self.to_dict()
        self.pop_optional_fields(data)

        return {
            "name": data["name"],
            "status": data["status"],
            "last_modified": data["last_modified"],
            "kind": data["kind"],
        }

    @classmethod
    def parse(
        cls,
        data: dict[str, Any],
        api_client: "APIClient",
        config: WorkloadConfig,
    ) -> Any:
        return cls(
            name=data["name"],
            status=Status.parse(data["status"]),
            last_modified=data["lastModified"],
            kind=data["kind"],
            links=[Link.parse(link) for link in data["links"]],
            api_client=api_client,
            config=config,
        )

    def get_remote_deployment(self, remote_api_client) -> dict[str, Any]:
        tmp = remote_api_client._get(
            f"gvc/{self.config.gvc}/workload/{self.config.workload_id}"
        )
        return tmp

    def get_replicas(self) -> dict[str, list[WorkloadReplica]]:
        from ..api.client import APIClient
        
        remote_api_client = APIClient(
            token=self.api_client.config.token,
            org=self.api_client.config.org,
            base_url=self.get_remote() + '/replicas',
        )

        self.get_remote_deployment(remote_api_client)
        return {
            container_name: [
                WorkloadReplica.parse(
                    {
                        "name": replica,
                        "container": container_name,
                        "config": self.config,
                        "remote_wss": self.get_remote_wss(),
                        "api_config": self.api_client.config,
                    }
                )
                for replica in self.get_remote_deployment(remote_api_client)["items"]
            ]
            for container_name in self.get_containers()
        }

    def get_remote_wss(self) -> str:
        return self.status.remote.replace("https:", "wss:") + "/remote"

    def get_remote(self) -> str:
        return self.status.remote

    def get_containers(self) -> dict[str, ContainerDeployment]:
        return {
            container.name: container
            for version in self.status.versions
            for container in version.containers
        }
