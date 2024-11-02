import json
import os
from pathlib import Path
from typing import List, Dict, Any
import base64


def analyze_trajectory_and_improve_prompt(
    trajectory_path: str,
    original_prompt: str,
    anthropic_client: Any,
) -> str:
    """
    Analyzes a trajectory log to identify mistakes and potential optimizations,
    then generates an improved task prompt with helpful nudges.

    Args:
        trajectory_path: Path to the trajectory directory
        original_prompt: The original task prompt
        anthropic_client: Initialized Anthropic client for LLM analysis

    Returns:
        Improved prompt with embedded helpful hints
    """
    # Load and parse trajectory data
    trajectory_dir = Path(trajectory_path)
    if not trajectory_dir.exists():
        raise ValueError(f"Trajectory directory not found: {trajectory_path}")

    # Get all step files in order
    step_files = sorted(
        [
            f
            for f in trajectory_dir.glob("*.json")
            if f.name.replace(".json", "").isdigit()
        ],
        key=lambda x: int(x.stem),
    )

    # Add print for number of step files found
    print(f"Found {len(step_files)} trajectory steps to analyze")

    # Collect all steps data
    steps_data = []
    for step_file in step_files:
        with open(step_file) as f:
            steps_data.append(json.load(f))

    # Prepare trajectory summary for LLM analysis
    trajectory_summary = _create_trajectory_summary(steps_data)

    # Get the last 3 screenshots from the trajectory
    trajectory_screenshots = Path(trajectory_dir) / "screenshots"
    screenshot_files = sorted(trajectory_screenshots.glob("*.png"))

    image_data_list = []
    if screenshot_files:
        # Take last 3 screenshots (or all if less than 3)
        last_screenshots = screenshot_files[-3:]

        # Read and encode each image
        for screenshot in last_screenshots:
            with open(screenshot, "rb") as img_file:
                image_data = base64.b64encode(img_file.read()).decode()
                image_data_list.append(image_data)

    # Ask LLM to analyze the trajectory
    print("\nRequesting LLM analysis...")
    analysis = _get_llm_analysis(
        trajectory_summary=trajectory_summary,
        image_data_list=image_data_list,
        original_prompt=original_prompt,
        client=anthropic_client,
    )

    return analysis


def _create_trajectory_summary(steps_data: List[Dict[str, Any]]) -> str:
    """Creates a structured summary of the trajectory for LLM analysis."""
    summary = []

    for step in steps_data:
        step_summary = {
            "timestamp": step["timestamp"],
            "actions": _extract_actions(step["messages"]),
            "errors": _extract_errors(step["response"]),
            "tool_usage": _extract_tool_usage(step["messages"]),
            "screenshots": len(step.get("screenshots", [])),
        }
        summary.append(step_summary)

    return json.dumps(summary, indent=2)


def _extract_actions(messages: List[Dict[str, Any]]) -> List[str]:
    """Extracts key actions from messages."""
    actions = []
    for msg in messages:
        if msg.get("role") == "assistant":
            for content in msg.get("content", []):
                if content.get("type") == "tool_use":
                    actions.append(f"{content['name']}: {content['input']}")
    return actions


def _extract_errors(response: Dict[str, Any]) -> List[str]:
    """Extracts errors from response."""
    errors = []
    for content in response.get("content", []):
        if content.get("type") == "tool_result" and content.get("is_error"):
            errors.append(content.get("content", ""))
    return errors


def _extract_tool_usage(messages: List[Dict[str, Any]]) -> Dict[str, int]:
    """Analyzes tool usage patterns."""
    tool_counts = {}
    for msg in messages:
        if msg.get("role") == "assistant":
            for content in msg.get("content", []):
                if content.get("type") == "tool_use":
                    tool_name = content["name"]
                    tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
    return tool_counts


def _get_llm_analysis(
    trajectory_summary: str,
    image_data_list: List[str],
    original_prompt: str,
    client: Any,
) -> Any:
    """Uses LLM to analyze trajectory and identify improvements."""

    # Determine media type (assuming PNG)
    media_type = "image/png"

    # Read and format the analysis prompt template
    with open("meta.txt") as f:
        prompt_template = f.read()

    # Format the template with trajectory and prompt
    analysis_prompt = prompt_template.replace(
        "{{TRAJECTORY}}", trajectory_summary
    ).replace("{{PROMPT}}", original_prompt)

    # Prepare the message content
    message_content = [{"type": "text", "text": analysis_prompt}]

    # Add images if available
    for image_data in image_data_list:
        message_content.insert(
            0,
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": image_data,
                },
            },
        )

    response = client.messages.create(
        model="claude-3-5-sonnet-20241022",
        max_tokens=2000,
        messages=[
            {"role": "user", "content": message_content},
        ],
    )

    # Parse the JSON response
    response = response.content[0].text

    # Extract JSON between <json_output> tags
    start_tag = "<json_output>"
    end_tag = "</json_output>"

    start_index = response.find(start_tag)
    end_index = response.find(end_tag)
    json_str = response[start_index + len(start_tag) : end_index]
    json_str = json_str.replace("\n", " ")
    json_str = json_str.strip()

    return json.loads(json_str)


def main():
    from anthropic import Anthropic
    from dotenv import load_dotenv
    import glob

    load_dotenv()

    # Get latest trajectory directory
    trajectory_dirs = glob.glob("trajectories/t*")
    latest_trajectory = max(trajectory_dirs)
    trajectory_num = latest_trajectory.split("/")[-1].replace("t", "")

    # Load previous prompt if it exists
    latest_prompt = ""
    path_latest_prompt = f"prompts/p{int(trajectory_num)-1}.txt"
    if os.path.exists(path_latest_prompt):
        with open(path_latest_prompt) as f:
            latest_prompt = f.read()

    # Analyze trajectory and get improved prompt
    client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    response = analyze_trajectory_and_improve_prompt(
        trajectory_path=latest_trajectory,
        original_prompt=latest_prompt,
        anthropic_client=client,
    )

    # Save improved prompt
    os.makedirs("prompts", exist_ok=True)
    with open(f"prompts/p{trajectory_num}.txt", "w") as f:
        f.write(response["improved_prompt"])


if __name__ == "__main__":
    main()
