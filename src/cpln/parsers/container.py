from dataclasses import dataclass
from typing import Any, Optional

from .base import BaseParser, preparse


@dataclass
class ContainerPort(BaseParser):
    """
    Represents a container port configuration.

    Attributes:
        number (int): The port number
        protocol (str): The protocol (e.g., 'tcp', 'udp')
    """

    number: int
    protocol: str


@dataclass
class Container(BaseParser):
    """
    Represents a container specification in a workload.

    This class parses and holds container configuration data from the CPLN API.

    Attributes:
        cpu (str): CPU allocation for the container
        name (str): Name of the container
        image (str): Container image reference
        ports (List[ContainerPort]): List of exposed ports
        memory (int): Memory allocation in bytes
        inherit_env (bool): Whether to inherit environment variables
        env (Optional[Dict[str, Any]]): Environment variables for the container
        volumes (Optional[List[Dict[str, Any]]]): Volume configurations for the container
        liveness_probe (Optional[Dict[str, Any]]): Liveness probe configuration
        readiness_probe (Optional[Dict[str, Any]]): Readiness probe configuration
    """

    cpu: str
    name: str
    image: str
    ports: list[ContainerPort]
    memory: int
    inherit_env: bool
    env: Optional[dict[str, Any]] = None
    volumes: Optional[list[dict[str, Any]]] = None
    liveness_probe: Optional[dict[str, Any]] = None
    readiness_probe: Optional[dict[str, Any]] = None
    lifecycle: Optional[dict[str, Any]] = None

    @classmethod
    @preparse
    def parse(cls, data: dict[str, Any]) -> Any:
        """
        Parse raw API data into a Container instance.

        Args:
            data (dict[str, Any]): Raw container data from the API

        Returns:
            Container: A parsed Container instance
        """
        ports = data.pop("ports")
        return cls(
            **cls.format_key_of_dict(data),
            ports=[ContainerPort.parse(port) for port in ports],
        )
