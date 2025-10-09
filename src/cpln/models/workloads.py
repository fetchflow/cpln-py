import copy
import random
from typing import Any, Optional

import inflection

from ..config import WorkloadConfig
from ..errors import WebSocketExitCodeError
from ..parsers.container import Container
from ..parsers.deployment import Deployment
from ..parsers.spec import Spec
from ..utils import get_default_workload_template, load_template, load_yaml_template
from .resource import Collection, Model


class Workload(Model):
    """
    A workload on the server.
    """

    def get(self) -> dict[str, Any]:
        """
        Get the workload.

        Returns:
            (dict): The workload.

        Raises:
            :py:class:`cpln.errors.NotFound`
                If the workload does not exist.
            :py:class:`cpln.errors.APIError`
                If the server returns an error.
        """
        return self.client.api.get_workload(self.config())

    def get_spec(self) -> Spec:
        """
        Get the workload specification.

        Returns:
            Spec: The parsed workload specification
        """
        return Spec.parse(self.attrs["spec"])

    def get_deployment(self, location: Optional[str] = None) -> Deployment:
        """
        Get the deployment information for this workload.

        Args:
            location (Optional[str]): The location/region to get deployment from.
                If None, gets deployment from default location.

        Returns:
            Deployment: The deployment information for the workload

        Raises:
            APIError: If the request fails
        """
        deployment_data = self.client.api.get_workload_deployment(
            self.config(location=location)
        )
        return deployment_data

    def delete(self) -> None:
        """
        Delete the workload.

        Raises:
            :py:class:`cpln.errors.APIError`
                If the server returns an error.
        """
        print(f"Deleting Workload: {self}")
        self.client.api.delete_workload(self.config())
        print("Deleted!")

    def clone(
        self,
        name: str,
        gvc: Optional[str] = None,
        workload_type: Optional[str] = None,
    ) -> None:
        """
        Clone the workload.

        Args:
            name (str): The name of the new workload.
            gvc (str, optional): The GVC to create the workload in. Defaults to None.
            workload_type (str, optional): The type of workload to create. Defaults to None.

        Returns:
            None

        Raises:
            Exception: If the API returns a non-2xx status code.
        """
        metadata = self.export()

        # TODO: I need to get identity link from the REST API, in order
        # to change it in the metadata. The path to the identity link is
        # different for different GVCs.

        # TODO: The parameters to the created/cloned workloads are too limited.
        # In order for this package to be more widely used, we need to implement
        # a way to pass more workload configuration parameters.
        metadata["name"] = name
        if gvc is not None:
            metadata["gvc"] = gvc

        if workload_type is not None:
            metadata["spec"]["type"] = workload_type

            # Ensure defaultOptions exists
            if "defaultOptions" not in metadata["spec"]:
                metadata["spec"]["defaultOptions"] = {}

            # Ensure autoscaling exists
            if "autoscaling" not in metadata["spec"]["defaultOptions"]:
                metadata["spec"]["defaultOptions"]["autoscaling"] = {}

            # Set autoscaling metric and capacityAI
            metadata["spec"]["defaultOptions"]["autoscaling"]["metric"] = "cpu"
            metadata["spec"]["defaultOptions"]["capacityAI"] = False

        response = self.client.api.create_workload(
            config=self.config(gvc=metadata["gvc"]),
            metadata=metadata,
        )
        if response.status_code // 100 == 2:
            print(response.status_code, response.text)
        else:
            print(response.status_code, response.json())
            raise RuntimeError(f"API call failed with status {response.status_code}")

    def suspend(self) -> None:
        """
        Suspend the workload.

        This will stop the workload from running while preserving its configuration.
        """
        self._change_suspend_state(state=True)

    def unsuspend(self) -> None:
        """
        Unsuspend (resume) the workload.

        This will resume the workload from a suspended state.
        """
        self._change_suspend_state(state=False)

    def exec(
        self,
        command: str,
        location: str,
        container: Optional[str] = None,
        replica_selector: Optional[int] = None,
    ):
        """
        Execute a command on the workload.

        Args:
            command (str): The command to execute.
            location (str): The location of the workload.
            container (str): The container to execute the command on.

        Returns:
            (dict): The response from the server.

        Raises:
            :py:class:`cpln.errors.WebSocketExitCodeError`
                If the command returns a non-zero exit code.
        """
        deployment = self.get_deployment(location=location)
        replicas = deployment.get_replicas()
        if len(replicas) == 0:
            raise ValueError(f"No replicas found in workload {self.attrs['name']}")

        replica = replicas.get(container, [])
        if len(replica) == 0:
            raise ValueError(
                f"Container {container} not found in workload {self.attrs['name']}"
            )

        # Choose a number between 0 and len(replica) - 1 randomly if replica_selector is None
        index = (
            replica_selector
            if replica_selector is not None
            else random.randint(0, len(replica) - 1)
        )
        return replica[index].exec(command)

    def ping(
        self,
        location: Optional[str] = None,
        container: Optional[str] = None,
        replica_selector: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Ping the workload.

        Args:
            location (str): The location of the workload.
                Default: None
        Returns:
            (dict): The response from the server containing status, message, and exit code.
        """
        try:
            self.exec(
                "echo ping",
                location=location,
                container=container,
                replica_selector=replica_selector,
            )
            return {
                "status": 200,
                "message": "Successfully pinged workload",
                "exit_code": 0,
            }
        except WebSocketExitCodeError as e:
            return {
                "status": 500,
                "message": f"Command failed with exit code: {e}",
                "exit_code": e.exit_code,
            }
        except Exception as e:
            return {"status": 500, "message": str(e), "exit_code": -1}

    def export(self) -> dict[str, Any]:
        """
        Export the workload.
        """
        from ..utils.utils import convert_dictionary_keys

        return {
            "name": self.name,
            "gvc": self.state["gvc"],
            "spec": convert_dictionary_keys(
                self.get_spec().to_dict(),
                lambda x: inflection.camelize(x, False),
                key_map={
                    "capacity_ai": "capacityAI",
                },
            ),
        }

    def config(
        self, location: Optional[str] = None, gvc: Optional[str] = None
    ) -> WorkloadConfig:
        """
        Get the workload config.

        Args:
            location (str): The location of the workload.
                Default: None

        Returns:
            (WorkloadConfig): The workload config.
        """
        return WorkloadConfig(
            gvc=self.state["gvc"] if gvc is None else gvc,
            workload_id=self.attrs["name"],
            location=location,
        )

    def get_replicas(self, location: Optional[str] = None) -> list[str]:
        """
        Get the replicas of the workload.

        Args:
            location (str): The location of the workload.
                Default: None

        Returns:
            (list): The replicas of the workload.
        """
        return self.get_deployment(location=location).get_replicas()

    def get_containers(self):
        """
        Get containers for this workload with full Container objects.

        Args:
            location: Optional location filter

        Returns:
            List of Container instances with full metadata
        """
        return self.get_spec().containers

    def get_container(self, container_name: str) -> Optional["Container"]:
        """
        Get a specific container by name within this workload.

        Args:
            container_name: Name of the container to find

        Returns:
            Container instance if found, None otherwise
        """
        containers = self.get_containers()
        return next(filter(lambda c: c.name == container_name, containers), None)

    def update(
        self,
        description: Optional[str] = None,
        image: Optional[str] = None,
        container_name: Optional[str] = None,
        workload_type: Optional[str] = None,
        replicas: Optional[int] = None,
        cpu: Optional[str] = None,
        memory: Optional[str] = None,
        environment_variables: Optional[dict[str, str]] = None,
        metadata_file_path: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        spec: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Update the workload with the provided parameters.

        This method supports both specific parameter updates and full spec updates.
        It performs validation before sending the update to the API and supports
        partial updates by merging with the existing workload specification.

        Args:
            description (Optional[str]): New description for the workload
            image (Optional[str]): New container image. If provided, container_name should also be specified
            container_name (Optional[str]): Name of container to update the image for
            workload_type (Optional[str]): New workload type ("serverless" or "standard")
            replicas (Optional[int]): Number of replicas for scaling
            cpu (Optional[str]): CPU resource specification (e.g., "100m", "1")
            memory (Optional[str]): Memory resource specification (e.g., "128Mi", "1Gi")
            environment_variables (Optional[Dict[str, str]]): Environment variables to update/add
            metadata_file_path (Optional[str]): Path to JSON file containing full metadata
            metadata (Optional[Dict[str, Any]]): Full metadata dictionary for complete replacement
            spec (Optional[Dict[str, Any]]): Workload spec dictionary for spec-only updates

        Returns:
            None: Updates return immediately without waiting for deployment completion

        Raises:
            ValueError: If validation fails or invalid parameters are provided
            RuntimeError: If the API call fails

        Examples:
            # Update container image
            workload.update(image="nginx:1.21", container_name="web")

            # Scale workload
            workload.update(replicas=5)

            # Update resources
            workload.update(cpu="500m", memory="1Gi")

            # Update environment variables (merges with existing)
            workload.update(environment_variables={"NEW_VAR": "value"})

            # Full spec update
            workload.update(spec={"containers": [...], "defaultOptions": {...}})
        """
        # Validate mutually exclusive options
        exclusive_options = [metadata_file_path, metadata, spec]
        provided_exclusive = [opt for opt in exclusive_options if opt is not None]

        if len(provided_exclusive) > 1:
            raise ValueError(
                "Only one of metadata_file_path, metadata, or spec can be provided"
            )

        # Validate container_name when image is provided
        if image is not None and container_name is None:
            # Try to auto-detect container name if only one container exists
            containers = self.get_containers()
            if len(containers) == 1:
                container_name = containers[0].name
            else:
                raise ValueError(
                    "container_name must be specified when image is provided "
                    "and workload has multiple containers"
                )

        # Validate workload_type
        if workload_type is not None and workload_type not in [
            "serverless",
            "standard",
            "cron",
        ]:
            raise ValueError(
                "workload_type must be 'serverless', 'standard', or 'cron'"
            )

        # Validate replicas
        if replicas is not None and replicas < 0:
            raise ValueError("replicas must be non-negative")

        # Validate resource specifications
        if cpu is not None:
            self._validate_cpu_spec(cpu)
        if memory is not None:
            self._validate_memory_spec(memory)

        # Build update data based on provided parameters
        try:
            if metadata_file_path is not None:
                # Load from file
                update_data = load_template(metadata_file_path)
            elif metadata is not None:
                # Use provided metadata (full replacement)
                update_data = copy.deepcopy(metadata)
            elif spec is not None:
                # Use provided spec (spec-only update)
                update_data = {"spec": copy.deepcopy(spec)}
            else:
                # Build update from individual parameters
                update_data = self._build_update_from_parameters(
                    description=description,
                    image=image,
                    container_name=container_name,
                    workload_type=workload_type,
                    replicas=replicas,
                    cpu=cpu,
                    memory=memory,
                    environment_variables=environment_variables,
                )

            # Apply the update via API
            response = self.client.api.patch_workload(
                config=self.config(),
                data=update_data,
            )

            # Handle response
            if response.status_code // 100 == 2:
                print(f"✅ Workload '{self.name}' updated successfully")
                print(f"   Status: {response.status_code}")
                # Note: You can call self.reload() to refresh workload data from server
            else:
                error_msg = f"API call failed with status {response.status_code}"
                try:
                    error_detail = response.json()
                    print(f"❌ Update failed: {error_detail}")
                    error_msg += f": {error_detail}"
                except Exception:
                    print(f"❌ Update failed: {response.text}")
                    error_msg += f": {response.text}"
                raise RuntimeError(error_msg)

        except Exception as e:
            print(f"❌ Failed to update workload '{self.name}': {e}")
            raise

    def _validate_cpu_spec(self, cpu: str) -> None:
        """
        Validate CPU resource specification.

        Args:
            cpu (str): CPU specification to validate

        Raises:
            ValueError: If CPU specification is invalid
        """
        import re

        # Match patterns like "100m", "1", "1.5", "2000m" but NOT bare integers like "100"
        # Valid: single digit integers ("1", "2"), decimal numbers ("1.5", "0.5"), or any integer with 'm' suffix ("100m", "2000m")
        cpu_pattern = r"^(\d\.\d+|\d+\.\d+|\d+m|[0-9])$"
        if not re.match(cpu_pattern, cpu):
            raise ValueError(
                f"Invalid CPU specification '{cpu}'. "
                "Expected format: decimal number (e.g., '1', '1.5') or integer with 'm' suffix (e.g., '100m', '2000m')"
            )

    def _validate_memory_spec(self, memory: str) -> None:
        """
        Validate memory resource specification.

        Args:
            memory (str): Memory specification to validate

        Raises:
            ValueError: If memory specification is invalid
        """
        import re

        # Match patterns like "128Mi", "1Gi", "500M", "2G"
        memory_pattern = r"^(\d+(\.\d+)?)(Mi|Gi|M|G|Ki|K|Ti|T)?$"
        if not re.match(memory_pattern, memory):
            raise ValueError(
                f"Invalid memory specification '{memory}'. "
                "Expected format: number followed by unit (e.g., '128Mi', '1Gi', '500M')"
            )

    def _build_update_from_parameters(
        self,
        description: Optional[str] = None,
        image: Optional[str] = None,
        container_name: Optional[str] = None,
        workload_type: Optional[str] = None,
        replicas: Optional[int] = None,
        cpu: Optional[str] = None,
        memory: Optional[str] = None,
        environment_variables: Optional[dict[str, str]] = None,
    ) -> dict[str, Any]:
        """
        Build update data structure from individual parameters.

        This method creates a partial update structure that merges with existing
        workload configuration rather than replacing it entirely.

        Args:
            Individual update parameters

        Returns:
            Dict[str, Any]: Update data structure for the API
        """
        update_data = {}

        # Update description
        if description is not None:
            update_data["description"] = description

        # Build spec updates
        spec_updates = {}

        # Update workload type
        if workload_type is not None:
            spec_updates["type"] = workload_type

        # Update container-related settings
        if any([image, cpu, memory, environment_variables]):
            containers_update = []

            # Get current containers to merge updates
            current_containers = self.get_containers()

            for container in current_containers:
                container_update = {
                    "name": container.name,
                    "image": container.image,
                }

                # Update image for specified container
                if image is not None and container.name == container_name:
                    container_update["image"] = image

                # Update resources
                if cpu is not None or memory is not None:
                    resources = {}
                    if cpu is not None:
                        resources["cpu"] = cpu
                    if memory is not None:
                        resources["memory"] = memory
                    container_update["resources"] = resources

                # Update environment variables (merge with existing)
                if environment_variables is not None:
                    # Get current env vars
                    current_env = getattr(container, "env", []) or []
                    env_dict = {
                        env.get("name"): env.get("value")
                        for env in current_env
                        if isinstance(env, dict)
                    }

                    # Merge with new env vars
                    env_dict.update(environment_variables)

                    # Convert back to list format
                    env_list = [{"name": k, "value": v} for k, v in env_dict.items()]
                    container_update["env"] = env_list

                containers_update.append(container_update)

            if containers_update:
                spec_updates["containers"] = containers_update

        # Update scaling (replicas)
        if replicas is not None:
            if "defaultOptions" not in spec_updates:
                spec_updates["defaultOptions"] = {}
            if "autoscaling" not in spec_updates["defaultOptions"]:
                spec_updates["defaultOptions"]["autoscaling"] = {}
            spec_updates["defaultOptions"]["autoscaling"]["minScale"] = replicas
            spec_updates["defaultOptions"]["autoscaling"]["maxScale"] = replicas

        # Add spec updates to main update data
        if spec_updates:
            update_data["spec"] = spec_updates

        return update_data

    def _change_suspend_state(self, state: bool = True) -> None:
        output = self.client.api.patch_workload(
            config=self.config(),
            data={"spec": {"defaultOptions": {"suspend": str(state).lower()}}},
        )
        print(f"{'' if state else 'Un'}Suspending Workload: {self}")
        return output


class WorkloadCollection(Collection):
    """
    Workloads on the server.
    """

    model = Workload

    def create(
        self,
        name: str,
        gvc: Optional[str] = None,
        config: Optional[WorkloadConfig] = None,
        description: Optional[str] = None,
        image: Optional[str] = None,
        container_name: Optional[str] = None,
        workload_type: Optional[str] = None,
        metadata_file_path: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Create the workload.
        """
        if gvc is None and config is None:
            raise ValueError("Either GVC or WorkloadConfig must be defined.")
        config = WorkloadConfig(gvc=gvc) if gvc else config

        if metadata is None:
            if metadata_file_path is None:
                if not image:
                    raise ValueError("Image is required.")
                if not container_name:
                    raise ValueError("Container name is required.")

                metadata = get_default_workload_template(
                    "serverless" if workload_type is None else workload_type
                )
                metadata["name"] = name
                metadata["description"] = description if description is not None else ""
                metadata["spec"]["containers"][0]["image"] = image
                metadata["spec"]["containers"][0]["name"] = container_name

            else:
                metadata = load_template(metadata_file_path)
        else:
            metadata["name"] = name
            if workload_type is not None:
                metadata["spec"]["type"] = workload_type
                metadata["spec"]["defaultOptions"]["autoscaling"]["metric"] = "cpu"
                metadata["spec"]["defaultOptions"]["capacityAI"] = False

        response = self.client.api.create_workload(config, metadata)
        if response.status_code // 100 == 2:
            print(response.status_code, response.text)
        else:
            print(response.status_code, response.json())
            raise RuntimeError(f"API call failed with status {response.status_code}")

    def create_from_template(
        self,
        template_path: str,
        variables: Optional[dict[str, str]] = None,
        gvc: Optional[str] = None,
        config: Optional[WorkloadConfig] = None,
    ) -> None:
        """
        Create a workload from a YAML template file.

        Args:
            template_path (str): Path to the YAML template file
            variables (Optional[dict[str, str]]): Variables for template substitution
            gvc (Optional[str]): The GVC to create the workload in. Defaults to None.
            config (Optional[WorkloadConfig]): Alternative to gvc parameter

        Returns:
            None

        Raises:
            ValueError: If neither gvc nor config is provided
            TemplateNotFoundError: If the template file doesn't exist
            TemplateParsingError: If the template is invalid
            TemplateVariableError: If required variables are missing
            RuntimeError: If the API call fails

        Example:
            >>> variables = {
            ...     "WORKLOAD_NAME": "my-app",
            ...     "IMAGE_NAME_TAG": "nginx:latest",
            ...     "GVC_NAME": "production"
            ... }
            >>> client.workloads.create_from_template(
            ...     template_path="./templates/workload.yml",
            ...     variables=variables,
            ...     gvc="production"
            ... )
        """
        if gvc is None and config is None:
            raise ValueError("Either GVC or WorkloadConfig must be defined.")

        config = WorkloadConfig(gvc=gvc) if gvc else config

        # Load and process the template
        metadata = load_yaml_template(template_path, variables)

        # Validate that the template contains required fields
        if "name" not in metadata:
            raise ValueError("Template must contain a 'name' field")

        response = self.client.api.create_workload(config, metadata)
        if response.status_code // 100 == 2:
            print(f"✅ Workload '{metadata['name']}' created successfully from template")
            print(f"   Status: {response.status_code}")
        else:
            error_msg = f"API call failed with status {response.status_code}"
            try:
                error_detail = response.json()
                print(f"❌ Template deployment failed: {error_detail}")
                error_msg += f": {error_detail}"
            except Exception:
                print(f"❌ Template deployment failed: {response.text}")
                error_msg += f": {response.text}"
            raise RuntimeError(error_msg)

    def apply_template(
        self,
        template_path: str,
        variables: Optional[dict[str, str]] = None,
        gvc: Optional[str] = None,
        config: Optional[WorkloadConfig] = None,
    ) -> None:
        """
        Apply a YAML template to create or update a workload.

        This method will attempt to update an existing workload if it exists,
        or create a new one if it doesn't exist.

        Args:
            template_path (str): Path to the YAML template file
            variables (Optional[dict[str, str]]): Variables for template substitution
            gvc (Optional[str]): The GVC to apply the template in. Defaults to None.
            config (Optional[WorkloadConfig]): Alternative to gvc parameter

        Returns:
            None

        Raises:
            ValueError: If neither gvc nor config is provided
            TemplateNotFoundError: If the template file doesn't exist
            TemplateParsingError: If the template is invalid
            TemplateVariableError: If required variables are missing
            RuntimeError: If the API call fails

        Example:
            >>> variables = {
            ...     "WORKLOAD_NAME": "my-app",
            ...     "IMAGE_NAME_TAG": "nginx:v1.1.0",
            ...     "GVC_NAME": "production"
            ... }
            >>> client.workloads.apply_template(
            ...     template_path="./templates/workload.yml",
            ...     variables=variables,
            ...     gvc="production"
            ... )
        """
        if gvc is None and config is None:
            raise ValueError("Either GVC or WorkloadConfig must be defined.")

        config = WorkloadConfig(gvc=gvc) if gvc else config

        # Load and process the template
        metadata = load_yaml_template(template_path, variables)

        # Validate that the template contains required fields
        if "name" not in metadata:
            raise ValueError("Template must contain a 'name' field")

        workload_name = metadata["name"]
        workload_config = WorkloadConfig(gvc=config.gvc, workload_id=workload_name)

        try:
            # Try to get the existing workload
            existing_workload = self.get(workload_config)
            print(f"🔄 Updating existing workload '{workload_name}' from template")

            # Update the existing workload
            response = self.client.api.patch_workload(
                config=workload_config,
                data=metadata,
            )

            if response.status_code // 100 == 2:
                print(f"✅ Workload '{workload_name}' updated successfully from template")
                print(f"   Status: {response.status_code}")
            else:
                error_msg = f"API call failed with status {response.status_code}"
                try:
                    error_detail = response.json()
                    print(f"❌ Template update failed: {error_detail}")
                    error_msg += f": {error_detail}"
                except Exception:
                    print(f"❌ Template update failed: {response.text}")
                    error_msg += f": {response.text}"
                raise RuntimeError(error_msg)

        except Exception as e:
            # If workload doesn't exist or there's an error getting it, create a new one
            if "not found" in str(e).lower() or "404" in str(e):
                print(f"🆕 Creating new workload '{workload_name}' from template")
                self.create_from_template(template_path, variables, gvc, config)
            else:
                # Re-raise other errors
                raise

    def get(self, config: WorkloadConfig):
        """
        Gets a workload.

        Args:
            config (WorkloadConfig): The workload config.

        Returns:
            (:py:class:`Workload`): The workload.

        Raises:
            :py:class:`cpln.errors.NotFound`
                If the workload does not exist.
            :py:class:`cpln.errors.APIError`
                If the server returns an error.
        """
        return self.prepare_model(
            self.client.api.get_workload(config=config), state={"gvc": config.gvc}
        )

    def list(
        self, gvc: Optional[str] = None, config: Optional[WorkloadConfig] = None
    ) -> list[Workload]:
        """
        List workloads.

        Args:
            gvc (str): The GVC to list workloads from.
            config (WorkloadConfig): The workload config.

        Returns:
            (list): The workloads.

        Raises:
            ValueError: If neither gvc nor config is defined.
        """
        if gvc is None and config is None:
            raise ValueError("Either GVC or WorkloadConfig must be defined.")

        config = WorkloadConfig(gvc=gvc) if gvc else config
        resp = self.client.api.get_workload(config)["items"]
        return [
            self.get(
                config=WorkloadConfig(gvc=config.gvc, workload_id=workload["name"])
            )
            for workload in resp
        ]
