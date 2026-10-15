# Unified local semantic builder

Open **Semantic Hub** at `/demo` in the running demo.
Select a source card, inspect its connection and versions, then choose **Open Studio**.
The selected connection stays in the URL when opening Studio, Versions & releases, or Data query.
The builder handles finance, manufacturing, pharma, and power through the selected typed DuckDB source snapshot.
It creates semantic definitions, business metadata, structural ontology proposals, and document evidence in one versioned workflow.

## Hub and source connections

1. Open the Hub to browse semantic models across the four built-in local sources.
2. Use **Source details** to inspect connection settings, model status, and version history.
3. Use **Configure data sources** to add a local dataset, Iceberg, Trino, or Atlas profile.
4. Choose **Open Studio** for the selected connection.
5. Complete source inspection, semantic editing, validation, and review in the existing builder.
6. Open **Versions & releases** to publish or activate an approved version.
7. Return to the Hub to browse other sources.

```text
Semantic Hub -> Source details -> Open Studio -> Validation & review -> Versions & releases
     |                                                                      |
     +-> Configure data sources                                      Data query
```

Local dataset profiles currently select one of the four registered fixture packs.
Each added connection has independent drafts, versions, and query state, even when two connections select the same pack.
Built-in connections retain existing state paths and previously saved versions.
The `--dataset` launch argument sets the fallback source for older links; the Hub displays all four sources.

Iceberg and Trino profiles store settings but do not connect or import schemas in this build.
Atlas profiles store metadata connection settings; Atlas also needs a paired query engine for SQL validation.
These remote profiles open a Studio setup page that explains the missing import adapter.
They do not expose fixture models or run local sample queries.
Credential references name environment variables; the profile database does not store credential values.

Profiles persist in `<state-dir>/connections.sqlite`.
Use `/demo/api/hub` for the catalog and `/demo/api/hub/source?source=<id>` for one source.
Studio and query API calls select their connection with `?source=<id>`.
Their mutation requests still require the matching pack, snapshot, and runtime session binding.

The [Hub screenshot](walkthrough/semantic-hub/1440-hub.png) and [source details screenshot](walkthrough/semantic-hub/1440-source-details.png) show the updated navigation.
Desktop and mobile captures live in `docs/walkthrough/semantic-hub/`.
Hub regression checks cover source isolation, persisted versions, all four connection forms, and source-specific navigation.
The existing builder browser checks also pass across all four datasets at desktop and mobile sizes.

Follow the [illustrated end-to-end walkthrough](walkthrough/semantic-builder/index.html) for nineteen captured builder steps.
Those screenshots predate the Hub landing page; first select a source and open Studio.
The former final builder step named Semantic Hub is now **Versions & releases**.
The [PDF edition](walkthrough/semantic-builder/semantic-builder-walkthrough.pdf) includes the same storyline and screenshots.
The walkthrough folder also includes a business note, independent SQL, and the published sample consumer package.

```text
Source evidence -> staged proposal -> explicit apply -> editable draft
                                                           |
                                                           v
Published export <- immutable artifacts <- item review <- SQL validation
       |
       v
Query activation
```

Start a local process with the OpenAI default endpoint and GPT-4o:

```sh
python start_demo.py --dataset power --port 8084 \
  --state-dir /tmp/helios-builder-review \
  --llm-token-file ~/tokens/openai --llm-model gpt-4o
```

The credential stays in process memory and is not stored in proposal or version artifacts.
The default endpoint is `https://api.openai.com/v1`.
Use `--llm-base-url` for another OpenAI-compatible endpoint.
Existing environment-based provider configuration remains available when the token-file option is omitted.
Both drafting and playground profiles inherit this provider by default. The playground interprets questions only against published semantic versions.

## Model configuration

Open **Model configuration** in the sidebar or visit `/demo/llm`.
Data-source configuration remains inside Semantic Hub.

1. Select **Semantic draft generation**, **Model playground**, or **Supporting-material embeddings**.
2. Inherit the launch configuration, disable that purpose, or select a custom OpenAI-compatible endpoint.
3. For custom settings, enter the model, base URL, and credential environment variable name.
4. Save the selected profile, then use **Test saved connection**.
5. Generate a Studio proposal, or run a reviewed sample and select **Explain result with LLM**.

