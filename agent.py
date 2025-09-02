import os
import asyncio
import re
from dotenv import load_dotenv
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient
import git
import yaml

# --- Load .env ---
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY not found in .env file!")

# --- Config ---
REPO_PATH = os.path.dirname(os.path.abspath(__file__))
REPO_URL = "https://github.com/victorrathore/autogen-harness-agent.git"  # your repo
HARNESS_FILE = os.path.join(REPO_PATH, ".harness", "pipeline.yaml")

# --- Ensure .harness dir exists ---
os.makedirs(os.path.join(REPO_PATH, ".harness"), exist_ok=True)

# --- Clone or init repo ---
if not os.path.exists(os.path.join(REPO_PATH, ".git")):
    repo = git.Repo.init(REPO_PATH)
else:
    repo = git.Repo(REPO_PATH)

# --- Ensure main branch exists ---
if repo.head.is_detached or repo.active_branch.name != "main":
    if "main" in repo.heads:
        repo.head.reference = repo.heads["main"]
    else:
        repo.git.checkout("-b", "main")

# --- Autogen Agent prompt ---
prompt = """
Generate a Harness.io pipeline YAML file for deploying a static HTML site.
Requirements:
1. Pipeline should have a build-and-deploy stage.
2. It should checkout code from GitHub.
3. Run a simple shell step that ensures index.html exists.
4. Push changes to GitHub main branch.
Return only valid YAML content (no markdown).
"""

# --- Initialize Agent ---
model_client = OpenAIChatCompletionClient(model="gpt-4o", api_key=api_key)
agent = AssistantAgent(
    name="assistant",
    model_client=model_client
)

async def main():
    # --- Generate pipeline asynchronously ---
    pipeline_task = await agent.run(task=prompt)
    pipeline_text = pipeline_task.messages[-1].content

    # --- Clean code fences ---
    pipeline_text = re.sub(r"```[a-zA-Z]*", "", pipeline_text)
    pipeline_text = pipeline_text.replace("```", "").strip()

    # --- Validate YAML ---
    try:
        yaml.safe_load(pipeline_text)
    except yaml.YAMLError as e:
        print("YAML syntax error:", e)
        raise

    # --- Save Harness pipeline ---
    with open(HARNESS_FILE, "w") as f:
        f.write(pipeline_text)
    print("Harness pipeline generated at:", HARNESS_FILE)

    # --- Git commit & push only if changes ---
    if repo.is_dirty(untracked_files=True):
        repo.git.add(all=True)
        repo.index.commit("Autogen update: Harness pipeline")
        if "origin" not in [r.name for r in repo.remotes]:
            origin = repo.create_remote("origin", REPO_URL)
        else:
            origin = repo.remote(name="origin")
        origin.push(refspec="main:main")
        print("Changes committed and pushed to GitHub")
    else:
        print("No changes to commit. Agent finished.")

# Run async main
asyncio.run(main())
