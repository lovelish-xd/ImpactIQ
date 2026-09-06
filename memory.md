# ImpactIQ Project Memory

## 1. Project Goal

ImpactIQ is a **deterministic change-impact analyzer for webMethods integration packages**. Given two Git revisions of a webMethods package, it discovers assets, parses their XML/SQL artifacts into structured domain models, compares them semantically, builds an invocation/mapping dependency graph, performs upstream BFS impact analysis, scores risk with explainable deterministic rules, generates regression test recommendations, and presents the results through a web UI with optional AI-powered natural language explanations.

The primary target demo scenario compares commits `02ccdc8` (baseline pipeline fix) and `5d26f89` (add customer email to order persistence) in the `demo/OrderProcessing` package.

---

## 2. Current Architecture

```
Git Revisions
→ GitRevisionReader (git archive tar extraction)       ✅ Implemented & Validated
→ Asset Discovery (rglob node.ndf)                   ✅ Implemented & Validated
→ webMethods Parser (Flow, DocType, Adapter)          ✅ Implemented & Validated
→ Domain Models (frozen dataclasses, immutable)      ✅ Implemented & Validated
→ Snapshot Comparison (fields, mappings, SQL, etc.)   ✅ Implemented & Validated
→ Dependency Graph (invocations, mappings, callers)   ✅ Implemented & Validated
→ Impact Analysis (BFS upstream traversal)           ✅ Implemented & Validated
→ Risk Scoring (deterministic rule-based, 0-100)      ✅ Implemented & Validated
→ Regression Test Recommendations (fact-derived)      ✅ Implemented & Validated
→ Structured Analyzer Result Orchestration           ✅ Implemented & Validated
→ JSON Serialization & Deserialization                ✅ Implemented & Validated
→ Lightweight API Server (http.server, /api/*)        ✅ Implemented & Validated
→ Connected UI (Live mode, Change Details, Paths)     ✅ Implemented & Validated
→ AI Explanation Layer (optional, stdlib urllib)      ✅ Implemented & Validated
→ End-to-End Integration Tests                       ✅ Implemented & Validated
```

---

## 3. Completed Work