The existing GPT-4o launch configuration uses `https://api.openai.com/v1`.
The token-file launch option populates `INFERENCE_TOKEN` in the server process.
Draft and query profiles inherit that launch configuration initially.
The embedding profile defaults to disabled with `text-embedding-3-small`; inherited mode reuses the launch credential and endpoint only.
The local review instance now has that embedding profile enabled and connection-tested.
Use [Supporting materials](supporting-materials.md) to analyze documents, review cross-model links, and add versioned evidence to drafts.
Settings persist independently in `<state-dir>/llm-settings.sqlite`, with revision checks for stale saves.
The UI stores credential references rather than credential values.

Query explanations describe server-executed reviewed results; this feature does not enable free-form question-to-SQL planning.
The server re-executes the bound sample and verifies its result hash before requesting an explanation.
The LLM receives at most 20 result rows and 10 columns, within a bounded evidence payload.
The model cannot replace the SQL, bypass review, activate a version, or edit the result.
Generated explanations appear separately from execution evidence and identify their provider and model.

## Author and review a context

Use [the four starter reference queries](demo-reference-sql.md) when validating the original sample metrics.
Every metric currently requires reference SQL; automatic suggestions remain proposed work.

1. Inspect source schemas, column types, bounded sample rows, and serving documents.
2. Generate a deterministic evidence proposal or request a configured LLM proposal.
3. Inspect the staged proposal, source references, assumptions, warnings, and model provenance.
4. Apply the selected proposal explicitly to the current draft revision.
5. Edit business metadata, metrics, field roles, dataset meanings, glossary terms, and directed relationships.
6. Add typed metric filters when inclusion, exclusion, or date rules must affect execution.
7. Append local text documents and supply explicit entity links where needed.
8. Write independent reference SQL for each metric.
9. Save the draft and validate compiled SQL against the independent reference results.
10. Review every required item, including source documents, appended documents, metadata, and ontology mappings.
11. Approve a complete version after all required decisions and technical checks pass.
12. Inspect its immutable artifacts in Versions & releases and publish the version locally.
13. Export the published consumer package or activate the published version for local queries.

### View a confirmed version

1. Open the source details in Semantic Hub, or open **Versions & releases** in Studio.
2. Click the version name, such as **v1.0**, or choose **View version**.
3. Explore the read-only version canvas, or expand definitions and review evidence below it.
4. Use **Download context JSON** to save the complete immutable release.
5. Choose **Back to versions** to return to version management.

Expand **Compare <version>** inside a version history entry to compare that release with another release, starter definitions, or the saved draft.
Comparison results stay inside that entry. Draft comparisons show the saved draft as the after state.

The viewer is read-only for reviewed and published versions.
Its canvas supports search, zoom, fullscreen, column inspection, relationship navigation, and saved document inspection.
Edit controls, relationship creation, and node dragging are disabled.
The graph endpoint accepts `/demo/api/context/source-graph?source=<connection-id>&version=<version>`.
It builds the graph from the archived release schema and definitions, including SQL-derived metric dependencies.
The canvas shows document content and links from that release's archived artifacts.
It loads the saved release and its archived artifacts, independently of the current draft.
Opening the viewer does not create a draft, publish a version, or change the version used for queries.
Use the separate **Create draft** action in version history to start editing from a confirmed version.
Older versions without archived artifacts show that limitation instead of substituting current draft content.
Direct links use `/demo/context?source=<connection-id>&version=<version>#hub`.

Proposal generation records a candidate without changing the draft.
Applying a candidate changes the draft and clears its validation and decisions.
Applying a candidate does not approve or publish it.
The live proposal checks use GPT-4o when the configured provider selects that model.
The builder records the actual provider and model in proposal provenance.
It does not require one fixed model for every deployment.

Proposals use serving evidence and bounded source profiles.
They do not use evaluation answers or generate independent reference SQL.
Unsupported candidates leave the current draft intact.
Declared source metrics remain separate when generated candidates change their source expression or fixed filters.
Reviewers must inspect units, aggregation meaning, source status rules, and reporting periods.
Executable SQL alone does not establish a reasonable business metric.

## Metadata and executable filters

Metrics record unit, grain, time rule, owner, synonyms, example questions, evidence references, assumptions, and rationale.
They also record inclusion rules, exclusion rules, and ontology concept references.
Dataset meanings, field meanings, field roles, and glossary terms provide additional business context.

Descriptions record intent.
Typed filters and aggregate expressions control execution.
An inclusion-rule description does not automatically insert a SQL condition or convert currency.
Fixed filters must reference fields in the metric's fact table.
The compiler combines fixed filters with caller filters.
CASE expressions can also encode conditional aggregation.

