# ImpactIQ

ImpactIQ is a hackathon prototype for AI-assisted change impact analysis in enterprise integration environments, with IBM webMethods Integration Server as the motivating platform.

The repository currently contains an early prototype: a controlled Order Processing demo, a real exported webMethods package used as reference context, validation utilities, and an initial static UI shell. The parser, comparison engine, dependency graph, risk scoring, AI layer, and API are future work.

## Project structure

```text
impactiq/
|-- ai-context/             real exported webMethods artifacts; reference only
|-- demo/OrderProcessing/   one canonical demo package representation
|-- src/                    reserved module boundaries for later milestones
|-- tests/                  standard-library validation scripts
|-- ui/                     static MVP shell with mock analysis data
|-- requirements.txt
`-- README.md
```

## Reference context

`ai-context/` is an exported Integration Server package snapshot. It contains `node.ndf` and `node.idf` metadata, Designer-generated `flow.xml` files, document prototypes, adapter service metadata, REST resources, triggers, and the nested `fileMover_utility` and `offboarding_utility` areas.

It is preserved in place as source/reference context. It is not copied into `demo/`, renamed, refactored, or used as an importable demo package.

The observed conventions are:

- Flow Services use `node.ndf` for service signature/runtime metadata and `flow.xml` with `FLOW VERSION="3.0"`, `SEQUENCE`, `INVOKE`, `MAP`, `LOOP`, and related Designer elements.
- Document Types use `node.ndf` with `Values version="2.0"`, nested `record` values, `rec_fields`, field types, dimensions, and (where applicable) protobuf/event metadata.
- Adapter Services use `node.ndf` with `svc_type` set to `AdapterService`, a `svc_sig` input/output signature, and an opaque serialized `IRTNODE_PROPERTY` value containing adapter-specific configuration.
- Triggers use `node.ndf` with `node_type` `webMethods/trigger`, a trigger record, message type condition, and target service name.
- Service references use the webMethods `package.namespace:service` form, for example `OrderProcessing.orderProcessing.services:CalculatePrice`.

These observations establish the shape used by the demo. They do not claim that the hand-authored demo is byte-for-byte importable into every Designer or Integration Server release.

## Demo and Git versioning

The demo has one canonical current representation under `demo/OrderProcessing/`. Version history is represented by Git commits and tags rather than permanent `demo/v1` and `demo/v2` directories.

The local history created for this milestone is:

```text
demo-original       baseline with the former duplicated v1/v2 demo
        |
        `-- demo-standardized   canonical webMethods-shaped demo
                |
                `-- demo-scheduler-entrypoint   scheduler-owned top-level orchestration
                        |
                        `-- demo-direct-scheduler   direct scheduler entry; no demo trigger
```

Useful commands:

```bash
git diff demo-original..demo-standardized -- demo
git diff demo-standardized..demo-scheduler-entrypoint -- demo
git diff demo-scheduler-entrypoint..demo-direct-scheduler -- demo
git show demo-original:demo/v2/OrderProcessing
git ls-tree -r --name-only demo-direct-scheduler demo/OrderProcessing
```

The current canonical package extends the changed state that was previously in V2 with a direct scheduler-owned entry point. To create the next version, edit the canonical assets, commit the change, and optionally add another tag. A future comparison engine can compare any two Git revisions or tags.

## Order Processing demo

```text
Direct caller
    |
    v
Scheduler
    |
    v
OrderProcessing
    |-- ValidateOrder
    |-- GetCustomer --> GetCustomerDB (Adapter Service)
    |-- CalculatePrice --> ApplyPromotion
    |-- SaveOrder --> SaveOrderDB (Adapter Service)
    `-- SendConfirmation
```

The package includes `OrderDocument` and `CustomerDocument` document types. Flow mappings and service references are represented in Designer-shaped `flow.xml` files. The scheduler is the top-level parent service for direct invocation. This demo does not include a trigger because no service publishes `OrderDocument`; trigger/pub-sub analysis can be added later as a separate scenario. The scheduler wraps the existing `OrderProcessing` child orchestration service with the `tryCatchTemplate` pattern observed in `ai-context/flows/tryCatchTemplate`; child services keep their existing business logic.

## Current change scenario

The current canonical state intentionally includes the changes that ImpactIQ should later detect when compared with `demo-original`:

| Change | Asset | Why it matters |
| --- | --- | --- |
| New Flow Service invocation | `CalculatePrice` invokes `ApplyPromotion` | Adds a new execution path and dependency; test orders with and without promotion codes. |
| Changed mapping | `CalculatePrice` maps `promotionCode` and `discountedSubtotal` | Pricing and downstream totals can change. |
| Document field addition | `OrderDocument` adds `promotionCode` and `discountAmount`; `CustomerDocument` adds `loyaltyTier` | Signatures, validation, mappings, persistence, and API consumers may be affected. |
| Adapter/query change | `GetCustomerDB` selects `loyalty_tier` and filters inactive customers | Lookup behavior and returned data changed. |
| Persistence change | `SaveOrderDB` stores `final_amount` and `discount_amount` | Database writes and regression assertions changed. |
| Dependency change | `CalculatePrice` now depends on `ApplyPromotion` | Upstream/downstream graph and regression scope expand. |
| Entry-point change | `scheduler` invokes `services:OrderProcessing` | The parent dependency graph changes and top-level error handling belongs to the scheduler. |
| Trigger removal | `triggers/OrderTrigger` removed from the demo | The demo is direct invocation based; without a publish service, keeping a trigger would create a misleading pub/sub dependency. |

For adapter services, the real export stores the query inside opaque serialized `IRTNODE_PROPERTY` metadata. The demo keeps the standard adapter `node.ndf` shape and adds a readable `query.sql` fixture beside each adapter so the intended SQL change is reviewable without pretending that the sidecar is a native Designer export.

## Validation and limits

Run:

```bash
python tests/validate_demo.py
```

The validator checks XML well-formedness, standard artifact roots and metadata, flow references, scheduler orchestration, document fields, adapter query fixtures, and the Git migration state. It is not a webMethods parser and cannot prove importability or runtime behavior without a matching Integration Server/Designer installation.

## UI shell

Run the static MVP UI with:

```bash
python -m http.server 8765 -d ui
```

Then open `http://localhost:8765/`. The UI currently loads `ui/mock-analysis.json`, which represents the `SaveOrderDB` customerEmail persistence change. That JSON file is the replacement point for a future analyzer API response.
