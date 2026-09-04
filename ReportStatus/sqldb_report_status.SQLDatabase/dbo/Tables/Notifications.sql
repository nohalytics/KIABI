CREATE TABLE [dbo].[Notifications] (
    [NotificationDate]   DATE           NOT NULL,
    [Notification]       VARCHAR (255)  NOT NULL,
    [WorkspaceId]        VARCHAR (255)  NOT NULL,
    [Environment]        VARCHAR (3)    NOT NULL,
    [WorkspaceName]      VARCHAR (255)  NOT NULL,
    [DatasetId]          VARCHAR (255)  NOT NULL,
    [DatasetName]        VARCHAR (255)  NOT NULL,
    [NotificationStatus] VARCHAR (255)  NOT NULL,
    [CreatedBy]          VARCHAR (255)  NOT NULL,
    [NotificationId]     INT            IDENTITY (1, 1) NOT NULL,
    [EndDate]            DATE           NULL,
    [ClearedBy]          VARCHAR (255)  NULL,
    [Link]               VARCHAR (1000) NULL,
    CONSTRAINT [PK_Notifications] PRIMARY KEY CLUSTERED ([NotificationId] ASC)
);


GO

CREATE UNIQUE NONCLUSTERED INDEX [UQ_Notifications_Active]
    ON [dbo].[Notifications]([WorkspaceId] ASC, [DatasetId] ASC) WHERE ([EndDate] IS NULL);


GO

