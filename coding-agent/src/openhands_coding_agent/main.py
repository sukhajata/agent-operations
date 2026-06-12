import json
import os
import re
import sys
import uuid
from pathlib import Path

from dotenv import find_dotenv, load_dotenv
from openhands.sdk import (
    AgentContext,
    Conversation,
    Event,
    LLMConvertibleEvent,
    OpenHandsAgentSettings,
    get_logger,
    load_project_skills,
    load_skills_from_dir,
)
from openhands.sdk.conversation.exceptions import ConversationRunError
from openhands.sdk.event import ActionEvent
from openhands.sdk.settings import CondenserSettings
from openhands.sdk.tool import Tool
from openhands.tools.browser_use import BrowserToolSet
from openhands.tools.file_editor import FileEditorTool
from openhands.tools.glob import GlobTool
from openhands.tools.grep import GrepTool
from openhands.tools.preset.default import register_builtins_agents
from openhands.tools.task import TaskToolSet
from openhands.tools.task_tracker import TaskTrackerTool
from openhands.tools.terminal import TerminalTool
from pydantic import SecretStr

PACKAGE_DIR = Path(__file__).parent

# Search CWD and all parent directories for .env so the agent picks up
# configuration whether invoked from the repo root or a subdirectory.
load_dotenv(find_dotenv(usecwd=True, raise_error_if_not_found=False))

logger = get_logger(__name__)


DEFAULT_MAX_COST_USD = 5.00
DEFAULT_MAX_ITERATIONS = 500
DEFAULT_CONDENSER_MAX_SIZE = 100
DEFAULT_PERSISTENCE_DIR = ".openhands/conversations"
DEFAULT_LLM_MODEL = "openrouter/deepseek/deepseek-v4-pro"


def load_mcp_config(path: str = "mcp_config.json") -> dict | None:
    """Load MCP server configuration from a JSON file.

    Resolves relative paths against the package directory so the config is
    found correctly whether the agent is run from the repo or installed globally.

    Args:
        path: Path to the MCP config file. Relative paths are resolved against
            the package directory (i.e. the directory containing this file).

    Returns:
        Parsed config dict, or None if the file does not exist.
    """
    resolved = Path(path) if Path(path).is_absolute() else PACKAGE_DIR / path
    if not resolved.exists():
        return None
    with open(resolved) as f:
        return json.load(f)


def load_agent_skills(workspace_dir: str) -> list:
    """Load skills from the package and from the target workspace.

    Skills are loaded in two layers:
    1. Package-level skills (AGENTS.md + skills/ bundled with this agent).
    2. Workspace-level skills (AGENTS.md + skills/ from the target repo), if
       the workspace is a different directory from the package.

    This ensures the base agent instructions always load first, with
    project-specific skills layered on top.

    Args:
        workspace_dir: Absolute path to the target workspace (usually CWD).

    Returns:
        List of loaded skill objects ready to pass to AgentContext.
    """
    skills = []

    # Always load the package's own AGENTS.md and skills/ first
    package_skills = load_project_skills(work_dir=PACKAGE_DIR)
    if package_skills:
        skills.extend(package_skills)
        logger.info("Loaded %d package skill(s)", len(package_skills))

    package_skills_dir = PACKAGE_DIR / "skills"
    if package_skills_dir.exists():
        _, _, agent_skills = load_skills_from_dir(package_skills_dir)
        if agent_skills:
            skills.extend(agent_skills.values())
            logger.info("Loaded %d skill(s) from package skills/ directory", len(agent_skills))

    # Also load project-specific skills from the target workspace
    if Path(workspace_dir) != PACKAGE_DIR:
        project_skills = load_project_skills(work_dir=workspace_dir)
        if project_skills:
            skills.extend(project_skills)
            logger.info("Loaded %d project skill(s) from workspace", len(project_skills))

        skills_dir = Path(workspace_dir) / "skills"
        if skills_dir.exists():
            _, _, agent_skills = load_skills_from_dir(skills_dir)
            if agent_skills:
                skills.extend(agent_skills.values())
                logger.info("Loaded %d skill(s) from workspace skills/ directory", len(agent_skills))

    return skills


