from typing import Any
from azure.data.tables import TableServiceClient, TableClient
from log import setup_logging

logger = setup_logging()

def load_jobs_config(users_table: TableClient, current_user: str) -> dict[str, Any]:
    try:
        user_settings = users_table.get_entity(current_user, row_key='0')
        return user_settings["job_settings"]
    except Exception as e:
        logger.error(f"Error loading jobs_config: {e}")
        return {}

def save_jobs_config(jobs_config: dict[str, Any], connection_string: str, current_user: str) -> bool:
    try:
        with TableServiceClient(connection_string) as table_service_client:
            table_client = table_service_client.get_table_client("herousers")
            user_settings = table_client.get_entity(current_user, row_key='0')
            user_settings["job_settings"] = jobs_config
            table_client.upsert_entity(user_settings)
            return True
    except Exception as e:
        logger.error(f"Error saving jobs_config: {e}")
        return False