Each metric needs independent reference SQL with the exact metric output alias.
Grouped references return grouping columns first, followed by that alias.
Both query results use the selected serving snapshot.
For the original power metric, an independent reference can calculate:

```sql
SELECT SUM(import_kwh) AS measured_import_kwh
FROM meter_readings
WHERE quality_status = 'VALID' AND is_estimated = 'false'
```

Confirm these conditions against the business definition before review.
The original manufacturing downtime metric measures planned maintenance minutes.
The original pharma assay metric describes draft laboratory results.
Neither definition establishes an operational release decision.

Generated Ossie metrics carry reviewed descriptive metadata in the HELIOS `business_context` extension.
The shared retrieval index preserves this metadata and indexes relevant business terms.
The extension excludes independent reference SQL and executable fixed-filter definitions.
Consumers must preserve executable semantics through the model and compiler contracts.
This increment does not change the separate document embedding implementation.

## Document and ontology artifacts

Open **Source data → Documents & unstructured data** to inspect source documents and uploads.

1. Select a document to read its content, source record links, and current review status.
2. Choose **Add document**, then select a plain-text or Markdown file.
3. Check the file preview and optionally expand **Link to a data record**.
4. Choose **Add to draft**. The new document appears in the list with pending review.
5. Choose **Review documents** to open the document review items.

Documents follow one path through the workspace:

```text
Source document → Canvas evidence → Item review → Version evidence
                       │
                       └── verified source record key
```

Choose **Show in canvas** from a document preview.
The canvas focuses on that document and its linked datasets.
Dotted blue edges identify supporting evidence and display the record key.
They do not represent SQL joins, metric dependencies, or vector embeddings.
Documents without record links remain model-wide context and have no invented edges.

The overview groups documents into one collection to keep large sources readable.
Open the collection or the Documents tree to select an individual document.
The inspector shows its content, record links, technical status, and human decision.
Choose **Review this document** to open its review row.
Choose **Open in canvas** in that row to return to the same evidence.
**Show all**, under View options, restores the grouped overview.
Navigation does not modify definitions or approve documents.

The list distinguishes source documents from uploaded documents.
Its record links show verified keys; document claims still require human review.
Document text remains readable even when a draft metric contains invalid SQL.
PDF, Word, OCR, and external document connectors are not supported in this increment.
**Version evidence** appears under Validation & review and Versions & releases.
It retains inspection of the selected version's metadata, ontology, and immutable document evidence.

The source snapshot retains actual serving document bytes and its declared document manifest.
Finance and power currently have no serving documents.
Their artifact bundles report this coverage gap.
Manufacturing and pharma preserve synthetic maintenance, batch, and deviation notes.

Appended documents accept local `.txt` or `.md` content up to 256 KiB.
A draft supports up to twenty appended documents.
Each optional entity link uses `table.column=value` against the selected serving snapshot.
The column must contain unique, nonempty keys, and the linked value must exist.
Ambiguous inferred source anchors remain unmapped and produce warnings.

Attachments bind immutable content bytes, filename, SHA-256, source snapshot hash, and explicit links.
Changing content creates a new attachment reference and requires another draft review.
Document bodies remain assertions with citations.
They do not become authoritative source facts or automatically resolve every identifier in the text.

Artifact bundles contain the semantic model, metadata inventory, structural ontology graph, typed source mapping, document content, manifests, and warnings.
Table classes, metric concepts, and join edges describe source structure.
They remain proposals with separate review evidence.
Reviewing a release does not certify an enterprise domain ontology.
The graph uses existing ontology node labels and edge types.
Declared join edges preserve source fields, target fields, cardinality, and meaning.

## Canvas, decisions, and versions

Studio provides an object tree, canvas, and inspector.
The canvas toolbar keeps mode selection, object search, Connect fields, Fit, and View options visible.
View options groups the graph view, neighborhood controls, column inspection, and fullscreen.
Columns inspects the selected dataset. Neighbors returns to that dataset's relationships, even when a column is selected.
Show all restores the semantic overview. The fullscreen button changes to Exit fullscreen while the canvas fills the screen.
Zoom controls sit on the canvas. The Connect fields dialog uses a single-column form on all screen sizes.
Forms offer an alternative to field connections on the canvas.
The canvas distinguishes declared relationships from dependencies parsed from metric SQL.
It does not show execution-observed lineage.
Node positions remain temporary layout preferences. The canvas no longer exposes named saved views.
Layout changes do not change the semantic draft.