def main():
    """Entry point for the coding agent CLI.

    All configuration is via environment variables (or a .env file searched
    from CWD upward). Only LLM_API_KEY is required.

    Optional env vars (all have sensible defaults):
        LLM_MODEL, LLM_BASE_URL, MAX_COST_USD, MAX_ITERATIONS, CONDENSER_MAX_SIZE

    Exits with code 1 if LLM_API_KEY is not set.
    """
    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        print("Error: LLM_API_KEY is not set. Add it to your .env file or set it as an environment variable.")
        sys.exit(1)

    max_cost = float(os.getenv("MAX_COST_USD", DEFAULT_MAX_COST_USD))
    max_iterations = int(os.getenv("MAX_ITERATIONS", DEFAULT_MAX_ITERATIONS))
    condenser_max_size = int(os.getenv("CONDENSER_MAX_SIZE", DEFAULT_CONDENSER_MAX_SIZE))

    # Persistence: always enabled so runs can be resumed.
    # RESUME_CONVERSATION_ID resumes a previous run; omit it to start fresh.
    persistence_dir = os.getenv("PERSISTENCE_DIR", DEFAULT_PERSISTENCE_DIR)
    resume_id_str = os.getenv("RESUME_CONVERSATION_ID")
    if resume_id_str:
        try:
            conversation_id = uuid.UUID(resume_id_str)
        except ValueError:
            print(f"Error: RESUME_CONVERSATION_ID '{resume_id_str}' is not a valid UUID.")
            sys.exit(1)
        resuming = True
    else:
        conversation_id = uuid.uuid4()
        resuming = False

    llm_config = {
        "usage_id": "agent",
        "api_key": SecretStr(api_key),
        "model": os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL),
    }
    if os.getenv("LLM_BASE_URL"):
        llm_config["base_url"] = os.getenv("LLM_BASE_URL")

    # OpenRouter provider routing: pin to specific providers and control fallbacks.
    # Only applied when the model string starts with "openrouter/".
    if llm_config["model"].startswith("openrouter/"):
        providers_env = os.getenv("OPENROUTER_PROVIDERS", "").strip()
        if providers_env:
            provider_order = [p.strip() for p in providers_env.split(",") if p.strip()]
            allow_fallbacks_str = os.getenv("OPENROUTER_ALLOW_FALLBACKS", "true").lower()
            allow_fallbacks = allow_fallbacks_str not in ("false", "0", "no")
            llm_config["extra_body"] = {
                "provider": {
                    "order": provider_order,
                    "allow_fallbacks": allow_fallbacks,
                }
            }
            logger.info(
                "OpenRouter provider routing: order=%s, allow_fallbacks=%s",
                provider_order,
                allow_fallbacks,
            )

    cwd = os.getcwd()

    # Register built-in sub-agent types (general-purpose, bash-runner,
    # code-explorer) so TaskToolSet can spawn them.
    register_builtins_agents()

    skills = load_agent_skills(cwd)
    mcp_config = load_mcp_config()

    settings = OpenHandsAgentSettings(
        llm=llm_config,
        tools=[
            Tool(name=TerminalTool.name),
            Tool(name=FileEditorTool.name),
            Tool(name=GlobTool.name),
            Tool(name=GrepTool.name),
            Tool(name=TaskTrackerTool.name),
            Tool(name=TaskToolSet.name),
            Tool(name=BrowserToolSet.name),
        ],
        condenser=CondenserSettings(enabled=True, max_size=condenser_max_size),
        agent_context=AgentContext(
            skills=skills,
            load_public_skills=False,
        ),
        mcp_config=mcp_config,
    )

    if mcp_config:
        logger.info("Loaded MCP config with servers: %s", list(mcp_config.get("mcpServers", {}).keys()))

    agent = settings.create_agent()
    llm_messages: list = []
    cost_cap_hit = False
    sub_agent_tasks: list[str] = []

    def conversation_callback(event: Event):
        nonlocal cost_cap_hit
        if isinstance(event, LLMConvertibleEvent):
            llm_messages.append(event.to_llm_message())

        # Track sub-agent spawns so we can report them in the summary.
        if isinstance(event, ActionEvent) and event.tool_name == "task" and event.action is not None:
            desc = getattr(event.action, "description", None)
            subagent_type = getattr(event.action, "subagent_type", "unknown")
            label = desc if desc else subagent_type
            sub_agent_tasks.append(label)

        current_cost = agent.llm.metrics.accumulated_cost
        if current_cost >= max_cost and not cost_cap_hit:
            cost_cap_hit = True
            logger.warning("Cost cap of $%.2f reached ($%.4f spent). Interrupting agent.", max_cost, current_cost)
            conversation.interrupt()

    logger.info(
        "Safety caps: max_cost=$%.2f, max_iterations=%d, condenser_max_size=%d",
        max_cost,
        max_iterations,
        condenser_max_size,
    )
    logger.info(
        "%s conversation %s (persistence: %s)",
        "Resuming" if resuming else "Starting new",
        conversation_id,
        persistence_dir,
    )

    conversation = Conversation(
        agent=agent,
        callbacks=[conversation_callback],
        workspace=cwd,
        persistence_dir=persistence_dir,
        conversation_id=conversation_id,
        max_iteration_per_run=max_iterations,
        stuck_detection=True,
    )

    task = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else None
    if not task:
        task = input("What would you like the agent to do? ")

    if not task.strip():
        print("No task provided. Exiting.")
        sys.exit(0)

    print(f"Conversation ID: {conversation_id}")
    logger.info("Starting agent with task: %s", task)
    conversation.send_message(task)
    try:
        conversation.run()
    except ConversationRunError as e:
        print("\n" + "=" * 80)
        print("❌  Agent run failed.")
        cause = e.__cause__ or e
        cause_str = str(cause)
        print(f"   {cause_str}")
        if _is_tool_json_error(cause_str):
            print()
            print("   ⚠️  The model produced malformed tool-call JSON.")
            print("   This is a model compatibility issue — not a bug in the agent.")
            model = os.environ.get("LLM_MODEL", "<not set>")
            print(f"   Model in use: {model}")
            print("   Switch to a model with reliable function-calling support, e.g.:")
            print("     LLM_MODEL=anthropic/claude-sonnet-4-5")
            print("     LLM_MODEL=openai/gpt-4o")
        _print_summary(agent, max_cost, skills, conversation, sub_agent_tasks, conversation_id, llm_messages)
        sys.exit(1)

    print("\n" + "=" * 80)
    if cost_cap_hit:
        print("⚠️  Agent interrupted: cost cap reached.")
    elif conversation.stuck_detector and conversation.stuck_detector.is_stuck():
        print("⚠️  Agent interrupted: stuck pattern detected.")
    else:
        print("Agent finished.")
    _print_summary(agent, max_cost, skills, conversation, sub_agent_tasks, conversation_id, llm_messages)


