"""GraphQL queries and mutations."""

from wandb_gql import gql

view_report = gql(
    """
    query SpecificReport($reportId: ID!) {
        view(id: $reportId) {
            id
            name
            displayName
            description
            project {
                id
                name
                entityName
            }
            createdAt
            updatedAt
            spec
        }
    }
    """
)
upsert_view = gql(
    """
    mutation upsertView(
        $id: ID
        $entityName: String
        $projectName: String
        $type: String
        $name: String
        $displayName: String
        $description: String
        $spec: String!
    ) {
        upsertView(
        input: {
            id: $id
            entityName: $entityName
            projectName: $projectName
            name: $name
            displayName: $displayName
            description: $description
            type: $type
            createdUsing: WANDB_SDK
            spec: $spec
        }
        ) {
        view {
            id
            type
            name
            displayName
            description
            project {
                id
                name
            entityName
            }
            spec
            updatedAt
        }
        inserted
        }
    }
"""
)

# Mutation to delete a report (view) given its ID.
# Accepts a flag to also delete any associated draft views.
# Mirrors the save/upsert structure above.
delete_view = gql(
    """
    mutation deleteView($id: ID!, $deleteDrafts: Boolean) {
        deleteView(input: { id: $id, deleteDrafts: $deleteDrafts }) {
            success
            pendingDrafts
            __typename
        }
    }
    """
)

projectInternalId = gql(
    """
    query ProjectInternalId($projectName: String!, $entityName: String!) {
        project(name: $projectName, entityName: $entityName) {
            id
            internalId
        }
    }
    """
)
