"""
Tests for workload template functionality.
"""

import os
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch
from typing import Any

from cpln.config import WorkloadConfig
from cpln.errors import TemplateNotFoundError, TemplateVariableError
from cpln.models.workloads import WorkloadCollection
from requests import Response


class TestWorkloadTemplates(unittest.TestCase):
    """Tests for workload template methods"""

    def setUp(self) -> None:
        """Set up test fixtures"""
        self.client = MagicMock()
        self.collection = WorkloadCollection(client=self.client)
        self.variables = {
            "WORKLOAD_NAME": "test-app",
            "IMAGE_NAME_TAG": "nginx:latest",
            "GVC_NAME": "production",
            "DESCRIPTION": "Test workload",
            "CONTAINER_NAME": "web"
        }

    def create_test_template(self, content: str) -> str:
        """Create a temporary template file"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(content)
            return f.name

    def test_create_from_template_success(self) -> None:
        """Test successful workload creation from template"""
        yaml_content = """
        name: ${WORKLOAD_NAME}
        description: ${DESCRIPTION}
        gvc: ${GVC_NAME}
        spec:
          type: serverless
          containers:
            - name: ${CONTAINER_NAME}
              image: ${IMAGE_NAME_TAG}
              cpu: 50m
              memory: 128Mi
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock successful API response
            mock_response = Mock(spec=Response)
            mock_response.status_code = 201
            mock_response.text = "Created"
            self.client.api.create_workload.return_value = mock_response

            # Mock print to avoid output during test
            with patch("builtins.print"):
                self.collection.create_from_template(
                    template_path=template_path,
                    variables=self.variables,
                    gvc="production"
                )

            # Verify API was called
            self.client.api.create_workload.assert_called_once()

            # Check the call arguments
            call_args = self.client.api.create_workload.call_args
            config = call_args[0][0] if call_args[0] else call_args[1]["config"]
            metadata = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]["metadata"]

            # Verify config
            self.assertEqual(config.gvc, "production")

            # Verify metadata was processed correctly
            self.assertEqual(metadata["name"], "test-app")
            self.assertEqual(metadata["description"], "Test workload")
            self.assertEqual(metadata["gvc"], "production")
            self.assertEqual(metadata["spec"]["containers"][0]["name"], "web")
            self.assertEqual(metadata["spec"]["containers"][0]["image"], "nginx:latest")

        finally:
            os.unlink(template_path)

    def test_create_from_template_with_config(self) -> None:
        """Test workload creation from template with WorkloadConfig"""
        yaml_content = """
        name: ${WORKLOAD_NAME}
        spec:
          type: standard
          containers:
            - name: ${CONTAINER_NAME}
              image: ${IMAGE_NAME_TAG}
        """

        template_path = self.create_test_template(yaml_content)
        config = WorkloadConfig(gvc="staging")

        try:
            # Mock successful API response
            mock_response = Mock(spec=Response)
            mock_response.status_code = 201
            self.client.api.create_workload.return_value = mock_response

            with patch("builtins.print"):
                self.collection.create_from_template(
                    template_path=template_path,
                    variables=self.variables,
                    config=config
                )

            # Verify API was called with correct config
            call_args = self.client.api.create_workload.call_args
            used_config = call_args[0][0] if call_args[0] else call_args[1]["config"]
            self.assertEqual(used_config, config)

        finally:
            os.unlink(template_path)

    def test_create_from_template_missing_name(self) -> None:
        """Test error when template is missing name field"""
        yaml_content = """
        description: ${DESCRIPTION}
        spec:
          type: serverless
        """

        template_path = self.create_test_template(yaml_content)

        try:
            with self.assertRaises(ValueError) as context:
                self.collection.create_from_template(
                    template_path=template_path,
                    variables=self.variables,
                    gvc="production"
                )

            self.assertIn("Template must contain a 'name' field", str(context.exception))

        finally:
            os.unlink(template_path)

    def test_create_from_template_missing_variables(self) -> None:
        """Test error when required variables are missing"""
        yaml_content = """
        name: ${WORKLOAD_NAME}
        missing: ${MISSING_VAR}
        """

        template_path = self.create_test_template(yaml_content)

        try:
            with self.assertRaises(TemplateVariableError):
                self.collection.create_from_template(
                    template_path=template_path,
                    variables=self.variables,
                    gvc="production"
                )

        finally:
            os.unlink(template_path)

    def test_create_from_template_no_gvc_or_config(self) -> None:
        """Test error when neither gvc nor config is provided"""
        yaml_content = "name: ${WORKLOAD_NAME}"
        template_path = self.create_test_template(yaml_content)

        try:
            with self.assertRaises(ValueError) as context:
                self.collection.create_from_template(
                    template_path=template_path,
                    variables=self.variables
                )

            self.assertIn("Either GVC or WorkloadConfig must be defined", str(context.exception))

        finally:
            os.unlink(template_path)

    def test_create_from_template_api_error(self) -> None:
        """Test handling of API errors"""
        yaml_content = """
        name: ${WORKLOAD_NAME}
        spec:
          type: serverless
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock API error response
            mock_response = Mock(spec=Response)
            mock_response.status_code = 400
            mock_response.json.return_value = {"error": "Invalid request"}
            mock_response.text = "Bad request"
            self.client.api.create_workload.return_value = mock_response

            with (
                patch("builtins.print"),
                self.assertRaises(RuntimeError) as context,
            ):
                self.collection.create_from_template(
                    template_path=template_path,
                    variables=self.variables,
                    gvc="production"
                )

            self.assertIn("API call failed with status 400", str(context.exception))

        finally:
            os.unlink(template_path)

    def test_apply_template_create_new(self) -> None:
        """Test apply_template creates new workload when it doesn't exist"""
        yaml_content = """
        name: ${WORKLOAD_NAME}
        spec:
          type: serverless
          containers:
            - name: ${CONTAINER_NAME}
              image: ${IMAGE_NAME_TAG}
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock workload not found (404 error)
            self.collection.get = Mock(side_effect=Exception("not found"))

            # Mock successful creation
            mock_response = Mock(spec=Response)
            mock_response.status_code = 201
            self.client.api.create_workload.return_value = mock_response

            with patch("builtins.print"):
                self.collection.apply_template(
                    template_path=template_path,
                    variables=self.variables,
                    gvc="production"
                )

            # Verify create was called
            self.client.api.create_workload.assert_called_once()

        finally:
            os.unlink(template_path)

    def test_apply_template_update_existing(self) -> None:
        """Test apply_template updates existing workload"""
        yaml_content = """
        name: ${WORKLOAD_NAME}
        spec:
          type: serverless
          containers:
            - name: ${CONTAINER_NAME}
              image: ${IMAGE_NAME_TAG}
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock existing workload found
            mock_workload = Mock()
            self.collection.get = Mock(return_value=mock_workload)

            # Mock successful update
            mock_response = Mock(spec=Response)
            mock_response.status_code = 200
            self.client.api.patch_workload.return_value = mock_response

            with patch("builtins.print"):
                self.collection.apply_template(
                    template_path=template_path,
                    variables=self.variables,
                    gvc="production"
                )

            # Verify update was called
            self.client.api.patch_workload.assert_called_once()

            # Check the call arguments
            call_args = self.client.api.patch_workload.call_args
            config = call_args[1]["config"]
            data = call_args[1]["data"]

            # Verify correct workload was targeted
            self.assertEqual(config.workload_id, "test-app")
            self.assertEqual(config.gvc, "production")

            # Verify metadata
            self.assertEqual(data["name"], "test-app")

        finally:
            os.unlink(template_path)

    def test_apply_template_update_error(self) -> None:
        """Test apply_template handles update errors"""
        yaml_content = """
        name: ${WORKLOAD_NAME}
        spec:
          type: serverless
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock existing workload found
            mock_workload = Mock()
            self.collection.get = Mock(return_value=mock_workload)

            # Mock API error response
            mock_response = Mock(spec=Response)
            mock_response.status_code = 400
            mock_response.json.return_value = {"error": "Invalid update"}
            self.client.api.patch_workload.return_value = mock_response

            with (
                patch("builtins.print"),
                self.assertRaises(RuntimeError) as context,
            ):
                self.collection.apply_template(
                    template_path=template_path,
                    variables=self.variables,
                    gvc="production"
                )

            self.assertIn("API call failed with status 400", str(context.exception))

        finally:
            os.unlink(template_path)

    def test_apply_template_missing_name(self) -> None:
        """Test apply_template error when template is missing name field"""
        yaml_content = """
        description: Test workload
        spec:
          type: serverless
        """

        template_path = self.create_test_template(yaml_content)

        try:
            with self.assertRaises(ValueError) as context:
                self.collection.apply_template(
                    template_path=template_path,
                    variables=self.variables,
                    gvc="production"
                )

            self.assertIn("Template must contain a 'name' field", str(context.exception))

        finally:
            os.unlink(template_path)

    def test_apply_template_no_gvc_or_config(self) -> None:
        """Test apply_template error when neither gvc nor config is provided"""
        yaml_content = "name: ${WORKLOAD_NAME}"
        template_path = self.create_test_template(yaml_content)

        try:
            with self.assertRaises(ValueError) as context:
                self.collection.apply_template(
                    template_path=template_path,
                    variables=self.variables
                )

            self.assertIn("Either GVC or WorkloadConfig must be defined", str(context.exception))

        finally:
            os.unlink(template_path)

    def test_template_file_not_found(self) -> None:
        """Test error when template file doesn't exist"""
        with self.assertRaises(TemplateNotFoundError):
            self.collection.create_from_template(
                template_path="/nonexistent/template.yml",
                variables=self.variables,
                gvc="production"
            )

    def test_template_with_no_variables(self) -> None:
        """Test template processing without variables"""
        yaml_content = """
        name: static-workload
        spec:
          type: serverless
          containers:
            - name: static-container
              image: nginx:latest
        """

        template_path = self.create_test_template(yaml_content)

        try:
            # Mock successful API response
            mock_response = Mock(spec=Response)
            mock_response.status_code = 201
            self.client.api.create_workload.return_value = mock_response

            with patch("builtins.print"):
                self.collection.create_from_template(
                    template_path=template_path,
                    gvc="production"
                )

            # Verify API was called
            self.client.api.create_workload.assert_called_once()

            # Check metadata
            call_args = self.client.api.create_workload.call_args
            metadata = call_args[0][1] if len(call_args[0]) > 1 else call_args[1]["metadata"]
            self.assertEqual(metadata["name"], "static-workload")

        finally:
            os.unlink(template_path)


if __name__ == "__main__":
    unittest.main()