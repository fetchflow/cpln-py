"""
YAML template processing functionality for cpln-py.

This module provides template processing capabilities to support GitHub Actions
and other automation tools that work with YAML configuration files.
"""

import re
from typing import Any, Dict, Optional, Set
import yaml
import os


class TemplateProcessor:
    """
    Handles YAML template processing with variable substitution.

    Supports multiple variable substitution formats:
    - ${VARIABLE_NAME} (preferred)
    - {{VARIABLE_NAME}} (Jinja2-style)
    - $VARIABLE_NAME (simple replacement)

    Example:
        >>> variables = {"WORKLOAD_NAME": "my-app", "IMAGE": "nginx:latest"}
        >>> processor = TemplateProcessor(variables=variables)
        >>> config = processor.process_file("./templates/workload.yml")
    """

    def __init__(self, variables: Optional[Dict[str, str]] = None) -> None:
        """
        Initialize the template processor with variable substitution map.

        Args:
            variables (Optional[Dict[str, str]]): Dictionary of variables to substitute
                in templates. Defaults to None (empty dictionary).
        """
        self.variables = variables or {}

    def process_file(self, template_path: str) -> Dict[str, Any]:
        """
        Load YAML file and perform variable substitution.

        Args:
            template_path (str): Path to the YAML template file

        Returns:
            Dict[str, Any]: The processed template data as a dictionary

        Raises:
            TemplateNotFoundError: If the template file doesn't exist
            TemplateParsingError: If the YAML file is invalid
            TemplateVariableError: If required variables are missing
        """
        from .errors import TemplateNotFoundError, TemplateParsingError

        if not os.path.exists(template_path):
            raise TemplateNotFoundError(f"Template file not found: {template_path}")

        try:
            with open(template_path, 'r', encoding='utf-8') as file:
                template_content = file.read()
        except IOError as e:
            raise TemplateNotFoundError(f"Unable to read template file {template_path}: {e}")

        return self.process_string(template_content)

    def process_string(self, template_content: str) -> Dict[str, Any]:
        """
        Process YAML string content with variable substitution.

        Args:
            template_content (str): The YAML template content as a string

        Returns:
            Dict[str, Any]: The processed template data as a dictionary

        Raises:
            TemplateParsingError: If the YAML content is invalid
            TemplateVariableError: If required variables are missing
        """
        from .errors import TemplateParsingError, TemplateVariableError

        # Check for undefined variables before substitution
        undefined_vars = self._get_undefined_variables(template_content)
        if undefined_vars:
            raise TemplateVariableError(
                f"Undefined variables in template: {', '.join(sorted(undefined_vars))}"
            )

        # Perform variable substitution
        processed_content = self.substitute_variables(template_content)

        # Parse YAML
        try:
            return yaml.safe_load(processed_content)
        except yaml.YAMLError as e:
            raise TemplateParsingError(f"Invalid YAML content: {e}")

    def substitute_variables(self, content: str) -> str:
        """
        Replace template variables with actual values.

        Supports multiple variable formats:
        - ${VARIABLE_NAME} (preferred)
        - {{VARIABLE_NAME}} (Jinja2-style)
        - $VARIABLE_NAME (simple replacement)

        Args:
            content (str): The template content containing variables

        Returns:
            str: Content with variables substituted
        """
        # Replace ${VARIABLE_NAME} format (preferred)
        content = re.sub(
            r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}',
            lambda m: self.variables.get(m.group(1), m.group(0)),
            content
        )

        # Replace {{VARIABLE_NAME}} format (Jinja2-style)
        content = re.sub(
            r'\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}',
            lambda m: self.variables.get(m.group(1), m.group(0)),
            content
        )

        # Replace $VARIABLE_NAME format (simple replacement)
        # This is more careful to avoid replacing parts of words
        content = re.sub(
            r'\$([A-Za-z_][A-Za-z0-9_]*)(?![A-Za-z0-9_])',
            lambda m: self.variables.get(m.group(1), m.group(0)),
            content
        )

        return content

    def get_template_variables(self, content: str) -> Set[str]:
        """
        Extract all template variables from content.

        Args:
            content (str): The template content to analyze

        Returns:
            Set[str]: Set of all variable names found in the template
        """
        variables = set()

        # Find ${VARIABLE_NAME} format
        variables.update(re.findall(r'\$\{([A-Za-z_][A-Za-z0-9_]*)\}', content))

        # Find {{VARIABLE_NAME}} format
        variables.update(re.findall(r'\{\{([A-Za-z_][A-Za-z0-9_]*)\}\}', content))

        # Find $VARIABLE_NAME format
        variables.update(re.findall(r'\$([A-Za-z_][A-Za-z0-9_]*)(?![A-Za-z0-9_])', content))

        return variables

    def validate_template_variables(self, content: str, required_vars: Optional[Set[str]] = None) -> bool:
        """
        Validate that all required variables are present in the template.

        Args:
            content (str): The template content to validate
            required_vars (Optional[Set[str]]): Set of required variable names.
                If None, validates that all variables in template are provided.

        Returns:
            bool: True if all required variables are available, False otherwise

        Raises:
            TemplateVariableError: If required variables are missing
        """
        from .errors import TemplateVariableError

        template_vars = self.get_template_variables(content)

        if required_vars is None:
            required_vars = template_vars

        missing_vars = required_vars - set(self.variables.keys())

        if missing_vars:
            raise TemplateVariableError(
                f"Missing required variables: {', '.join(sorted(missing_vars))}"
            )

        return True

    def _get_undefined_variables(self, content: str) -> Set[str]:
        """
        Get variables that are in the template but not defined in self.variables.

        Args:
            content (str): The template content to check

        Returns:
            Set[str]: Set of undefined variable names
        """
        template_vars = self.get_template_variables(content)
        return template_vars - set(self.variables.keys())


def load_yaml_template(template_path: str, variables: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Convenience function to load and process a YAML template file.

    Args:
        template_path (str): Path to the YAML template file
        variables (Optional[Dict[str, str]]): Variables for substitution

    Returns:
        Dict[str, Any]: The processed template data

    Raises:
        TemplateNotFoundError: If the template file doesn't exist
        TemplateParsingError: If the YAML file is invalid
        TemplateVariableError: If required variables are missing
    """
    processor = TemplateProcessor(variables=variables)
    return processor.process_file(template_path)


def validate_template_variables(template_content: str, required_vars: Set[str]) -> bool:
    """
    Validate that all required variables are present in template content.

    Args:
        template_content (str): The template content to validate
        required_vars (Set[str]): Set of required variable names

    Returns:
        bool: True if all required variables are found

    Raises:
        TemplateVariableError: If required variables are missing
    """
    processor = TemplateProcessor()
    template_vars = processor.get_template_variables(template_content)

    missing_vars = required_vars - template_vars
    if missing_vars:
        from .errors import TemplateVariableError
        raise TemplateVariableError(
            f"Required variables not found in template: {', '.join(sorted(missing_vars))}"
        )

    return True


def get_template_variables(template_content: str) -> Set[str]:
    """
    Extract all template variables from content.

    Args:
        template_content (str): The template content to analyze

    Returns:
        Set[str]: Set of all variable names found in the template
    """
    processor = TemplateProcessor()
    return processor.get_template_variables(template_content)