import fabric.functions as fn
import datetime
import time
import requests
from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient

udf = fn.UserDataFunctions()

# Service principal credentials 
TENANT_ID = "0e2f240d-11ec-48d0-8dbe-8871cf2c1770"
CLIENT_ID = "164bbc75-cfbe-4f56-ab0e-fc84e998f89e"
KEY_VAULT_URL = "https://akv-data-fabric.vault.azure.net/"
SECRET_NAME = "SPNPowerBIAdmin"

########################################################################
## FONCTION - RECUPERATION DU SECRET DEPUIS AZURE KEY VAULT
########################################################################

def get_client_secret(keyVaultClient: fn.FabricItem) -> str:
    credential = keyVaultClient.get_access_token()
    client = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)
    return client.get_secret(SECRET_NAME).value


########################################################################
## FONCTION - RAFRAICHISSEMENT DE LA TABLE _Notifications 
########################################################################

def refresh_table(workspace_id: str, dataset_id: str, client_secret: str) -> None:
    credential = ClientSecretCredential(TENANT_ID, CLIENT_ID, client_secret)
    token = credential.get_token("https://analysis.windows.net/powerbi/api/.default").token

    trigger_url = f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}/datasets/{dataset_id}/refreshes"
    history_url = f"{trigger_url}?$top=1"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    body = {
        "type": "full",
        "commitMode": "transactional",
        "objects": [
            {"table": "_Notifications"}
        ]
    }

    # 1. Déclencher le refresh
    response = requests.post(trigger_url, headers=headers, json=body)

    if response.status_code != 202:
        raise fn.UserThrownError(
            "Le déclenchement du refresh Power BI a échoué.",
            {"status_code": response.status_code, "response": response.text}
        )

    # 2. Poller l'historique jusqu'à Completed / Failed, avec timeout de sécurité
    max_wait_seconds = 180
    poll_interval_seconds = 5
    elapsed = 0

    while elapsed < max_wait_seconds:
        history_response = requests.get(history_url, headers=headers)

        if history_response.status_code != 200:
            raise fn.UserThrownError(
                "Impossible de vérifier l'historique de refresh Power BI.",
                {"status_code": history_response.status_code, "response": history_response.text}
            )

        latest_refresh = history_response.json().get("value", [{}])[0]
        status = latest_refresh.get("status")

        if status == "Completed":
            return
        elif status == "Failed":
            raise fn.UserThrownError(
                "Le refresh de la table Power BI a échoué.",
                {"error": latest_refresh.get("serviceExceptionJson", "Détail non disponible")}
            )
        # "Unknown" = toujours en cours, on continue

        time.sleep(poll_interval_seconds)
        elapsed += poll_interval_seconds

    raise fn.UserThrownError(
        "Le refresh de la table Power BI n'a pas terminé dans le temps imparti.",
        {}
    )

##################################################################################
## UDF FONCTION - ENREGISTRER UN STATUS POUR UN WORKSPACE ET DATASET EN SPECIFIQUE
##################################################################################
@udf.connection(argName="sqlDB", alias="sqldbreportstat")
@udf.generic_connection(argName="keyVaultClient", audienceType="KeyVault")
@udf.function()
def insert_notification(
    sqlDB: fn.FabricSqlConnection,
    keyVaultClient: fn.FabricItem,
    workspaceId: str,
    workspaceName: str,
    datasetId: str,
    datasetName: str,
    createdBy: str,
    notification: str,
    notificationStatus: str,
    environment: str,
    Link: str= ""
) -> str:

    if len(notification) > 255:
        raise fn.UserThrownError(
            "Le message de notification dépasse la limite de 255 caractères.",
            {"Notification:": notification}
        )

    notification_date = datetime.date.today()

    # Convertit une saisie vide en NULL plutôt qu'en chaîne vide
    easy_it_link_value = Link if Link else None

    connection = sqlDB.connect()
    cursor = connection.cursor()

    # 1. Clôturer l'éventuelle notification active existante pour ce workspace/dataset
    close_query = """
        UPDATE dbo.Notifications
        SET EndDate = ?
        WHERE WorkspaceId = ? AND DatasetId = ? AND EndDate IS NULL
    """
    cursor.execute(close_query, (notification_date, workspaceId, datasetId))

    # 2. Insérer la nouvelle ligne active (EndDate = NULL)
    insert_query = """
        INSERT INTO dbo.Notifications
            (NotificationDate, Notification, WorkspaceId, Environment, WorkspaceName, DatasetId, DatasetName, NotificationStatus, CreatedBy, Link, EndDate, ClearedBy)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
    """
    cursor.execute(
        insert_query,
        (notification_date, notification, workspaceId, environment ,workspaceName, datasetId, datasetName, notificationStatus, createdBy, easy_it_link_value)
    )

    connection.commit()
    cursor.close()
    connection.close()

    client_secret = get_client_secret(keyVaultClient)
    refresh_table(workspaceId, datasetId, client_secret)

    return "Notification enregistrée avec succès"


##################################################################################
## UDF FONCTION - CLOTURER LA NOTIFICATION
##################################################################################

@udf.connection(argName="sqlDB", alias="sqldbreportstat")
@udf.generic_connection(argName="keyVaultClient", audienceType="KeyVault")
@udf.function()
def remove_notification(
    sqlDB: fn.FabricSqlConnection, 
    keyVaultClient: fn.FabricItem,
    notificationId: int, 
    ClearedBy: str
    ) -> str:

    connection = sqlDB.connect()
    cursor = connection.cursor()

    select_query = "SELECT WorkspaceId, DatasetId, EndDate FROM dbo.Notifications WHERE NotificationId = ?"
    cursor.execute(select_query, notificationId)
    row = cursor.fetchone()

    if row is None:
        cursor.close()
        connection.close()
        raise fn.UserThrownError(
            "Aucune notification trouvée avec cet identifiant.",
            {"NotificationId:": notificationId}
        )

    workspaceId, datasetId, endDate = row

    if endDate is not None:
        cursor.close()
        connection.close()
        raise fn.UserThrownError(
            "Cette notification est déjà clôturée.",
            {"NotificationId:": notificationId}
        )

    close_date = datetime.date.today()
    update_query = "UPDATE dbo.Notifications SET EndDate = ?, ClearedBy=? WHERE NotificationId = ?"
    cursor.execute(update_query, (close_date, ClearedBy, notificationId))

    if cursor.rowcount == 0:
        connection.rollback()
        cursor.close()
        connection.close()
        raise fn.UserThrownError(
            "La clôture a échoué.",
            {"NotificationId:": notificationId}
        )

    connection.commit()
    cursor.close()
    connection.close()

    client_secret = get_client_secret(keyVaultClient)
    refresh_table(workspaceId, datasetId, client_secret)

    return "Notification clôturée avec succès"