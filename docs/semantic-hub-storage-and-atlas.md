# Semantic Hub: workflow state, artifact storage, and Atlas integration

Recorded: 13 October 2026.
This document captures the customer architecture discussion and distinguishes implemented features from the proposed enterprise design.

## Customer-facing answer

> The current demo persists workflow and review state in SQLite.
> Embeddings use local Lance tables through embedded LanceDB.
> Semantic Hub retains the model definitions, evidence, approvals, and version history.
> For an enterprise deployment, we propose PostgreSQL for workflow state and object storage for documents, vectors, and model artifacts.
> Atlas would provide enterprise catalog, glossary, and lineage integration.
> Existing Atlas code provides a starting point, but the new Hub workflow is not yet connected to it.

## Storage responsibilities

| Information | Current implementation | Proposed enterprise storage |
| --- | --- | --- |
| Intermediate results, AI proposals, draft revisions, validation, and approvals | SQLite | PostgreSQL |
| Uploaded documents and extracted content | SQLite, including original file bytes | Object storage for files; PostgreSQL for state and references |
| Embeddings | Local Lance tables through embedded LanceDB | Lance tables in object storage |
| Generated Ossie models | Local source-pack JSON files; reviewed models also captured in SQLite releases | Immutable, versioned artifact bundles in object storage |
| Ontology and business metadata | JSON within versioned artifact bundles | Canonical bundles in object storage; searchable representations in Atlas |
| Catalog discovery and lineage | Local Hub catalog and canvas | Atlas integration |
| Sample SQL execution | DuckDB over local source snapshots | A supported query engine connected to the relevant data source |

DuckDB executes sample queries and validation.
SQLite stores workflow state and review history.
These components have different responsibilities.

## How intermediate-stage tracking works today

The application records extraction results, AI proposals, review decisions, validation reports, and model releases.
It also records document-to-model associations and draft application history.
Draft revision checks prevent stale updates.
Published releases capture the reviewed definition and its associated artifacts.

Saved stage results survive an application restart when the state directory remains available.
The current implementation is not a durable background-job system that automatically resumes an interrupted LLM request.
Production work would add persistent job records, retry policies, idempotency controls, and worker recovery.

The visual workflow has a narrower recovery mechanism already implemented.
It saves the pending review decision before creating a fact model.
An interrupted creation can resume using that same decision.
This does not establish recovery for every processing stage.

| Store | Contents |
| --- | --- |
| `supporting-materials.sqlite` | Document revisions, original bytes, extraction results, analysis, reviewed links, and application history |
| Source-specific `context.sqlite` | Drafts, proposals, validation, object decisions, reviewed releases, publication records, and builder attachments |
| `connections.sqlite` | Data-source connection profiles |
| `llm-settings.sqlite` | Model configuration and credential references |
| `supporting-material-vectors.lancedb/` | Lance tables containing embedding vectors and their text/model fingerprints |
| `document-models/` | Immutable source packs generated from explicitly reviewed document observations |

The running review instance uses `/tmp/helios-builder-review` as its state root.
That temporary path is a local development choice.
A deployed instance should use a persistent storage location.

Built-in source workspaces use `<pack-id>/<snapshot-hash>/context.sqlite` beneath the state root.
Additional connections use a separate connection namespace beneath `connections/<source-id>/`.
The source snapshot hash binds a workspace to its underlying data.

## Where Lance data can live

