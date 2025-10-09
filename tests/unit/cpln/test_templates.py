"""
Tests for the templates module.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from cpln.errors import TemplateNotFoundError, TemplateParsingError, TemplateVariableError
from cpln.templates import (
    TemplateProcessor,
    load_yaml_template,
    validate_template_variables,
    get_template_variables,
)


class TestTemplateProcessor(unittest.TestCase):
    """Tests for the TemplateProcessor class"""

    def setUp(self) -> None:
        """Set up test fixtures"""
        self.variables = {
            "WORKLOAD_NAME": "test-app",
            "IMAGE_NAME_TAG": "nginx:latest",
            "GVC_NAME": "production",
            "DESCRIPTION": "Test workload"
        }
        self.processor = TemplateProcessor(variables=self.variables)

    def test_initialization_with_variables(self) -> None:
        """Test processor initialization with variables"""
        processor = TemplateProcessor(variables=self.variables)
        self.assertEqual(processor.variables, self.variables)

    def test_initialization_without_variables(self) -> None:
        """Test processor initialization without variables"""
        processor = TemplateProcessor()
        self.assertEqual(processor.variables, {})

    def test_substitute_variables_dollar_brace_format(self) -> None:
        """Test variable substitution with ${VARIABLE} format"""
        content = "name: ${WORKLOAD_NAME}\nimage: ${IMAGE_NAME_TAG}"
        expected = "name: test-app\nimage: nginx:latest"
        result = self.processor.substitute_variables(content)
        self.assertEqual(result, expected)

    def test_substitute_variables_double_brace_format(self) -> None:
        """Test variable substitution with {{VARIABLE}} format"""
        content = "name: {{WORKLOAD_NAME}}\nimage: {{IMAGE_NAME_TAG}}"
        expected = "name: test-app\nimage: nginx:latest"
        result = self.processor.substitute_variables(content)
        self.assertEqual(result, expected)

    def test_substitute_variables_dollar_format(self) -> None:
        """Test variable substitution with $VARIABLE format"""
        content = "name: $WORKLOAD_NAME\nimage: $IMAGE_NAME_TAG"
        expected = "name: test-app\nimage: nginx:latest"
        result = self.processor.substitute_variables(content)
        self.assertEqual(result, expected)

    def test_substitute_variables_mixed_formats(self) -> None:
        """Test variable substitution with mixed formats"""
        content = "name: ${WORKLOAD_NAME}\nimage: {{IMAGE_NAME_TAG}}\ngvc: $GVC_NAME"
        expected = "name: test-app\nimage: nginx:latest\ngvc: production"
        result = self.processor.substitute_variables(content)
        self.assertEqual(result, expected)

    def test_substitute_variables_undefined_variables(self) -> None:
        """Test that undefined variables are left unchanged"""
        content = "name: ${WORKLOAD_NAME}\nundefined: ${UNDEFINED_VAR}"
        expected = "name: test-app\nundefined: ${UNDEFINED_VAR}"
        result = self.processor.substitute_variables(content)
        self.assertEqual(result, expected)

    def test_substitute_variables_partial_word_protection(self) -> None:
        """Test that $VARIABLE format doesn't replace parts of words"""
        content = "name: $WORKLOAD_NAME_SUFFIX and $WORKLOAD_NAME"
        expected = "name: $WORKLOAD_NAME_SUFFIX and test-app"
        result = self.processor.substitute_variables(content)
        self.assertEqual(result, expected)

    def test_get_template_variables_all_formats(self) -> None:
        """Test extracting variables from all formats"""
        content = """
        name: ${WORKLOAD_NAME}
        image: {{IMAGE_NAME_TAG}}
        gvc: $GVC_NAME
        description: ${DESCRIPTION}
        """
        expected = {"WORKLOAD_NAME", "IMAGE_NAME_TAG", "GVC_NAME", "DESCRIPTION"}
        result = self.processor.get_template_variables(content)
        self.assertEqual(result, expected)

    def test_get_template_variables_duplicates(self) -> None:
        """Test that duplicate variables are deduplicated"""
        content = """
        name: ${WORKLOAD_NAME}
        backup_name: ${WORKLOAD_NAME}
        image: {{WORKLOAD_NAME}}
        """
        expected = {"WORKLOAD_NAME"}
        result = self.processor.get_template_variables(content)
        self.assertEqual(result, expected)

    def test_get_template_variables_empty_content(self) -> None:
        """Test extracting variables from empty content"""
        content = "name: test\nimage: nginx"
        result = self.processor.get_template_variables(content)
        self.assertEqual(result, set())

    def test_validate_template_variables_success(self) -> None:
        """Test successful template validation"""
        content = "name: ${WORKLOAD_NAME}\nimage: ${IMAGE_NAME_TAG}"
        result = self.processor.validate_template_variables(content)
        self.assertTrue(result)

    def test_validate_template_variables_missing_required(self) -> None:
        """Test template validation with missing required variables"""
        content = "name: ${WORKLOAD_NAME}\nimage: ${MISSING_VAR}"
        required_vars = {"WORKLOAD_NAME", "MISSING_VAR"}

        with self.assertRaises(TemplateVariableError) as context:
            self.processor.validate_template_variables(content, required_vars)

        self.assertIn("Missing required variables", str(context.exception))
        self.assertIn("MISSING_VAR", str(context.exception))

    def test_validate_template_variables_auto_detect(self) -> None:
        """Test template validation with auto-detected variables"""
        content = "name: ${WORKLOAD_NAME}\nimage: ${MISSING_VAR}"

        with self.assertRaises(TemplateVariableError) as context:
            self.processor.validate_template_variables(content)

        self.assertIn("Missing required variables", str(context.exception))
        self.assertIn("MISSING_VAR", str(context.exception))

    def test_process_string_valid_yaml(self) -> None:
        """Test processing valid YAML string"""
        yaml_content = """
        name: ${WORKLOAD_NAME}
        spec:
          image: ${IMAGE_NAME_TAG}
          gvc: ${GVC_NAME}
        """
        result = self.processor.process_string(yaml_content)

        self.assertEqual(result["name"], "test-app")
        self.assertEqual(result["spec"]["image"], "nginx:latest")
        self.assertEqual(result["spec"]["gvc"], "production")

    def test_process_string_invalid_yaml(self) -> None:
        """Test processing invalid YAML string"""
        yaml_content = """
        name: ${WORKLOAD_NAME}
        spec:
          image: ${IMAGE_NAME_TAG}
          invalid: [unclosed
        """

        with self.assertRaises(TemplateParsingError):
            self.processor.process_string(yaml_content)

    def test_process_string_undefined_variables(self) -> None:
        """Test processing string with undefined variables"""
        yaml_content = """
        name: ${WORKLOAD_NAME}
        undefined: ${UNDEFINED_VAR}
        """

        with self.assertRaises(TemplateVariableError) as context:
            self.processor.process_string(yaml_content)

        self.assertIn("Undefined variables", str(context.exception))
        self.assertIn("UNDEFINED_VAR", str(context.exception))

    def test_process_file_success(self) -> None:
        """Test successful file processing"""
        yaml_content = """
        name: ${WORKLOAD_NAME}
        spec:
          image: ${IMAGE_NAME_TAG}
          gvc: ${GVC_NAME}
        """

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = self.processor.process_file(temp_path)
            self.assertEqual(result["name"], "test-app")
            self.assertEqual(result["spec"]["image"], "nginx:latest")
            self.assertEqual(result["spec"]["gvc"], "production")
        finally:
            os.unlink(temp_path)

    def test_process_file_not_found(self) -> None:
        """Test processing non-existent file"""
        with self.assertRaises(TemplateNotFoundError) as context:
            self.processor.process_file("/nonexistent/file.yml")

        self.assertIn("Template file not found", str(context.exception))

    def test_process_file_permission_error(self) -> None:
        """Test processing file with permission error"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write("name: test")
            temp_path = f.name

        try:
            # Make file unreadable
            os.chmod(temp_path, 0o000)

            with self.assertRaises(TemplateNotFoundError) as context:
                self.processor.process_file(temp_path)

            self.assertIn("Unable to read template file", str(context.exception))
        finally:
            # Restore permissions and clean up
            os.chmod(temp_path, 0o644)
            os.unlink(temp_path)


class TestTemplateFunctions(unittest.TestCase):
    """Tests for template utility functions"""

    def setUp(self) -> None:
        """Set up test fixtures"""
        self.variables = {
            "WORKLOAD_NAME": "test-app",
            "IMAGE_NAME_TAG": "nginx:latest",
            "GVC_NAME": "production"
        }

    def test_load_yaml_template_success(self) -> None:
        """Test successful YAML template loading"""
        yaml_content = """
        name: ${WORKLOAD_NAME}
        spec:
          image: ${IMAGE_NAME_TAG}
        """

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = load_yaml_template(temp_path, self.variables)
            self.assertEqual(result["name"], "test-app")
            self.assertEqual(result["spec"]["image"], "nginx:latest")
        finally:
            os.unlink(temp_path)

    def test_load_yaml_template_no_variables(self) -> None:
        """Test YAML template loading without variables"""
        yaml_content = """
        name: static-name
        spec:
          image: static-image
        """

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = load_yaml_template(temp_path)
            self.assertEqual(result["name"], "static-name")
            self.assertEqual(result["spec"]["image"], "static-image")
        finally:
            os.unlink(temp_path)

    def test_validate_template_variables_function_success(self) -> None:
        """Test template variable validation function"""
        content = "name: ${VAR1}\nimage: ${VAR2}"
        required_vars = {"VAR1", "VAR2"}

        result = validate_template_variables(content, required_vars)
        self.assertTrue(result)

    def test_validate_template_variables_function_missing(self) -> None:
        """Test template variable validation function with missing variables"""
        content = "name: ${VAR1}\nimage: static"
        required_vars = {"VAR1", "VAR2"}

        with self.assertRaises(TemplateVariableError) as context:
            validate_template_variables(content, required_vars)

        self.assertIn("Required variables not found", str(context.exception))
        self.assertIn("VAR2", str(context.exception))

    def test_get_template_variables_function(self) -> None:
        """Test get template variables function"""
        content = """
        name: ${WORKLOAD_NAME}
        image: {{IMAGE_NAME_TAG}}
        gvc: $GVC_NAME
        """
        expected = {"WORKLOAD_NAME", "IMAGE_NAME_TAG", "GVC_NAME"}
        result = get_template_variables(content)
        self.assertEqual(result, expected)

    def test_complex_yaml_template(self) -> None:
        """Test processing a complex YAML template"""
        variables = {
            "WORKLOAD_NAME": "web-app",
            "IMAGE_NAME_TAG": "nginx:1.21",
            "GVC_NAME": "production",
            "DESCRIPTION": "Production web application",
            "CONTAINER_NAME": "web",
            "CPU": "100m",
            "MEMORY": "256Mi"
        }

        yaml_content = """
        name: ${WORKLOAD_NAME}
        description: ${DESCRIPTION}
        gvc: ${GVC_NAME}
        spec:
          type: serverless
          containers:
            - name: ${CONTAINER_NAME}
              image: ${IMAGE_NAME_TAG}
              cpu: ${CPU}
              memory: ${MEMORY}
              ports:
                - number: 8080
                  protocol: http
          defaultOptions:
            autoscaling:
              minScale: 1
              maxScale: 5
        """

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name

        try:
            result = load_yaml_template(temp_path, variables)

            # Verify basic fields
            self.assertEqual(result["name"], "web-app")
            self.assertEqual(result["description"], "Production web application")
            self.assertEqual(result["gvc"], "production")

            # Verify nested container spec
            container = result["spec"]["containers"][0]
            self.assertEqual(container["name"], "web")
            self.assertEqual(container["image"], "nginx:1.21")
            self.assertEqual(container["cpu"], "100m")
            self.assertEqual(container["memory"], "256Mi")

            # Verify complex nested structure
            self.assertEqual(result["spec"]["type"], "serverless")
            self.assertEqual(result["spec"]["defaultOptions"]["autoscaling"]["minScale"], 1)

        finally:
            os.unlink(temp_path)


if __name__ == "__main__":
    unittest.main()