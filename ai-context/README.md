# ai-context

`ai-context/` is the reference webMethods Integration Server package snapshot for the ImpactIQ prototype.

ImpactIQ is an AI-assisted change impact analysis project for enterprise integration environments. The prototype uses a controlled demo package under `demo/`, but that demo should be shaped by real webMethods artifacts rather than invented XML. This folder provides those real artifacts.

## What This Folder Contains

This package includes exported webMethods-style source artifacts such as:

- `flows/` - Flow Services with `flow.xml` and `node.ndf` metadata.
- `docs/` - Document Type definitions using webMethods `node.ndf` record structures.
- `adapters/` - Adapter Service metadata and signatures.
- `triggers/` - Trigger metadata showing message type and target service relationships.
- `fileMover_utility/` - A utility area with its own services and dependencies.
- `offboarding_utility/` - A second utility area with a different service/dependency shape.
- `node.idf` - Package/folder interface metadata.

These files are useful because they show actual webMethods conventions: `Values version="2.0"` metadata, `FLOW VERSION="3.0"` flow definitions, `INVOKE`, `MAP`, `MAPCOPY`, `LOOP`, service signatures, document records, trigger conditions, and adapter metadata patterns.

## How ImpactIQ Uses ai-context

Use this folder as reference/input context when building ImpactIQ capabilities:

1. Study real webMethods package structure.
2. Identify how Flow Services, Documents, Adapters, Triggers, and folders are represented.
3. Validate that the simplified demo under `demo/OrderProcessing/` follows realistic artifact shapes.
4. Use these files later as parser fixtures when implementing dependency extraction and comparison logic.
5. Compare naming patterns such as `package.namespace:service` references across flows and triggers.

The controlled demo should stay small and readable. `ai-context/` helps make that demo realistic.

## How To Inspect It

From the project root:

```powershell
rg --files ai-context
rg -n "INVOKE|MAPCOPY|svc_type|node_type|messageType|serviceName" ai-context
```

To check XML well-formedness for this reference package:

```powershell
Get-ChildItem -Path ai-context -Recurse -File -Include *.xml,*.ndf,*.idf |
  ForEach-Object { [xml](Get-Content -Raw -LiteralPath $_.FullName) | Out-Null }
```

## Important Guardrails

- Treat `ai-context/` as reference material, not as the canonical demo.
- Do not move, rename, split, or reshape this package just to fit the demo.
- Do not create `ai-context/v1` or `ai-context/v2`.
- Do not copy the whole package into `demo/`.
- Do not assume every file is byte-for-byte portable across all webMethods or Designer versions.
- Adapter-specific settings may be stored in opaque serialized metadata such as `IRTNODE_PROPERTY`.

The demo lives in `demo/OrderProcessing/`. Git history represents demo evolution. `ai-context/` remains the real-world reference that keeps the prototype grounded.


---

# ImpactIQ — Functional AI Context

## 1. Project Overview

- **Project Name:** ImpactIQ
- **Event:** 7 Eleven Hackathon 2026
- **Purpose:** Help enterprise integration developers understand the impact of a change before it is deployed.

### One-line description

ImpactIQ analyzes changes in enterprise integrations, identifies what may be affected, assesses the level of risk, and recommends what should be tested before deployment.

## 2. Business Problem

Enterprise integrations are made up of many connected components. A change to one component can unintentionally affect other services, interfaces, data, or downstream systems.

Today, developers often need to manually:
- Find what changed.
- Trace dependencies.
- Identify affected services.
- Determine the potential risk.
- Decide which regression tests are required.
- Explain the impact to reviewers or other developers.

This process can be time-consuming and important dependencies can be missed.

### Consequences

- Regression defects
- Unnecessary testing
- Missed testing
- Production incidents
- Longer deployment cycles
- Increased manual effort

## 3. ImpactIQ's Main Goal

ImpactIQ should answer five questions whenever a change is introduced:
1. What changed?
2. What could be affected?
3. How significant is the impact?
4. Why could it be affected?
5. What should we test before deployment?

## 4. Main User

The primary user is an enterprise integration developer.

Other potential users:
- Integration leads
- QA/test engineers
- Solution architects
- Technical reviewers
- Release/deployment teams

## 5. Core Functional Capabilities

### 5.1 Compare Integration Versions

The user should be able to provide an older version and a newer version of an integration.

ImpactIQ should compare the two and identify meaningful differences.

It should distinguish between:
- Added components
- Removed components
- Modified components
- Changed relationships
- Changed data structures
- Changed mappings
- Changed processing logic

The focus should be on meaningful functional changes, not simply showing that files are different.

### 5.2 Identify Changes in Services

ImpactIQ should identify changes to integration services.

Examples:
- A new service is introduced.
- An existing service is removed.
- One service starts calling another service.
- An existing service call is changed.
- The order of processing changes.
- A decision or condition changes.

The result should clearly explain the change.

**Example:**
> A new credit validation step was added to Order Processing before the order is saved.

### 5.3 Identify Data/Document Changes

ImpactIQ should identify changes to data structures used by integrations.

Examples:
- A new field is added.
- A field is removed.
- A field's data type changes.
- A field becomes mandatory or optional.
- The structure of a document changes.

**Example:**
> creditScore was added to Customer information. Services consuming Customer information may need validation.

### 5.4 Identify Mapping Changes

ImpactIQ should identify changes in how data moves between components.

Examples:
- A source field is mapped to a different target field.
- A mapping is removed.
- A new mapping is introduced.
- A transformation changes.
- A field is no longer populated.

**Example:**
> Customer email is now mapped to a different order field. This may affect downstream order processing.

### 5.5 Identify Adapter/External System Changes

ImpactIQ should identify changes involving connections to external systems.

