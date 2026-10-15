## Purpose

Provides a streaming, human-readable view of retrieval-augmented search progress while preserving the existing file-search result presentation for the final answer.

## ADDED Requirements

### Requirement: Stream retrieval progress
The system SHALL provide a streaming enhanced-search API that accepts the existing enhanced-search request and emits ordered progress events during agent planning, tool calls, and result construction. Each stream SHALL end with exactly one terminal event: either a final result event or an error event.

#### Scenario: Agent uses multiple searches
- **WHEN** the retrieval agent reasons and executes more than one search
- **THEN** the stream emits ordered events for each reasoning summary and tool call
- **AND** the stream emits an event describing the outcome of each search
- **AND** the stream ends with one final result event

#### Scenario: Cached aggregate is available
- **WHEN** an enhanced search is submitted and its aggregate is already cached
- **THEN** the stream indicates that the cached result is being returned
- **AND** the stream ends promptly with the final result event

#### Scenario: Enhanced search fails
- **WHEN** agent configuration, provider communication, tool validation, or result construction fails
- **THEN** the stream ends with one error event containing an actionable user-facing message
- **AND** the error does not expose API keys, provider payloads, or internal message arrays

### Requirement: Present progress in user-friendly language
The system SHALL present retrieval progress as a readable timeline while an enhanced search is running. The timeline SHALL distinguish agent reasoning summaries, tool calls, tool outcomes, and terminal status without requiring users to understand provider protocols or raw tool arguments.

#### Scenario: Agent refines a search
- **WHEN** the agent issues a new search with different query terms or filters
- **THEN** the timeline shows the new step in user-facing language
- **AND** the step identifies the purpose of the search without displaying raw JSON

#### Scenario: Agent provides a visible reasoning summary
- **WHEN** the agent returns user-safe reasoning content for a round
- **THEN** the timeline shows that content as a concise summary
- **AND** hidden model reasoning is not requested or displayed

### Requirement: Integrate the final answer with search results
The final result event SHALL use the existing enhanced-search response contract. When it arrives, the system SHALL stop showing the loading timeline and present the final result using the existing search results list, sorting, pagination, counters, and file interactions.

#### Scenario: Final result arrives
- **WHEN** the stream emits the final result event
- **THEN** the existing search results view presents the returned files
- **AND** the running progress timeline is no longer shown as the primary state
- **AND** the user can optionally review the completed retrieval process

#### Scenario: Final result is empty
- **WHEN** the final result event contains no files
- **THEN** the search results view presents the existing empty search state

### Requirement: Cancel and supersede progress streams
The system SHALL cancel an active enhanced-search progress stream when the user starts a different search or leaves the streaming search context. A superseded stream MUST NOT update the search results view after its replacement starts.

#### Scenario: User starts a new search
- **WHEN** an enhanced search is running and the user submits another search
- **THEN** the previous stream is cancelled
- **AND** the progress timeline is reset for the new search
- **AND** events from the previous stream do not modify the new search state

#### Scenario: User navigates away while searching
- **WHEN** the streaming search context is unmounted
- **THEN** the active stream is cancelled and no further UI updates occur

### Requirement: Preserve non-streaming compatibility
The system SHALL retain the existing non-streaming enhanced-search API and response contract. Cached pagination and sorting requests SHALL continue to reuse the aggregate without re-running the retrieval agent.

#### Scenario: User changes page after streaming completes
- **WHEN** the user requests another page of the completed enhanced search
- **THEN** the request uses the non-streaming enhanced-search behavior
- **AND** the agent is not re-run while the aggregate remains cached

#### Scenario: API caller uses the existing endpoint
- **WHEN** a client calls the existing enhanced-search endpoint
- **THEN** the request and response behavior remains compatible
