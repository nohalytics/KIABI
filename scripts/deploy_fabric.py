import os
from azure.identity import ClientSecretCredential
from fabric_cicd import FabricWorkspace, publish_all_items

tenant_id = os.environ["FABRIC_TENANT_ID"]
client_id = os.environ["FABRIC_CLIENT_ID"]
client_secret = os.environ["FABRIC_CLIENT_SECRET"]
target_env = os.environ["TARGET_ENV"]  # "PRE" ou "PRO"

token_credential = ClientSecretCredential(
    tenant_id=tenant_id,
    client_id=client_id,
    client_secret=client_secret,
)

workspace_ids = {
    "PRE": "5a2bdff8-ba6f-4e9e-a78b-0fa4bb0134df/",
    "PRO": "236a6aaa-eb37-463a-a7a4-81655beaf427",
}

target_workspace = FabricWorkspace(
    workspace_id=workspace_ids[target_env],
    environment=target_env,
    repository_directory="./<nom-du-dossier-de-ton-pbip>",
    item_type_in_scope=["Report"],
    token_credential=token_credential,
)

publish_all_items(target_workspace)