def _extract_tier(llm_messages: list) -> str | None:
    """Scan assistant messages for the tier classification stated at run start.

    Returns the tier number as a string ("0"–"4"), or None if not found
    (e.g. the run aborted before classification).
    """
    pattern = re.compile(r"\bTier\s+([0-4])\b")
    for msg in llm_messages:
        if not isinstance(msg, dict) or msg.get("role") != "assistant":
            continue
        content = msg.get("content", "")
        if isinstance(content, list):
            text = " ".join(
                block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text"
            )
        else:
            text = str(content)
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


def _is_tool_json_error(error_str: str) -> bool:
    """Return True if the error looks like the model produced malformed tool-call JSON."""
    indicators = [
        "invalid_parameter_error",
        "function.arguments",
        "unparseable JSON",
        "JSON format",
        "must be in JSON",
        "Error validating tool",
    ]
    lower = error_str.lower()
    return any(ind.lower() in lower for ind in indicators)


def _print_summary(
    agent,
    max_cost: float,
    skills: list,
    conversation,
    sub_agent_tasks: list[str],
    conversation_id: uuid.UUID,
    llm_messages: list,
) -> None:
    """Print the post-run cost, tier, skills, sub-agent, and resume summary."""
    cost = agent.llm.metrics.accumulated_cost
    print(f"LLM cost: ${cost:.4f} (cap: ${max_cost:.2f})")

    tier = _extract_tier(llm_messages)
    if tier is not None:
        print(f"Tier: {tier}")
    else:
        print("Tier: unknown (aborted before classification or not stated)")

    # Skills: combine trigger-activated and explicitly invoked, deduplicated.
    activated = list(conversation.state.activated_knowledge_skills)
    invoked = list(conversation.state.invoked_skills)
    all_skills = list(dict.fromkeys(activated + invoked))
    if all_skills:
        print(f"Skills used: {', '.join(all_skills)}")
    else:
        print(f"Skills loaded: {len(skills)} (none triggered during this run)")

    # Sub-agents spawned via TaskToolSet.
    if sub_agent_tasks:
        print(f"Sub-agents run ({len(sub_agent_tasks)}):")
        for label in sub_agent_tasks:
            print(f"  - {label}")

    # Always print the conversation ID so users can resume if needed.
    print(f"Conversation ID: {conversation_id}")
    print(f'To resume: RESUME_CONVERSATION_ID={conversation_id} coding-agent "RESUME: <what was in progress>"')
    print("  Use 'RESUME: ...' to continue an interrupted task; omit it to start a new task in the same conversation.")


if __name__ == "__main__":
    main()
