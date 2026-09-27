## Context

See  for motivation. Currently,  and  both declare local styles, detail slide-panels, pagination, and list items. This refactoring unifies the shared components to improve readability and conform directly to the backend schema of .

## Goals / Non-Goals

**Goals:**
- Extract four frontend components (, , , ).
- Eradicate intermediate data mappings, directly feeding the backend-typed  into these components and views.
- Consolidate and unify styles to reduce rendering duplications.

**Non-Goals:**
- Introduce new user-facing functionalities or features.
- Change API endpoints or network protocols.

## Decisions

### 1. Directly Consume  Types
Both pages used to define intermediate interfaces such as  or localized . 
**Decision**: Remove local type definitions. Use the imported  type from  as the standard type.
* Rationale: Reduces type boilerplate and ensures any updates from backend auto-propagate to components.

### 2. Component Extraction Boundaries
- ****: Under , export a React component displaying file details.
- ****: Under , export a generic pagination component that takes simple number inputs (, , , and ).
- ****: Under , handles rendering single row search result.
- ****: Under , handles rendering single folder card.

## Risks / Trade-offs

- **Risk**: Differences in tag-coloring algorithms between search tags and folder tags.
  - *Mitigation*: Unify badge coloring in  and individual items by supporting standard CSS helper mappings.
