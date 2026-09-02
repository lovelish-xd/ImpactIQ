# Canonical Demo

`OrderProcessing/` is the single current demo representation. It follows the artifact shapes observed in `ai-context/`:

- `node.idf` marks namespace/folder interfaces.
- `node.ndf` stores Designer-style service, document, and adapter metadata.
- `flow.xml` stores Flow Service execution and pipeline operations.
- `pdt.proto` is included for the OrderDocument event/document prototype.

Adapter query text is kept in `query.sql` sidecars because the reference exports serialize adapter-specific metadata inside opaque `IRTNODE_PROPERTY` values. The sidecars are demo review fixtures, not claims of native Designer export files.

## Scheduler Entry Flow

The canonical entry point is the scheduler Flow Service stored directly under `OrderProcessing/ns/orderProcessing/scheduler/`. Its Flow XML is `scheduler/flow.xml` and its service metadata is `scheduler/node.ndf`.

In this demo, the scheduler service is a direct orchestration entry point. It is not started by publish/subscribe messaging, and there is no demo trigger because the package does not publish an `OrderDocument`.

The scheduler owns the top-level try/catch behavior. Its Flow XML follows the `tryCatchTemplate` pattern observed in `ai-context/flows/tryCatchTemplate`: child service failures propagate back to the scheduler, where the catch block invokes `pub.flow:getLastError` and exits the parent flow. The child services remain focused on their existing business logic.

| Step | Flow service | Input | Output | Description |
| --- | --- | --- | --- | --- |
| 1 | `scheduler` | `OrderProcessingInput`, a reference to `OrderDocument` | No direct output document | Parent scheduler/orchestrator. Wraps the child invocation in the top-level try/catch copied from the reference `tryCatchTemplate`. |
| 2 | `OrderProcessing` | `OrderProcessingInput`, a reference to `OrderDocument` | No direct output document | Child orchestration service that preserves the existing business execution sequence. |
| 3 | `ValidateOrder` | `OrderDocument` | `validationResult` | Checks that the incoming order has the required order, customer, and line-item data before downstream processing continues. |
| 4 | `GetCustomer` | `OrderDocument` | `CustomerDocument` | Maps `OrderDocument/order/customerId` into the `GetCustomerDB` adapter input, invokes the adapter service, and maps customer results back into `CustomerDocument`. |
| 5 | `GetCustomerDB` | `customerId`, optional `$connectionName` | `results[]` with `customerId`, `customerName`, `customerEmail`, and `loyaltyTier` | Adapter service that reads customer profile data. The standardized demo keeps readable SQL in `adapters/GetCustomerDB/query.sql`. |
| 6 | `CalculatePrice` | `OrderDocument`, `CustomerDocument` | Updated `OrderDocument` | Calculates order pricing, maps `promotionCode` and `subtotal` into `ApplyPromotion`, then maps `discountAmount`, discounted subtotal, and total amount back into `OrderDocument`. |
| 7 | `ApplyPromotion` | `promotionCode`, `subtotal` | `discountAmount`, `discountedSubtotal` | Applies the demo promotion rule. This is the new flow invocation added in the changed demo state so ImpactIQ can later detect a dependency and execution-path change. |
| 8 | `SaveOrder` | `OrderDocument`, `CustomerDocument` | No direct output document | Maps the finalized order values into `SaveOrderDBInput`, including `finalAmount` and `discountAmount`, then invokes the persistence adapter. |
| 9 | `SaveOrderDB` | `orderId`, `customerId`, `finalAmount`, `discountAmount`, `orderStatus`, optional `$connectionName` | `rowsAffected` | Adapter service that persists the order. The readable insert statement is kept in `adapters/SaveOrderDB/query.sql`. |
| 10 | `SendConfirmation` | `OrderDocument`, `CustomerDocument` | No direct output document | Sends the confirmation message after validation, enrichment, pricing, and persistence have completed. |

The top-level execution order is:

```text
scheduler
  -> OrderProcessing
       -> ValidateOrder
       -> GetCustomer
            -> GetCustomerDB
       -> CalculatePrice
            -> ApplyPromotion
       -> SaveOrder
            -> SaveOrderDB
       -> SendConfirmation
```

Key pipeline mappings represented in the demo:

- `GetCustomer` copies `/OrderDocument/order/customerId` to `/GetCustomerDBInput/customerId`.
- `GetCustomer` copies adapter result fields into `/CustomerDocument/customer/*`, including `loyaltyTier`.
- `CalculatePrice` copies `/OrderDocument/order/promotionCode` and `/OrderDocument/order/subtotal` into `ApplyPromotion`.
- `CalculatePrice` copies `discountAmount` and `discountedSubtotal` back into `OrderDocument`.
- `SaveOrder` copies `/OrderDocument/order/totalAmount` to `/SaveOrderDBInput/finalAmount`.
- `SaveOrder` copies `/OrderDocument/order/discountAmount` to `/SaveOrderDBInput/discountAmount`.
