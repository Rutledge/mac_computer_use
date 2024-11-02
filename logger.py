import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4


class AnthropicJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle Anthropic message types"""

    def default(self, obj):
        # Handle any Pydantic models or objects with model_dump
        if hasattr(obj, "model_dump"):
            return obj.model_dump()
        # Handle Path objects
        if isinstance(obj, Path):
            return str(obj)
        # Handle any objects with a dict representation
        if hasattr(obj, "__dict__"):
            return obj.__dict__
        return super().default(obj)


class TrajectoryLogger:
    def __init__(self):
        self.base_dir = Path("trajectories")
        self.current_trajectory = None
        self.step_counter = 0
        self.screenshot_counter = 0

    def start_trajectory(self) -> str:
        """Start a new trajectory and return its ID"""
        self.current_trajectory = f"t{uuid4().hex[:8]}"
        self.step_counter = 0
        self.screenshot_counter = 0

        # Create trajectory directory
        trajectory_dir = self.base_dir / self.current_trajectory
        trajectory_dir.mkdir(parents=True, exist_ok=True)
        (trajectory_dir / "screenshots").mkdir(exist_ok=True)

        return self.current_trajectory

    def log_step(
        self, messages: list, response: Any, screenshots: Optional[list[str]] = None
    ) -> None:
        """Log a single step in the current trajectory"""
        if not self.current_trajectory:
            raise ValueError("No active trajectory")

        self.step_counter += 1

        # Prepare log data
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "step": self.step_counter,
            "messages": messages,
            "response": response,
            "screenshots": screenshots or [],
        }

        # Save to JSON file using custom encoder
        step_file = (
            self.base_dir / self.current_trajectory / f"{self.step_counter}.json"
        )
        with open(step_file, "w") as f:
            json.dump(log_data, f, indent=2, cls=AnthropicJSONEncoder)

    def save_screenshot(self, base64_image: str) -> str:
        """Save a base64 screenshot and return its path"""
        if not self.current_trajectory:
            raise ValueError("No active trajectory")

        self.screenshot_counter += 1
        screenshot_path = (
            self.base_dir
            / self.current_trajectory
            / "screenshots"
            / f"screenshot_{self.screenshot_counter}.png"
        )

        # Decode and save the image
        import base64

        with open(screenshot_path, "wb") as f:
            f.write(base64.b64decode(base64_image))

        return str(screenshot_path.relative_to(self.base_dir))


# Global logger instance
trajectory_logger = TrajectoryLogger()
