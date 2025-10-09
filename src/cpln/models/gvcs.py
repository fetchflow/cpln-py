from typing import Optional

from ..utils import load_yaml_template
from .resource import Collection, Model


class GVC(Model):
    """
    A GVC (Global Virtual Cloud) on the server.
    """

    def get(self) -> dict[str, any]:
        """
        Get the GVC.

        Returns:
            (dict): The GVC.

        Raises:
            :py:class:`cpln.errors.NotFound`
                If the GVC does not exist.
            :py:class:`cpln.errors.APIError`
                If the server returns an error.
        """
        return self.client.api.get_gvc(self.attrs["name"])

    def create(self) -> None:
        """
        Create the GVC.

        Raises:
            :py:class:`cpln.errors.APIError`
                If the server returns an error.
        """
        print(f"Creating GVC: {self}")
        self.client.api.create_gvc(self.attrs["name"], self.attrs["description"])
        print("Created!")

    def delete(self) -> None:
        """
        Delete the GVC.

        Raises:
            :py:class:`cpln.errors.APIError`
                If the server returns an error.
        """
        print(f"Deleting GVC: {self}")
        self.client.api.delete_gvc(self.attrs["name"])
        print("Deleted!")


class GVCCollection(Collection):
    """
    GVCs on the server.
    """

    model = GVC

    def get(self, name: str):
        """
        Get a GVC.

        Args:
            name (str): The name of the GVC.

        Returns:
            (:py:class:`GVC`): The GVC.

        Raises:
            :py:class:`cpln.errors.NotFound`
                If the GVC does not exist.
            :py:class:`cpln.errors.APIError`
                If the server returns an error.
        """
        return self.prepare_model(self.client.api.get_gvc(name))

    def list(self):
        """
        List GVCs on the server.

        Returns:
            (list[:py:class:`GVC`]): The GVCs.

        Raises:
            :py:class:`cpln.errors.APIError`
                If the server returns an error.
        """
        resp = self.client.api.get_gvc()["items"]
        return [self.prepare_model(gvc) for gvc in resp]

    def create_from_template(
        self,
        template_path: str,
        variables: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Create a GVC from a YAML template file.

        Args:
            template_path (str): Path to the YAML template file
            variables (Optional[dict[str, str]]): Variables for template substitution

        Returns:
            None

        Raises:
            TemplateNotFoundError: If the template file doesn't exist
            TemplateParsingError: If the template is invalid
            TemplateVariableError: If required variables are missing
            RuntimeError: If the API call fails

        Example:
            >>> variables = {
            ...     "GVC_NAME": "production",
            ...     "DESCRIPTION": "Production environment GVC"
            ... }
            >>> client.gvcs.create_from_template(
            ...     template_path="./templates/gvc.yml",
            ...     variables=variables
            ... )
        """
        # Load and process the template
        metadata = load_yaml_template(template_path, variables)

        # Validate that the template contains required fields
        if "name" not in metadata:
            raise ValueError("Template must contain a 'name' field")

        gvc_name = metadata["name"]
        description = metadata.get("description", "")

        try:
            print(f"🆕 Creating GVC '{gvc_name}' from template")
            self.client.api.create_gvc(gvc_name, description)
            print(f"✅ GVC '{gvc_name}' created successfully from template")
        except Exception as e:
            print(f"❌ Template deployment failed: {e}")
            raise RuntimeError(f"Failed to create GVC from template: {e}")

    def apply_template(
        self,
        template_path: str,
        variables: Optional[dict[str, str]] = None,
    ) -> None:
        """
        Apply a YAML template to create or update a GVC.

        This method will attempt to update an existing GVC if it exists,
        or create a new one if it doesn't exist.

        Note: GVC update functionality depends on the API supporting GVC updates.
        Currently, this method primarily handles creation.

        Args:
            template_path (str): Path to the YAML template file
            variables (Optional[dict[str, str]]): Variables for template substitution

        Returns:
            None

        Raises:
            TemplateNotFoundError: If the template file doesn't exist
            TemplateParsingError: If the template is invalid
            TemplateVariableError: If required variables are missing
            RuntimeError: If the API call fails

        Example:
            >>> variables = {
            ...     "GVC_NAME": "staging",
            ...     "DESCRIPTION": "Staging environment GVC"
            ... }
            >>> client.gvcs.apply_template(
            ...     template_path="./templates/gvc.yml",
            ...     variables=variables
            ... )
        """
        # Load and process the template
        metadata = load_yaml_template(template_path, variables)

        # Validate that the template contains required fields
        if "name" not in metadata:
            raise ValueError("Template must contain a 'name' field")

        gvc_name = metadata["name"]

        try:
            # Try to get the existing GVC
            existing_gvc = self.get(gvc_name)
            print(f"✅ GVC '{gvc_name}' already exists")
            print(f"   Note: GVC updates are not currently supported via templates")

        except Exception as e:
            # If GVC doesn't exist or there's an error getting it, create a new one
            if "not found" in str(e).lower() or "404" in str(e):
                print(f"🆕 Creating new GVC '{gvc_name}' from template")
                self.create_from_template(template_path, variables)
            else:
                # Re-raise other errors
                raise