### Domain Models — COMPLETE
- [`src/models/domain.py`](file:///d:/Projects/ImapctIQ/impactiq/src/models/domain.py), [`src/models/__init__.py`](file:///d:/Projects/ImapctIQ/impactiq/src/models/__init__.py)
- Frozen dataclasses: `Asset`, `AssetType`, `Field`, `ServiceSignature`, `Mapping`, `Invocation`, `AssetSnapshot`, `Change`, `ChangeType`.
- Immutability enforced via `MappingProxyType`.
- Tests: 6 passing in `tests/test_models.py`.

### webMethods Parser — COMPLETE
- [`src/parser/webmethods.py`](file:///d:/Projects/ImapctIQ/impactiq/src/parser/webmethods.py), [`src/parser/__init__.py`](file:///d:/Projects/ImapctIQ/impactiq/src/parser/__init__.py)
- Asset discovery via `node.ndf` search.
- Parsers for Flow Services (`flow.xml`), Document Types (`node.ndf`), and Adapter Services (`node.ndf` + `query.sql`).
- Tests: 6 passing in `tests/test_parser.py`.

### Git Snapshot Loading — COMPLETE
- [`src/comparison/git_snapshot.py`](file:///d:/Projects/ImapctIQ/impactiq/src/comparison/git_snapshot.py)
- `GitRevisionReader`: extracts package revisions safely without modifying the working tree.
- Uses `filter="data"` on Python 3.12+ to eliminate Python 3.14 tarfile deprecation warnings.
- Validated via `tests/test_comparison.py`.

### Snapshot Comparison — COMPLETE
- [`src/comparison/snapshots.py`](file:///d:/Projects/ImapctIQ/impactiq/src/comparison/snapshots.py), [`src/comparison/__init__.py`](file:///d:/Projects/ImapctIQ/impactiq/src/comparison/__init__.py)
- Field, mapping, invocation, and SQL diffing.
- Produces deterministic `Change` objects with precise before/after snapshots and metadata.
- Tests: 5 passing in `tests/test_comparison.py`.

### Dependency Graph — COMPLETE
- [`src/dependency/graph.py`](file:///d:/Projects/ImapctIQ/impactiq/src/dependency/graph.py), [`src/dependency/__init__.py`](file:///d:/Projects/ImapctIQ/impactiq/src/dependency/__init__.py)
- Directed adjacency graph with `dependents_of` (upstream callers) and `dependencies_of` (downstream callees).
- Explicit edge types: `EdgeType.INVOCATION` and `EdgeType.MAPPING`.
- External service references (e.g. `pub.flow:getLastError`) recorded with `external=True`.
- Tests: 11 passing in `tests/test_dependency.py`.

### Impact Analysis — COMPLETE
- [`src/impact/__init__.py`](file:///d:/Projects/ImapctIQ/impactiq/src/impact/__init__.py)
- Upstream BFS traversal from all changed nodes.
- Distinguishes `CHANGED` (distance 0), `DIRECTLY_AFFECTED` (distance 1), and `TRANSITIVELY_AFFECTED` (distance 2+).
- Records reason and evidence chains for each impacted asset.
- Excludes unrelated package assets.
- Tests: 10 passing in `tests/test_impact.py`.

### Deterministic Risk Scoring — COMPLETE
- [`src/risk/scoring.py`](file:///d:/Projects/ImapctIQ/impactiq/src/risk/scoring.py), [`src/risk/__init__.py`](file:///d:/Projects/ImapctIQ/impactiq/src/risk/__init__.py)
- 0–100 integer score mapped to `LOW`, `MEDIUM`, `HIGH`, `CRITICAL`.
- Weighted scoring rules based on modified assets, added/removed fields, mappings, SQL changes, and direct/transitive callers.
- Returns explicit `RiskDriver` objects explaining every point contribution.
- Tests: 9 passing in `tests/test_risk.py`.

### Regression Test Recommendations — COMPLETE
- [`src/recommendations/__init__.py`](file:///d:/Projects/ImapctIQ/impactiq/src/recommendations/__init__.py)
- Generates prioritized test scenarios directly from detected changes and impact paths.
- Recommends input tests for added fields, data mapping tests, database operation verification for SQL changes, and caller invocation tests.
- Tests: 11 passing in `tests/test_recommendations.py`.

### Structured Analyzer Result — COMPLETE
- [`src/analyzer.py`](file:///d:/Projects/ImapctIQ/impactiq/src/analyzer.py)
- Orchestrates pipeline: `compare_revisions` → `build_dependency_graph` → `analyze_impact` → `calculate_risk` → `generate_recommendations`.
- Returns immutable `AnalysisResult`.
- Tests: 14 passing in `tests/test_analyzer.py`.

### JSON Serialization — COMPLETE
- [`src/serializer.py`](file:///d:/Projects/ImapctIQ/impactiq/src/serializer.py)
- `serialize_analysis` and `serialize_analysis_json`.
- Adheres to the UI JSON contract with extensions for `changes` and `impact`.
- Validated via roundtrip tests.

### Lightweight HTTP API Server — COMPLETE
- [`server.py`](file:///d:/Projects/ImapctIQ/impactiq/server.py)
- Python standard library (`http.server`) serving static UI and API endpoints:
  - `GET /api/commits`: Returns available Git commits for selection.
  - `GET /api/analyze?base=<base>&target=<target>`: Executes deterministic analysis.
  - `GET /api/explain?base=<base>&target=<target>`: Returns optional natural language explanation.

### Connected UI — COMPLETE
- [`ui/index.html`](file:///d:/Projects/ImapctIQ/impactiq/ui/index.html), [`ui/app.js`](file:///d:/Projects/ImapctIQ/impactiq/ui/app.js), [`ui/styles.css`](file:///d:/Projects/ImapctIQ/impactiq/ui/styles.css)
- Live mode auto-detection connecting to `server.py`.
- Commit dropdowns populated dynamically from repository Git log.
- Displays: Metric Strip, Change Summary, Affected Assets cards, SVG Risk gauge with drivers, Change Details breakdown, Impact Path dependency flow diagrams, Recommended Regression Tests, and AI Explanation Layer.
- Fallback to mock data if API is unavailable.
- Validated with headless browser testing.

### AI Explanation Layer — COMPLETE
- [`src/ai/explanation.py`](file:///d:/Projects/ImapctIQ/impactiq/src/ai/explanation.py), [`src/ai/__init__.py`](file:///d:/Projects/ImapctIQ/impactiq/src/ai/__init__.py)
- Generates natural language explanations from structured analysis facts without external dependencies (uses `urllib.request`).
- Supports Google Gemini and OpenAI-compatible endpoints.
- Strict prompt constraints prevent AI from altering risk scores, dependencies, or changes.
- Gracefully indicates unconfigured state when no API key is provided without breaking analyzer functionality.
- Tests: 6 passing in `tests/test_ai.py`.

### End-to-End Pipeline Tests — COMPLETE
- [`tests/test_e2e.py`](file:///d:/Projects/ImapctIQ/impactiq/tests/test_e2e.py)
- 14 integration tests verifying complete pipeline behavior on demo commits (`02ccdc8` → `5d26f89`):
  - Semantic changes: `SaveOrderDB` customerEmail input, `SaveOrder` customerEmail mapping, `SaveOrderDB` query.sql (customer_email column + 6th parameter).
  - Graph invocations and BFS impact traversal.
  - Risk drivers and regression test recommendations.
  - Same-revision baseline comparison producing zero changes, zero affected assets, and zero risk score.

---

## 4. Current Git State

- **Branch:** `master`
- **Commits:**
  - `9b5e7b1`: Initial OrderProcessing integration
  - `02ccdc8`: Fix OrderProcessing pipeline and GetCustomer mapping order
  - `5d26f89`: Add customer email to order persistence
- **Working Tree:**
  - All source code, API server, UI, and test suites are working and verified.

---

## 5. Completed Tests / Validation Summary

Total tests across the project: **100 tests passing** in ~4-5 seconds (`python -B -m unittest discover -s tests`).

| Test File | Tests | Status | Coverage Focus |
|---|---|---|---|
| `tests/test_models.py` | 6 | ✅ Passing | Domain models, immutability, metadata |
| `tests/test_parser.py` | 6 | ✅ Passing | Flow, Document Type, Adapter parsing |
| `tests/test_comparison.py` | 5 | ✅ Passing | Git snapshot comparison, field/mapping/SQL diffs |
| `tests/test_dependency.py` | 11 | ✅ Passing | Adjacency graph, invocations, mappings, external nodes |
| `tests/test_impact.py` | 10 | ✅ Passing | Upstream BFS, direct vs transitive impact, isolation |
| `tests/test_risk.py` | 9 | ✅ Passing | Deterministic score, drivers, level thresholds |
| `tests/test_recommendations.py` | 11 | ✅ Passing | Fact-derived test recommendations, priorities |
| `tests/test_analyzer.py` | 14 | ✅ Passing | Orchestrator, JSON serialization, same-revision |
| `tests/test_ai.py` | 6 | ✅ Passing | AI prompt generation, mock API calls, graceful fallbacks |
| `tests/test_e2e.py` | 14 | ✅ Passing | Full end-to-end integration, demo semantic changes |
| **Total** | **100** | **✅ All Passing** | |

---

## 6. Known Limitations / Important Technical Notes

1. **Deterministic Separation:** AI must never be the source of truth for change detection, impact traversal, or risk scoring; AI is exclusively an explanation layer over structured facts.
2. **Standard Library Only:** The backend and AI layer deliberately avoid third-party pip dependencies to ensure maximum portability and zero-install operation.
3. **No Direct Schema Inference:** Database schema changes are inferred strictly from `query.sql` sidecars and adapter signature inputs.
4. **Git Versioning:** Revisions are referenced by Git commit hashes; no duplicate V1/V2 folders are created.

---

## 7. Configuration & Environment Notes

- **Multi-Provider AI Layer**: `src/ai/explanation.py` supports:
  - **Groq / Grok**: `GROK_API_KEY` or `GROQ_API_KEY` (using ultra-fast models like `openai/gpt-oss-120b`).
  - **xAI Grok**: `GROK_API_KEY` or `XAI_API_KEY` (using `grok-2-latest`).
  - **Google Gemini**: `GEMINI_API_KEY` (using `gemini-3.6-flash`).
  - **OpenAI**: `OPENAI_API_KEY` (using `gpt-4o-mini` or `OPENAI_MODEL`).
- **Automatic .env Loading**: `.env.local` and `.env` in the repository root are loaded automatically without third-party packages.
- **Server Concurrency**: `server.py` uses `ThreadingHTTPServer` with an in-memory cache so simultaneous static, analyzer, and AI explanation requests do not block each other.

---

## 8. Next Recommended Step

- Restart the server process in your terminal (`python server.py`) to run the multi-threaded server with live Groq/Grok AI explanations.
- Create a Git commit to preserve the working tree.


