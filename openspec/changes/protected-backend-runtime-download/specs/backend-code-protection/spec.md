## Purpose

Packages the backend in a protected form that avoids plaintext source distribution while keeping application updates small and runtime dependencies reusable.

## ADDED Requirements

### Requirement: Protected backend package
The system SHALL package backend application code inside the signed app in a protected form and SHALL NOT include plaintext backend source files in a release app bundle. The packaged backend SHALL start with the downloaded runtime and expose the same production API behavior as development source execution.

#### Scenario: Release bundle inspection
- **WHEN** a release app bundle is inspected
- **THEN** no backend `.py` source file from the application package is present

#### Scenario: Backend starts from protected package
- **WHEN** the runtime and model are ready and the app starts the backend
- **THEN** the protected backend publishes its connection information and becomes healthy without requiring the user's Python environment

### Requirement: Worker process compatibility
The protected backend SHALL support its multiprocess import and query workers on every release platform. Protected code SHALL not cause worker startup to import a second API server, fail to find application modules, or lose the model cache configuration.

#### Scenario: Import and query workers
- **WHEN** an import task and a query task run at the same time
- **THEN** each worker starts from the protected package and only the main backend process listens on the API port

#### Scenario: Model worker restart
- **WHEN** a model worker exits and is started again
- **THEN** the restarted worker loads the selected model set and continues using the same protected backend package

### Requirement: Isolated runtime environment
The system SHALL start the protected backend with the downloaded interpreter and an environment that prevents user Python settings from redirecting application imports or model loading. The model cache location SHALL be supplied explicitly by the desktop app.

#### Scenario: Host has conflicting Python variables
- **WHEN** the desktop app starts while `PYTHONHOME`, `PYTHONPATH`, or `VIRTUAL_ENV` points to another Python installation
- **THEN** the backend still uses its downloaded runtime and protected package

### Requirement: Protection scope
Code protection SHALL be treated as tamper resistance for application source, not as the licensing trust boundary. License validity, device binding, and update authentication SHALL continue to depend on compiled desktop code and server verification rather than checks implemented only in protected Python.

#### Scenario: Protected Python is analyzed
- **WHEN** a determined user reverse engineers or instruments the protected Python code
- **THEN** license enforcement remains governed by compiled desktop and server-side verification rather than yielding control exclusively to Python-side checks