Examples:
- A database operation changes.
- A query changes.
- Input/output data changes.
- A different external operation is used.
- A dependency on an external system is added or removed.

**Example:**
> The customer lookup now retrieves an additional credit-related value from the database.

## 6. Dependency Analysis

This is one of ImpactIQ's most important capabilities.

ImpactIQ should understand relationships between integration components.

For example:

```text
Customer Information
        ↓
Customer Service
        ↓
Order Processing
        ↓
Save Order
        ↓
Order Database
```

If Customer Information changes, ImpactIQ should determine which other components may be affected.

### Dependency types

ImpactIQ should identify:
- Direct dependencies
- Indirect dependencies
- Upstream dependencies
- Downstream dependencies

## 7. Impact Analysis

After finding a change, ImpactIQ should determine its potential impact.

**Example:**

- **Changed:**
  - Customer Information
- **Directly affected:**
  - Customer Service
- **Potential downstream impact:**
  - Order Processing
  - Credit Validation
  - Order Persistence

The user should be able to understand why each component was identified.

ImpactIQ should avoid simply listing every component in the system. The results should focus on components that are meaningfully connected to the change.

## 8. Risk Assessment

ImpactIQ should classify the potential impact of a change.

Possible levels:
- Low
- Medium
- High
- Critical

Risk should consider factors such as:
- Nature of the change
- Number of affected components
- Importance of affected components
- Whether existing behavior was removed or changed
- Whether data structures changed
- Whether external systems are involved
- Whether the change affects an important processing path
- Whether multiple downstream components depend on the changed component

The risk result should include a clear explanation.

**Example:**
> **High Risk:** An existing customer field changed its data type and is consumed by multiple downstream services. This may cause data compatibility issues.

## 9. Regression Test Recommendations

ImpactIQ should recommend focused regression tests based on the detected changes and affected components.

The goal is not to recommend every possible test.

The goal is to identify the tests that are most relevant to the change.

### Example

**If a credit validation step is added:**
- Customer below credit limit
- Customer at credit limit
- Customer above credit limit
- Missing credit information
- Approved order reaches persistence
- Rejected order does not reach persistence

**If a data field changes:**
- Existing valid data
- New data format
- Missing optional data
- Invalid data
- Downstream processing
- End-to-end processing

## 10. AI-Powered Explanation

ImpactIQ should make technical analysis easier to understand.

The user should receive a simple explanation of:
- What changed
- Why it matters
- What could be affected
- Why those components are affected
- How serious the change is
- What should be tested

**Example:**
> The Order Processing integration now performs a credit-limit check before saving an order. This introduces a new dependency and changes the order-processing path. Orders that fail the credit check may no longer reach the database, so both approved and rejected credit scenarios should be tested.

The AI should explain findings rather than inventing unsupported dependencies or changes.

## 11. Change Summary

ImpactIQ should provide a quick summary for developers and reviewers.

**Example:**

```text
Impact Analysis

Risk: HIGH

Changes detected: 4
Potentially affected components: 6
Recommended regression tests: 7

Major changes:
• New credit validation
• Customer document updated
• Order mapping changed
• Database operation changed
```

## 12. Impact Visualization

ImpactIQ should make dependencies and potential impact easy to understand visually.

**Example:**

```text
Customer Document
       ↓
Customer Service
       ↓
Order Processing
      / \
     /   \
Credit   Save Order
Check       ↓
          Database
```

The user should be able to quickly see:
- What changed
- What depends on it
- What may be affected
- How the impact spreads

## 13. Before vs After View

ImpactIQ should allow users to understand the difference between two integration versions.

**Example:**

### BEFORE
```text
Order Processing
 ├── Validate Order
 ├── Get Customer
 ├── Calculate Price
 └── Save Order
```

### AFTER
```text
Order Processing
 ├── Validate Order
 ├── Get Customer
 ├── Check Credit       ← Added
 ├── Calculate Price    ← Changed
 └── Save Order
```

This should make changes understandable even before looking at the detailed analysis.

## 14. Prioritization

When many changes are detected, ImpactIQ should help the user focus on the most important ones.

For example:
- **HIGH:** Database operation changed
- **HIGH:** Customer field datatype changed
- **MEDIUM:** Mapping changed
- **LOW:** Optional field added

This prevents developers from having to manually inspect every detected difference.

## 15. Developer Review Summary

ImpactIQ should provide a concise summary that could be used during:
- Code/integration review
- Deployment review
- Change approval
- Regression planning

**Example:**
- **Change:** Added credit validation to Order Processing.
- **Impact:** Order persistence behavior may change for customers failing validation.
- **Risk:** High.
- **Affected areas:** Order Processing, Customer validation, Order Database.
- **Testing:** Validate approved, rejected, and boundary credit scenarios.

## 16. Example End-to-End Scenario

### Original integration
```text
Order Processing
      ↓
Validate Order
      ↓
Get Customer
      ↓
Calculate Price
      ↓
Save Order
```

### Developer changes it
```text
Order Processing
      ↓
Validate Order
      ↓
Get Customer
      ↓
Check Credit Limit     ← New
      ↓
Calculate Price        ← Mapping changed
      ↓
Save Order
```

Customer information is also changed:

**Before:**
- Customer ID
- Name
- Email

**After:**
- Customer ID
- Name
- Email
- Credit Score          ← New

### ImpactIQ result

- **4 meaningful changes detected**
- **HIGH RISK**

**Potentially affected:**
- Order Processing
- Calculate Price
- Save Order
- Customer Service

**Why:**
The new credit validation changes the processing path, while the Customer information change affects data used by downstream processing.

**Recommended testing:**
- Approved customer
- Rejected customer
- Boundary credit score
- Existing order calculation
- Order persistence
- Customer data compatibility