Stable object identifiers distinguish renames from deletion and addition.
Change review displays added, modified, removed, and affected objects against a visible baseline.
Reviewers can approve selected eligible items or request changes.
The review table supports numbered pages, 10/25/50 rows per page, and selection across pages.
Batch decisions appear separately from pagination.
The confirmation dialog shows selected objects, reviewer, decision note, and explicit confirmation in a single-column form.
The version page lists failed checks and unapproved-object counts, with links to validation and missing reference SQL.
The review table separates missing validation from actual blockers.
“Not validated” means the saved draft needs validation; “Unsaved changes” means existing evidence no longer applies.
“Blocked” includes the reason that prevents approval.
“Ready for review” means an item is eligible for human review, not that its business claims are approved.
“Unchanged” compares definitions with the baseline; it does not imply validation or approval.
Blocked items remain unresolved after a mixed batch decision.
Item approval does not approve the complete version.

Drafts use optimistic revisions.
A stale browser cannot overwrite a newer revision.
Semantic edits clear validation and item decisions.
Validation and decisions bind to the exact revision, definition hash, and evidence hash.

Complete approval stores immutable definitions, Ossie content, SQL evidence, item decisions, and artifact bundles.
Version names remain immutable within their source snapshot.
Older releases retain their original artifact bytes when newer drafts change.
Publication and activation remain separate actions.
Only a published release can become active for local queries.
Restoring a release creates another draft that needs validation and review.

SQLite state lives at `<state>/<pack>/<snapshot>/context.sqlite`.
The Docker demo uses the existing `/state` volume.
Source fixtures retain their original draft state.
Reviewer names provide local attribution, not authenticated enterprise identity.
Publication registers a version in the local Hub.

## Export and integration boundaries

`/demo/api/context/artifacts` inspects the draft or a named version.
`/demo/api/context/export?version=<published-version>` exports a verified local publication.
The export contains separate `manifest`, `document`, `context`, and `artifacts` objects.
The manifest distinguishes document, context, source-snapshot, and release hashes.
Consumers must not pass the entire context package to an Ossie document loader.

The local builder workflow is implemented.
Warehouse harvesting, enterprise publication, and downstream consumer adapters remain separate acceptance work.
Studio publication does not automatically register a model in the authenticated MCP artifact store.
UOB and Semantic Guardrails still need compatible adapters for this release package.
The [Model playground](model-playground.md) supports bounded typed question interpretation against published versions.
Arbitrary SQL generation and document passage answers remain outside this local query contract.
Document retrieval still requires verified model and source isolation before integration.

## Validation and verification

The builder supports twenty metrics, twenty single-key many-to-one relationships, and three grouping fields per metric.
Each metric uses one fact table and one SUM, AVG, COUNT(column), MIN, or MAX aggregate.
Grouping requires one unambiguous directed many-to-one route.
Target keys must be unique and non-null.
Every source row must match its declared target.
These checks prevent supported inner joins from multiplying or dropping fact rows.

Each query has a five-second deadline and a 256 MB DuckDB memory limit.
Validation rejects results above two hundred rows.
Column order must match; row order need not match.
Numeric comparison uses an absolute tolerance of `1e-8`.
Agreement on a fixture does not establish correctness on unseen production data.

Run focused acceptance checks in an environment with the project dependencies:

```sh
PYTHONPATH=shared:. python -m pytest -o pythonpath=shared \
  apps/helios/tests/test_demo_context.py \
  apps/helios/tests/test_demo_runtime.py \
  apps/helios/tests/test_builder_api.py \
  apps/helios/tests/test_builder_proposals.py \
  apps/helios/tests/test_builder_retrieval_metadata.py \
  apps/helios/tests/test_builder_artifacts.py -q
```

Run the browser workflow with a temporary workspace:

```sh
python apps/helios/workbench/check_demo_browser.py \
  --context-builder --output /tmp/helios-context-browser

python apps/helios/workbench/check_builder_increment_browser.py \
  --output /tmp/helios-builder-increment-browser
```

Run live proposal acceptance with a linked synthetic note in every pack:

```sh
python apps/helios/workbench/check_builder_live.py \
  --credential-file ~/tokens/openai --model gpt-4o --attach-sample \
  --output /tmp/helios-builder-acceptance
```

The browser checks use automated test reviewers and isolated workspaces.
They do not install approvals in the operator's workspace.
See [artifact reasonableness assessment](builder-artifact-assessment.md) for source coverage and live proposal findings.
The [validation summary](builder-validation.json) records the completed 12 October 2026 acceptance run.
