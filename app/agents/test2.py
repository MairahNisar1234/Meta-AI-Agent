import persistence
persistence.init_db()
agent_id = persistence.save_agent(
    canonical_name="test_agent",
    display_name="Test Agent",
    original_prompt="test prompt",
    category="none",
    source_code_dir="/tmp/some_folder_with_files",
)
print("saved:", agent_id)
print(persistence.get_agent(agent_id))