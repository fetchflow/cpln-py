from dataclasses import dataclass
from typing import Any, Optional

from .base import BaseParser, preparse
from .container import Container


@dataclass
class LoadBalancer(BaseParser):
    """
    Represents load balancer configuration for a workload.

    Attributes:
        direct (dict[str, Any]): Direct load balancer configuration
        replica_direct (bool): Whether to use replica-direct routing
    """

    direct: dict[str, Any]
    replica_direct: bool


@dataclass
class FirewallConfig(BaseParser):
    """
    Represents firewall configuration for a workload.

    Attributes:
        external (Optional[dict[str, Any]]): External firewall rules
        internal (Optional[dict[str, Any]]): Internal firewall rules
    """

    external: Optional[dict[str, Any]] = None
    internal: Optional[dict[str, Any]] = None


@dataclass
class Autoscaling(BaseParser):
    """
    Represents autoscaling configuration for a workload.

    Attributes:
        metric (str): The metric to use for autoscaling (e.g., 'cpu', 'memory')
        target (int): Target value for the metric
        max_scale (int): Maximum number of replicas
        min_scale (int): Minimum number of replicas
        max_concurrency (int): Maximum concurrent requests per replica
        scale_to_zero_delay (int): Delay before scaling to zero (in seconds)
    """

    metric: str = "cpu"
    target: int = 50
    max_scale: int = 10
    min_scale: int = 1
    max_concurrency: int = 0
    scale_to_zero_delay: int = 300


@dataclass
class MultiZone(BaseParser):
    """
    Represents multi-zone configuration for a workload.

    Attributes:
        enabled (bool): Whether multi-zone deployment is enabled
    """

    enabled: bool = False


@dataclass
class DefaultOptions(BaseParser):
    """
    Represents default options for a workload.

    Attributes:
        debug (bool): Whether debug mode is enabled
        suspend (bool): Whether the workload is suspended
        multi_zone (MultiZone): Multi-zone configuration
        capacity_ai (bool): Whether capacity AI is enabled
        autoscaling (Autoscaling): Autoscaling configuration
        timeout_seconds (int): Request timeout in seconds
    """

    debug: bool = False
    suspend: bool = False
    multi_zone: MultiZone = None
    capacity_ai: bool = False
    autoscaling: Autoscaling = None
    timeout_seconds: int = 30


@dataclass
class Spec(BaseParser):
    """
    Represents a workload specification.

    Attributes:
        type (str): Type of the workload (e.g., 'serverless', 'stateful')
        containers (list[Container]): List of container specifications
        identity_link (str): Identity link for the workload
        load_balancer (LoadBalancer): Load balancer configuration
        default_options (DefaultOptions): Default options for the workload
        firewall_config (FirewallConfig): Firewall configuration
        support_dynamic_tags (bool): Whether dynamic tags are supported
    """

    type: str
    containers: list[Container]
    identity_link: Optional[str] = None
    load_balancer: Optional[LoadBalancer] = None
    default_options: Optional[DefaultOptions] = None
    firewall_config: Optional[FirewallConfig] = None
    support_dynamic_tags: Optional[bool] = None
    rollout_options: Optional[dict[str, Any]] = None
    security_options: Optional[dict[str, Any]] = None

    @classmethod
    @preparse
    def parse(cls, data: dict[str, Any]) -> Any:
        containers = data.pop("containers", [])
        load_balancer = data.pop("loadBalancer", None)
        default_options = data.pop("defaultOptions", None)
        firewall_config = data.pop("firewallConfig", None)

        parsed_data = cls.format_key_of_dict(data)

        return cls(
            **parsed_data,
            containers=[Container.parse(container) for container in containers],
            load_balancer=LoadBalancer.parse(load_balancer) if load_balancer else None,
            default_options=DefaultOptions.parse(default_options)
            if default_options
            else None,
            firewall_config=FirewallConfig.parse(firewall_config)
            if firewall_config
            else None,
        )