Lance supports local storage, S3 and compatible stores, Azure Blob Storage, and Google Cloud Storage.
The storage URI selects the backend.
Authentication and storage options require configuration for the selected environment.
See the [Lance object-store documentation](https://lance.org/guide/object_store/).

Our current wrapper uses a local filesystem path.
Remote storage configuration and deployment testing remain implementation work.
Changing the local state path to an object-store URI is not sufficient with the current wrapper.

Lance stores embeddings and their associated records.
It does not replace the workflow database or the SQL execution engine.
Atlas would catalog references to this data rather than store the vector payloads.

## Proposed enterprise layout

```text
Semantic Hub
 |
 +-- PostgreSQL
 |    +-- Workflow state and job records
 |    +-- Review decisions and publication records
 |    +-- Artifact references and synchronization status
 |
 +-- Object storage
 |    +-- Original documents
 |    +-- Lance datasets and indexes
 |    +-- Versioned semantic bundles
 |         +-- model.ossie.json
 |         +-- metadata.json
 |         +-- ontology.json
 |         +-- source-mapping.json
 |         +-- Evidence and validation manifests
 |
 +-- Atlas
      +-- Catalog entities and glossary terms
      +-- Classifications and relationships
      +-- Artifact locations, versions, and lineage
```

This layout is proposed, not deployed.
The filenames illustrate an export structure; they are not the current on-disk layout for every release.

Today, reviewed releases already contain semantic definitions, metadata, ontology, evidence, and validation information.
The release bundle is stored in SQLite.
Document-derived source packs also contain local files such as `draft.ossie.json`, `metadata.json`, and source manifests.

The enterprise design would export each published version as an immutable bundle.
PostgreSQL would reference its location, version identifier, and checksums.
Atlas would expose its searchable catalog representation.
Later Atlas edits would not silently rewrite a published Hub version.

## Atlas integration: existing foundation and remaining work

Atlas provides APIs for entities, relationships, glossary terms, classifications, and lineage.
These APIs support registering semantic models and connecting them to enterprise data assets.
See the [Apache Atlas API documentation](https://atlas.apache.org/api/v2/ui/index.html).

The wider Helios repository already contains:

- An Atlas REST client for glossary operations, term assignments, entity lookup, and lineage reads.
- Harvesting code that can collect glossary terms and their assigned entities.
- Existing console and API paths for Atlas glossary operations.

The new local Hub currently saves Atlas connection profiles.
Importing Atlas metadata into this workflow and synchronizing published releases are not yet connected or verified.
An Atlas profile alone does not provide a SQL query source.

The proposed integration sequence is:

1. Import existing table identities, glossary terms, and lineage from Atlas.
2. Use that information as evidence when drafting semantic definitions.
3. Preserve the imported evidence within the reviewed model version.
4. Register published models, metrics, and supporting-document relationships in Atlas.
5. Store artifact URIs, checksums, and version identifiers on those catalog entries.
6. Record synchronization status and retry failed catalog updates without changing the approved model version.

This integration needs agreed entity types and identity mappings.
For example, a Hub model version could reference Atlas table entities and glossary terms.
Document-support relationships should remain distinct from SQL dependencies and observed execution lineage.
The local ontology graph is a structural proposal; publishing it to Atlas does not establish enterprise ontology certification.

## Ownership of records

Semantic Hub owns semantic authoring, approval, and version history.
The workflow database owns processing state and review records.
Object storage retains the original files, Lance data, and canonical artifact bundles.
Atlas provides enterprise discovery and catalog relationships.

We should agree which system owns each synchronized field before enabling updates in both directions.
For example, Atlas may supply enterprise glossary terms while Hub owns a published metric definition.
Stable identifiers, version bindings, and checksums connect these records without requiring all content in one database.

## Implementation references

- [Context workspace and release storage](../shared/helios_core/demo/context.py)
- [Proposal staging](../shared/helios_core/demo/proposals.py)
- [Supporting-material state](../shared/helios_core/demo/materials.py)
- [Lance vector storage](../shared/helios_core/demo/lance_vectors.py)
- [Metadata and ontology bundles](../shared/helios_core/demo/builder_artifacts.py)
- [Document-derived source packs](../shared/helios_core/demo/document_facts.py)
- [Existing Atlas client](../shared/helios_core/atlas/client.py)
- [Existing catalog harvesting](../shared/helios_core/catalog/harvest.py)
- [Operational metadata guidance](builtin/helios-compat/operational-metadata.md)
- [Current implementation status](SEMANTIC_FOUNDATION_STATUS.md)
- [Visual-document workflow](visual-document-facts.md)

The enterprise storage and Atlas work described here remains proposed integration work.
This document does not change the running application or its storage configuration.
