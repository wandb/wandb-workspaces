"""Filter helpers for Reports API to make filtering more intuitive.

This module provides helper classes and functions to create filters in a way
that matches what users see in the W&B UI, rather than requiring them to 
construct complex filter expressions manually.
"""

from typing import Any, List, Optional, Union
from dataclasses import dataclass
from abc import ABC, abstractmethod

from wandb_workspaces import expr


# Mapping of UI-friendly names to internal field names
UI_TO_INTERNAL_MAPPING = {
    # Run fields
    "Name": "displayName",
    "ID": "id", 
    "State": "state",
    "Tags": "tags",
    "Created": "createdAt",
    "Updated": "updatedAt",
    "Duration": "duration",
    "User": "user.username",
    "Group": "group",
    "Job Type": "jobType",
    
    # Common fields that are the same
    "config": "config",
    "summary": "summary",
}


class FilterBuilder:
    """Helper class to build filters using a more intuitive API."""
    
    @staticmethod
    def name(value: Union[str, List[str]]) -> expr.FilterExpr:
        """Filter by run name(s).
        
        Args:
            value: Run name or list of run names
            
        Returns:
            FilterExpr for filtering by name
            
        Example:
            >>> FilterBuilder.name("my_run")
            >>> FilterBuilder.name(["run1", "run2", "run3"])
        """
        if isinstance(value, str):
            value = [value]
        return expr.Metric("displayName").isin(value)
    
    @staticmethod
    def id(value: Union[str, List[str]]) -> expr.FilterExpr:
        """Filter by run ID(s).
        
        Args:
            value: Run ID or list of run IDs
            
        Returns:
            FilterExpr for filtering by ID
        """
        if isinstance(value, str):
            value = [value]
        return expr.Metric("id").isin(value)
    
    @staticmethod
    def state(value: Union[str, List[str]]) -> expr.FilterExpr:
        """Filter by run state(s).
        
        Args:
            value: State or list of states (e.g., "finished", "running", "crashed")
            
        Returns:
            FilterExpr for filtering by state
        """
        if isinstance(value, str):
            value = [value]
        return expr.Metric("state").isin(value)
    
    @staticmethod
    def tags(value: Union[str, List[str]], mode: str = "any") -> expr.FilterExpr:
        """Filter by tags.
        
        Args:
            value: Tag or list of tags
            mode: "any" to match runs with any of the tags, 
                  "all" to match runs with all tags
            
        Returns:
            FilterExpr for filtering by tags
        """
        if isinstance(value, str):
            value = [value]
        
        if mode == "any":
            return expr.Metric("tags").isin(value)
        elif mode == "all":
            # For matching all tags, we need to use isin for now
            # TODO: Implement proper "contains all" logic when available
            return expr.Metric("tags").isin(value)
        else:
            raise ValueError(f"Invalid mode: {mode}. Use 'any' or 'all'")
    
    @staticmethod
    def config(key: str, value: Any = None, operator: str = "=") -> expr.FilterExpr:
        """Filter by config value.
        
        Args:
            key: Config key (supports nested keys with dots, e.g., "model.layers")
            value: Value to compare against (optional for exists check)
            operator: Comparison operator ("=", "!=", "<", ">", "<=", ">=", "in", "contains")
            
        Returns:
            FilterExpr for filtering by config
            
        Example:
            >>> FilterBuilder.config("learning_rate", 0.001)
            >>> FilterBuilder.config("model.type", "transformer")
            >>> FilterBuilder.config("epochs", 50, ">")
        """
        metric = expr.Config(key)
        
        if value is None:
            # Just check if the config key exists by checking it's not equal to None
            # Note: There's no direct exists() method, so we use != None as a workaround
            return metric != None
        
        if operator == "=":
            return metric == value
        elif operator == "!=":
            return metric != value
        elif operator == "<":
            return metric < value
        elif operator == ">":
            return metric > value
        elif operator == "<=":
            return metric <= value
        elif operator == ">=":
            return metric >= value
        elif operator == "in":
            if not isinstance(value, list):
                value = [value]
            return metric.isin(value)
        elif operator == "contains":
            # Use isin with single value as a workaround
            return metric.isin([value])
        else:
            raise ValueError(f"Invalid operator: {operator}")
    
    @staticmethod
    def summary(key: str, value: Any = None, operator: str = "=") -> expr.FilterExpr:
        """Filter by summary metric.
        
        Args:
            key: Summary metric key
            value: Value to compare against (optional for exists check)
            operator: Comparison operator ("=", "!=", "<", ">", "<=", ">=", "in")
            
        Returns:
            FilterExpr for filtering by summary metric
            
        Example:
            >>> FilterBuilder.summary("loss", 0.5, "<")
            >>> FilterBuilder.summary("accuracy", 0.9, ">=")
        """
        metric = expr.Summary(key)
        
        if value is None:
            # Check if summary metric exists by checking it's not equal to None
            return metric != None
        
        if operator == "=":
            return metric == value
        elif operator == "!=":
            return metric != value
        elif operator == "<":
            return metric < value
        elif operator == ">":
            return metric > value
        elif operator == "<=":
            return metric <= value
        elif operator == ">=":
            return metric >= value
        elif operator == "in":
            if not isinstance(value, list):
                value = [value]
            return metric.isin(value)
        else:
            raise ValueError(f"Invalid operator: {operator}")
    
    @staticmethod
    def duration(seconds: float, operator: str = "=") -> expr.FilterExpr:
        """Filter by run duration.
        
        Args:
            seconds: Duration in seconds
            operator: Comparison operator ("=", "!=", "<", ">", "<=", ">=")
            
        Returns:
            FilterExpr for filtering by duration
        """
        metric = expr.Metric("duration")
        
        if operator == "=":
            return metric == seconds
        elif operator == "!=":
            return metric != seconds
        elif operator == "<":
            return metric < seconds
        elif operator == ">":
            return metric > seconds
        elif operator == "<=":
            return metric <= seconds
        elif operator == ">=":
            return metric >= seconds
        else:
            raise ValueError(f"Invalid operator: {operator}")
    
    @staticmethod
    def user(username: Union[str, List[str]]) -> expr.FilterExpr:
        """Filter by user who created the run.
        
        Args:
            username: Username or list of usernames
            
        Returns:
            FilterExpr for filtering by user
        """
        if isinstance(username, str):
            username = [username]
        return expr.Metric("user.username").isin(username)
    
    @staticmethod
    def group(value: Union[str, List[str]]) -> expr.FilterExpr:
        """Filter by run group.
        
        Args:
            value: Group name or list of group names
            
        Returns:
            FilterExpr for filtering by group
        """
        if isinstance(value, str):
            value = [value]
        return expr.Metric("group").isin(value)
    
    @staticmethod
    def created_after(timestamp: Union[str, int]) -> expr.FilterExpr:
        """Filter runs created after a certain time.
        
        Args:
            timestamp: ISO timestamp string or Unix timestamp
            
        Returns:
            FilterExpr for filtering by creation time
        """
        return expr.Metric("createdAt") > timestamp
    
    @staticmethod
    def created_before(timestamp: Union[str, int]) -> expr.FilterExpr:
        """Filter runs created before a certain time.
        
        Args:
            timestamp: ISO timestamp string or Unix timestamp
            
        Returns:
            FilterExpr for filtering by creation time
        """
        return expr.Metric("createdAt") < timestamp
    
    @staticmethod
    def combine(*filters: expr.FilterExpr, operator: str = "and") -> List[expr.FilterExpr]:
        """Combine multiple filters into a list.
        
        Args:
            *filters: FilterExpr objects to combine
            operator: "and" or "or" (currently only "and" is supported)
            
        Returns:
            List of FilterExpr objects
            
        Example:
            >>> f1 = FilterBuilder.name("test_run")
            >>> f2 = FilterBuilder.config("epochs", 50, ">")
            >>> combined = FilterBuilder.combine(f1, f2)
        """
        if not filters:
            raise ValueError("At least one filter must be provided")
        
        if operator == "or":
            raise NotImplementedError("OR operator is not yet supported. Use separate Runsets for OR logic.")
        
        # For AND, just return the list of filters
        return list(filters)


# Convenience function to convert UI field names to internal names
def ui_to_internal_field(ui_name: str) -> str:
    """Convert a UI-friendly field name to the internal field name.
    
    Args:
        ui_name: The field name as shown in the UI
        
    Returns:
        The internal field name
    """
    return UI_TO_INTERNAL_MAPPING.get(ui_name, ui_name)


# Export a simple alias for common use
Filters = FilterBuilder