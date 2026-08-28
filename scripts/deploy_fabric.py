import os
from azure.identity import ClientSecretCredential
from fabric_cicd import FabricWorkspace, publish_all_items

# Récupération des credentials et de l'environnement cible depuis les variables d'environnement
tenant_id = os.environ["FABRIC_TENANT_ID"]
client_id = os.environ["FABRIC_CLIENT_ID"]
client_secret = os.environ["FABRIC_CLIENT_SECRET"]
target_env = os.environ["TARGET_ENV"]  # "PRE" ou "PRO"

# Création de l'objet d'authentification
token_credential = ClientSecretCredential(
    tenant_id=tenant_id,
    client_id=client_id,
    client_secret=client_secret,
)

# Mapping environnement → ID du workspace cible
workspace_ids = {
    "PRE": "5a2bdff8-ba6f-4e9e-a78b-0fa4bb0134df",
    "PRO": "236a6aaa-eb37-463a-a7a4-81655beaf427",
}

# Chemin robuste vers le dossier "guide de développeur", peu importe le répertoire de travail courant
script_dir = os.path.dirname(os.path.abspath(__file__))
repository_directory = os.path.abspath(os.path.join(script_dir, "..", "guide de développeur"))

target_workspace = FabricWorkspace(
    workspace_id=workspace_ids[target_env],
    environment=target_env,
    repository_directory=repository_directory,
    item_type_in_scope=["Report"],
    token_credential=token_credential,
)

publish_all_items(target_workspace)
