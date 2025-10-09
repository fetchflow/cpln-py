"""
Tests for GVC template functionality.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

from cpln.errors import TemplateNotFoundError, TemplateVariableError
from cpln.models.gvcs import GVCCollection


class TestGVCTemplates(unittest.TestCase):
    """Tests for GVC template methods"""

    def setUp(self) -> None:
        """Set up test fixtures"""
        self.client = MagicMock()
        self.collection = GVCCollection(client=self.client)
        self.variables = {
            "GVC_NAME": "production",
            "DESCRIPTION": "Production environment GVC",
            "ENVIRONMENT": "prod",
            "TEAM": "platform"
        }

    def create_test_template(self, content: str) -> str:
        """Create a temporary template file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(content)
            return f.name

    def test_create_from_template_success(self) -> None:
        """Test successful GVC creation from template"""
        yaml_content = """
        name: ${GVC_NAME}
        description: ${DESCRIPTION}
        tags:
          environment: ${ENVIRONMENT}
          team: ${TEAM}
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock successful API response
            self.client.api.create_gvc.return_value = None

            # Mock print to avoid output during test
            with patch("builtins.print"):
                self.collection.create_from_template(
                    template_path=template_path,
                    variables=self.variables
                )

            # Verify API was called with correct parameters
            self.client.api.create_gvc.assert_called_once_with(
                "production",
                "Production environment GVC"
            )

        finally:
            os.unlink(template_path)

    def test_create_from_template_no_description(self) -> None:
        """Test GVC creation from template without description"""
        yaml_content = """
        name: ${GVC_NAME}
        tags:
          environment: ${ENVIRONMENT}
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock successful API response
            self.client.api.create_gvc.return_value = None

            with patch("builtins.print"):
                self.collection.create_from_template(
                    template_path=template_path,
                    variables=self.variables
                )

            # Verify API was called with empty description
            self.client.api.create_gvc.assert_called_once_with("production", "")

        finally:
            os.unlink(template_path)

    def test_create_from_template_missing_name(self) -> None:
        """Test error when template is missing name field"""
        yaml_content = """
        description: ${DESCRIPTION}
        tags:
          environment: ${ENVIRONMENT}
        """

        template_path = self.create_test_template(yaml_content)

        try:
            with self.assertRaises(ValueError) as context:
                self.collection.create_from_template(
                    template_path=template_path,
                    variables=self.variables
                )

            self.assertIn("Template must contain a 'name' field", str(context.exception))

        finally:
            os.unlink(template_path)

    def test_create_from_template_missing_variables(self) -> None:
        """Test error when required variables are missing"""
        yaml_content = """
        name: ${GVC_NAME}
        missing: ${MISSING_VAR}
        """

        template_path = self.create_test_template(yaml_content)

        try:
            with self.assertRaises(TemplateVariableError):
                self.collection.create_from_template(
                    template_path=template_path,
                    variables=self.variables
                )

        finally:
            os.unlink(template_path)

    def test_create_from_template_api_error(self) -> None:
        """Test handling of API errors"""
        yaml_content = """
        name: ${GVC_NAME}
        description: ${DESCRIPTION}
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock API error
            self.client.api.create_gvc.side_effect = Exception("API Error")

            with (
                patch("builtins.print"),
                self.assertRaises(RuntimeError) as context,
            ):
                self.collection.create_from_template(
                    template_path=template_path,
                    variables=self.variables
                )

            self.assertIn("Failed to create GVC from template", str(context.exception))

        finally:
            os.unlink(template_path)

    def test_apply_template_create_new(self) -> None:
        """Test apply_template creates new GVC when it doesn't exist"""
        yaml_content = """
        name: ${GVC_NAME}
        description: ${DESCRIPTION}
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock GVC not found (404 error)
            self.collection.get = Mock(side_effect=Exception("not found"))

            # Mock successful creation
            self.client.api.create_gvc.return_value = None

            with patch("builtins.print"):
                self.collection.apply_template(
                    template_path=template_path,
                    variables=self.variables
                )

            # Verify create was called
            self.client.api.create_gvc.assert_called_once_with(
                "production",
                "Production environment GVC"
            )

        finally:
            os.unlink(template_path)

    def test_apply_template_existing_gvc(self) -> None:
        """Test apply_template with existing GVC"""
        yaml_content = """
        name: ${GVC_NAME}
        description: ${DESCRIPTION}
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock existing GVC found
            mock_gvc = Mock()
            self.collection.get = Mock(return_value=mock_gvc)

            with patch("builtins.print"):
                self.collection.apply_template(
                    template_path=template_path,
                    variables=self.variables
                )

            # Verify get was called
            self.collection.get.assert_called_once_with("production")

            # Verify create was NOT called (GVC already exists)
            self.client.api.create_gvc.assert_not_called()

        finally:
            os.unlink(template_path)

    def test_apply_template_missing_name(self) -> None:
        """Test apply_template error when template is missing name field"""
        yaml_content = """
        description: ${DESCRIPTION}
        tags:
          environment: ${ENVIRONMENT}
        """

        template_path = self.create_test_template(yaml_content)

        try:
            with self.assertRaises(ValueError) as context:
                self.collection.apply_template(
                    template_path=template_path,
                    variables=self.variables
                )

            self.assertIn("Template must contain a 'name' field", str(context.exception))

        finally:
            os.unlink(template_path)

    def test_apply_template_get_error_not_404(self) -> None:
        """Test apply_template re-raises non-404 errors from get"""
        yaml_content = """
        name: ${GVC_NAME}
        description: ${DESCRIPTION}
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock non-404 error
            self.collection.get = Mock(side_effect=Exception("API Error"))

            with self.assertRaises(Exception) as context:
                self.collection.apply_template(
                    template_path=template_path,
                    variables=self.variables
                )

            self.assertEqual(str(context.exception), "API Error")

        finally:
            os.unlink(template_path)

    def test_template_file_not_found(self) -> None:
        """Test error when template file doesn't exist"""
        with self.assertRaises(TemplateNotFoundError):
            self.collection.create_from_template(
                template_path="/nonexistent/template.yml",
                variables=self.variables
            )

    def test_template_with_no_variables(self) -> None:
        """Test template processing without variables"""
        yaml_content = """
        name: static-gvc
        description: Static GVC description
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock successful API response
            self.client.api.create_gvc.return_value = None

            with patch("builtins.print"):
                self.collection.create_from_template(template_path=template_path)

            # Verify API was called with static values
            self.client.api.create_gvc.assert_called_once_with(
                "static-gvc",
                "Static GVC description"
            )

        finally:
            os.unlink(template_path)

    def test_create_from_template_no_variables_param(self) -> None:
        """Test template processing with None variables parameter"""
        yaml_content = """
        name: simple-gvc
        description: Simple GVC
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock successful API response
            self.client.api.create_gvc.return_value = None

            with patch("builtins.print"):
                self.collection.create_from_template(
                    template_path=template_path,
                    variables=None
                )

            # Verify API was called
            self.client.api.create_gvc.assert_called_once_with(
                "simple-gvc",
                "Simple GVC"
            )

        finally:
            os.unlink(template_path)

    def test_complex_gvc_template(self) -> None:
        """Test processing a complex GVC template"""
        variables = {
            "GVC_NAME": "staging-env",
            "DESCRIPTION": "Staging environment for testing",
            "ENVIRONMENT": "staging",
            "TEAM": "development",
            "REGION": "us-east-1",
            "COST_CENTER": "engineering"
        }

        yaml_content = """
        name: ${GVC_NAME}
        description: ${DESCRIPTION}
        tags:
          environment: ${ENVIRONMENT}
          team: ${TEAM}
          region: ${REGION}
          cost-center: ${COST_CENTER}
        locations:
          - ${REGION}
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock successful API response
            self.client.api.create_gvc.return_value = None

            with patch("builtins.print"):
                self.collection.create_from_template(
                    template_path=template_path,
                    variables=variables
                )

            # Verify API was called with correct parameters
            self.client.api.create_gvc.assert_called_once_with(
                "staging-env",
                "Staging environment for testing"
            )

        finally:
            os.unlink(template_path)


if __name__ == "__main__":
    unittest.main()